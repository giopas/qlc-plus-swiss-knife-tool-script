; Inno Setup script for QLC Swiss Knife (Windows).
; Build:  ISCC /DAppVersion=2.9.1 packaging\windows\installer.iss   (after pyinstaller)
; Per-user install (no administrator): the app folder stays writable, so
; "Update and restart" inside the app keeps working.
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{1072CA33-233E-4F56-9F17-2987DFD56AFE}
AppName=QLC Swiss Knife
AppVersion={#AppVersion}
AppPublisher=giopas
AppPublisherURL=https://github.com/giopas/qlc-plus-swiss-knife-tool-script
AppSupportURL=https://github.com/giopas/qlc-plus-swiss-knife-tool-script/issues
DefaultDirName={autopf}\QLC Swiss Knife
DefaultGroupName=QLC Swiss Knife
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\release
OutputBaseFilename=QLC-Swiss-Knife-{#AppVersion}-windows-x64-setup
SetupIconFile=..\icons\icon.ico
UninstallDisplayIcon={app}\QLC Swiss Knife.exe
LicenseFile=..\..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked

[Files]
Source: "..\..\dist\QLC Swiss Knife\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\QLC Swiss Knife"; Filename: "{app}\QLC Swiss Knife.exe"
Name: "{autodesktop}\QLC Swiss Knife"; Filename: "{app}\QLC Swiss Knife.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\QLC Swiss Knife.exe"; Description: "Start QLC Swiss Knife"; Flags: nowait postinstall skipifsilent
