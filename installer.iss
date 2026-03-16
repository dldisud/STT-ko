#ifndef MyAppName
#define MyAppName "KoreanSTT"
#endif

#ifndef MyAppVersion
#define MyAppVersion "1.0.0"
#endif

#ifndef MyAppDir
#define MyAppDir "dist\\KoreanSTT"
#endif

[Setup]
AppId={{8E9F8DA4-21AB-433F-A95C-C57A2C5D7437}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Korean STT
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=dist\installer
OutputBaseFilename={#MyAppName}_Setup_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "{#MyAppDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "INSTALL_NOTICE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppName}.exe"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppName}.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppName}.exe"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
