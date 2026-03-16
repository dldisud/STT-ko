param(
    [string]$AppName = "KoreanSTT",
    [string]$AppVersion = "1.0.0"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$VenvDir = Join-Path $Root ".stt-build-venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$script:BuildPython = $null

function Resolve-HostPython {
    if ($env:STT_PYTHON -and (Test-Path $env:STT_PYTHON)) {
        return (Resolve-Path $env:STT_PYTHON).Path
    }

    $candidates = @(
        (Join-Path $Root "python\python.exe"),
        (Join-Path $Root "python_embeded\python.exe")
    )

    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) {
            return (Resolve-Path $c).Path
        }
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd -and $pythonCmd.Source) {
        return $pythonCmd.Source
    }

    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        $exe = & py -3.11 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }

        $exe = & py -3 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
    }

    return $null
}

function Test-PythonUsable([string]$PythonExe) {
    if (-not $PythonExe -or -not (Test-Path $PythonExe)) {
        return $false
    }

    try {
        & $PythonExe -c "import pip" 1>$null 2>$null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

function Ensure-BuildPython {
    $runtime = Resolve-HostPython
    if (-not $runtime) {
        throw "Python runtime not found. Set STT_PYTHON to python.exe path and rerun. Example: `$env:STT_PYTHON='C:\Python311\python.exe'"
    }

    if (Test-Path $VenvPython) {
        if (Test-PythonUsable $VenvPython) {
            $script:BuildPython = (Resolve-Path $VenvPython).Path
            return
        }

        Write-Host "[WARN] Existing build venv is broken. Recreating..."
        Remove-Item -Recurse -Force $VenvDir -ErrorAction SilentlyContinue
    }

    Write-Host "[1/7] Creating build venv"
    try {
        & $runtime -m venv $VenvDir
    }
    catch {
        Write-Host "[WARN] venv creation failed. Falling back to host python."
    }

    if (Test-Path $VenvPython) {
        try {
            & $VenvPython -m ensurepip --upgrade 1>$null 2>$null
        }
        catch {
            # no-op
        }

        if (Test-PythonUsable $VenvPython) {
            $script:BuildPython = (Resolve-Path $VenvPython).Path
            return
        }

        Write-Host "[WARN] New venv is not usable. Falling back to host python."
    }

    if (-not (Test-PythonUsable $runtime)) {
        throw "Host python exists but pip is not usable. Please install/repair pip, then retry."
    }

    $script:BuildPython = $runtime
}

function Discover-FfmpegExe([string]$AppRoot) {
    $direct = Join-Path $AppRoot "ffmpeg\bin\ffmpeg.exe"
    if (Test-Path $direct) {
        return (Resolve-Path $direct).Path
    }

    $candidates = @()
    Get-ChildItem -Path $AppRoot -Directory -Filter "ffmpeg-*" -ErrorAction SilentlyContinue | ForEach-Object {
        $candidate = Join-Path $_.FullName "bin\ffmpeg.exe"
        if (Test-Path $candidate) {
            $candidates += (Get-Item $candidate)
        }
    }

    if ($candidates.Count -gt 0) {
        $picked = $candidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        return $picked.FullName
    }

    $cmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
        return $cmd.Source
    }

    return $null
}

function Test-FileSampleNonZero([string]$Path, [int64]$Offset, [int]$SampleSize) {
    $fs = [System.IO.File]::OpenRead($Path)
    try {
        $seekOffset = [int64]$Offset
        if ($seekOffset -lt 0) { $seekOffset = [int64]0 }
        $fs.Seek($seekOffset, [System.IO.SeekOrigin]::Begin) | Out-Null

        $buf = New-Object byte[] $SampleSize
        $read = $fs.Read($buf, 0, $SampleSize)
        if ($read -le 0) { return $false }

        for ($i = 0; $i -lt $read; $i++) {
            if ($buf[$i] -ne 0) { return $true }
        }
        return $false
    }
    finally {
        $fs.Close()
    }
}

function Test-ModelFile([string]$Path, [int64]$MinSizeBytes) {
    if (-not (Test-Path $Path)) {
        return @{ Ok = $false; Reason = "missing file" }
    }

    $item = Get-Item $Path
    if ($item.Length -lt $MinSizeBytes) {
        return @{ Ok = $false; Reason = "file too small" }
    }

    $sampleSize = 4096
    $middle = [int64]($item.Length / 2) - [int64]($sampleSize / 2)
    if ($middle -lt 0) { $middle = 0 }
    $tail = [int64]$item.Length - [int64]$sampleSize
    if ($tail -lt 0) { $tail = 0 }

    $checks = @(
        (Test-FileSampleNonZero $Path 0 $sampleSize),
        (Test-FileSampleNonZero $Path $middle $sampleSize),
        (Test-FileSampleNonZero $Path $tail $sampleSize)
    )

    if ($checks -contains $false) {
        return @{ Ok = $false; Reason = "zero-filled pattern" }
    }

    return @{ Ok = $true; Reason = "ok" }
}

Ensure-BuildPython

Write-Host "[2/7] Pre-validating ffmpeg and models"
$ffmpegExe = Discover-FfmpegExe $Root
if (-not $ffmpegExe) {
    throw "ffmpeg not found. Put ffmpeg under app root (ffmpeg or ffmpeg-*) and retry."
}

Write-Host "[3/7] Installing build dependencies"
& $script:BuildPython -m pip install --upgrade pip
& $script:BuildPython -m pip install -r requirements.txt pyinstaller

Write-Host "[4/7] Cleaning old build outputs"
Remove-Item -Recurse -Force (Join-Path $Root "build") -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $Root ("dist\" + $AppName)) -ErrorAction SilentlyContinue

Write-Host "[5/7] Building onedir app"
$addData = @(
    "ui;ui"
)

$ffmpegRoot = Split-Path -Parent (Split-Path -Parent $ffmpegExe)
if (-not (Test-Path (Join-Path $ffmpegRoot "bin\ffmpeg.exe"))) {
    throw "Invalid ffmpeg root for bundling: $ffmpegRoot"
}
$addData += "$ffmpegRoot;ffmpeg"

$pyiArgs = @(
    "--noconfirm",
    "--clean",
    "--onedir",
    "--windowed",
    "--name", $AppName,
    "--collect-all", "webview",
    "main.py"
)

foreach ($item in $addData) {
    $pyiArgs += "--add-data"
    $pyiArgs += $item
}

& $script:BuildPython -m PyInstaller @pyiArgs

Write-Host "[6/7] Building installer (Inno Setup)"
$iss = Join-Path $Root "installer.iss"
$appDist = Join-Path $Root ("dist\" + $AppName)

$innoCandidates = @(
    "$Env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$Env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$Env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$ISCC = $innoCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $ISCC) {
    $isccCmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($isccCmd -and $isccCmd.Source) {
        $ISCC = $isccCmd.Source
    }
}
if (-not $ISCC) {
    throw "Inno Setup 6 not found. Install Inno Setup and retry."
}

& $ISCC "/DMyAppName=$AppName" "/DMyAppVersion=$AppVersion" "/DMyAppDir=$appDist" $iss

Write-Host "[7/7] Done"
Write-Host "Installer output: dist\\installer"

