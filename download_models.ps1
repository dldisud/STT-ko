param()

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$VenvDir = Join-Path $Root ".stt-tools-venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$script:RunPython = $null

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

function Ensure-Python {
    $runtime = Resolve-HostPython
    if (-not $runtime) {
        throw "Python runtime not found. Set STT_PYTHON to python.exe path and rerun."
    }

    if (Test-Path $VenvPython) {
        if (Test-PythonUsable $VenvPython) {
            $script:RunPython = (Resolve-Path $VenvPython).Path
            return
        }

        Write-Host "[WARN] Existing tools venv is broken. Recreating..."
        Remove-Item -Recurse -Force $VenvDir -ErrorAction SilentlyContinue
    }

    Write-Host "[1/4] Prepare Python"
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
            $script:RunPython = (Resolve-Path $VenvPython).Path
            return
        }

        Write-Host "[WARN] New venv is not usable. Falling back to host python."
    }

    if (-not (Test-PythonUsable $runtime)) {
        throw "Host python exists but pip is not usable. Please install/repair pip, then retry."
    }

    $script:RunPython = $runtime
}

function Get-PythonScriptsDir([string]$PythonExe) {
    $parent = Split-Path -Parent $PythonExe
    if ((Split-Path $parent -Leaf).ToLower() -eq "scripts") {
        return $parent
    }

    $scripts = Join-Path $parent "Scripts"
    if (Test-Path $scripts) {
        return $scripts
    }

    return $parent
}

function Invoke-HFDownload([string]$RepoId, [string]$LocalDir) {
    $scriptsDir = Get-PythonScriptsDir $script:RunPython
    $hfExe = Join-Path $scriptsDir "hf.exe"
    $hfCliExe = Join-Path $scriptsDir "huggingface-cli.exe"

    if (Test-Path $hfExe) {
        & $hfExe download $RepoId --local-dir $LocalDir
        return $LASTEXITCODE
    }

    if (Test-Path $hfCliExe) {
        & $hfCliExe download $RepoId --local-dir $LocalDir
        return $LASTEXITCODE
    }

    $tmpPy = Join-Path $Root "_hf_snapshot_download.py"
    $pyCode = @"
from huggingface_hub import snapshot_download
import sys

repo_id = sys.argv[1]
local_dir = sys.argv[2]

snapshot_download(
    repo_id=repo_id,
    local_dir=local_dir,
    )
"@
    Set-Content -Encoding utf8 $tmpPy $pyCode

    try {
        & $script:RunPython $tmpPy $RepoId $LocalDir
        return $LASTEXITCODE
    }
    finally {
        Remove-Item $tmpPy -Force -ErrorAction SilentlyContinue
    }
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

function Validate-Moonshine([string]$Dir) {
    $result = Test-ModelFile (Join-Path $Dir "model.safetensors") 50000000
    return $result
}

function Validate-Qwen([string]$Dir) {
    $r1 = Test-ModelFile (Join-Path $Dir "model-00001-of-00002.safetensors") 3000000000
    if (-not $r1.Ok) { return @{ Ok = $false; Reason = "shard1: $($r1.Reason)" } }

    $r2 = Test-ModelFile (Join-Path $Dir "model-00002-of-00002.safetensors") 300000000
    if (-not $r2.Ok) { return @{ Ok = $false; Reason = "shard2: $($r2.Reason)" } }

    return @{ Ok = $true; Reason = "ok" }
}

function Download-Model([string]$RepoId, [string]$TargetDir, [scriptblock]$Validator) {
    $targetName = Split-Path $TargetDir -Leaf
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $tmpRoot = Join-Path $Root "_download_tmp"
    $tmpDir = Join-Path $tmpRoot ("$targetName`_$timestamp")
    $backupDir = "${TargetDir}_backup_$timestamp"

    New-Item -ItemType Directory -Force $tmpRoot | Out-Null

    Write-Host "Downloading $RepoId ..."
    $rc = Invoke-HFDownload $RepoId $tmpDir

    $check = & $Validator $tmpDir
    if (-not $check.Ok) {
        Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue
        if ($rc -ne 0) {
            throw "Download failed for ${RepoId} (exit code: $rc)"
        }
        throw "Downloaded model is invalid for ${RepoId}: $($check.Reason)"
    }

    if ($rc -ne 0) {
        Write-Warning "Downloader returned non-zero exit code ($rc), but model files passed integrity checks. Continuing."
    }

    $targetExists = Test-Path $TargetDir
    try {
        if ($targetExists) {
            Move-Item $TargetDir $backupDir -Force
        }

        Move-Item $tmpDir $TargetDir -Force

        $finalCheck = & $Validator $TargetDir
        if (-not $finalCheck.Ok) {
            throw "Final model check failed after move: $($finalCheck.Reason)"
        }

        if (Test-Path $backupDir) {
            Remove-Item -Recurse -Force $backupDir
        }
    }
    catch {
        if (Test-Path $TargetDir) {
            Remove-Item -Recurse -Force $TargetDir -ErrorAction SilentlyContinue
        }
        if (Test-Path $backupDir) {
            Move-Item $backupDir $TargetDir -Force
        }
        throw
    }
}

Ensure-Python

Write-Host "[2/4] Install huggingface hub"
& $script:RunPython -m pip install --upgrade pip
& $script:RunPython -m pip install "huggingface_hub>=0.31.0"

Write-Host "[3/4] Download models"
Download-Model "UsefulSensors/moonshine-tiny-ko" (Join-Path $Root "moonshine-tiny-ko") ${function:Validate-Moonshine}
Download-Model "Qwen/Qwen3-ASR-1.7B" (Join-Path $Root "Qwen3-ASR-1.7B") ${function:Validate-Qwen}

Write-Host "[4/4] Completed"
Write-Host "Models are verified and ready."


