; Inno Setup script for QLC+ Stage Monitor (Windows), the companion app of QLC Swiss Knife.
; Build:  ISCC /DAppVersion=3.20.1 packaging\windows\stagemonitor.iss   (after pyinstaller packaging/stagemonitor.spec)
; Per-user install (no administrator), in %LOCALAPPDATA%\Programs\QLC Stage Monitor,
; which is where Swiss Knife looks for it (core/companion.py).
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{9A4AC018-6CC3-4AAA-9718-022F59215461}
AppName=QLC+ Stage Monitor
AppVersion={#AppVersion}
AppPublisher=giopas
AppPublisherURL=https://github.com/giopas/qlc-plus-swiss-knife-tool-script
AppSupportURL=https://github.com/giopas/qlc-plus-swiss-knife-tool-script/issues
DefaultDirName={autopf}\QLC Stage Monitor
DefaultGroupName=QLC+ Stage Monitor
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\release
OutputBaseFilename=QLC-Stage-Monitor-{#AppVersion}-windows-x64-setup
SetupIconFile=..\icons\stage-monitor.ico
UninstallDisplayIcon={app}\QLC Stage Monitor.exe
LicenseFile=..\..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked

[Files]
Source: "..\..\dist\QLC Stage Monitor\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\QLC+ Stage Monitor"; Filename: "{app}\QLC Stage Monitor.exe"
Name: "{autodesktop}\QLC+ Stage Monitor"; Filename: "{app}\QLC Stage Monitor.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\QLC Stage Monitor.exe"; Description: "Start QLC+ Stage Monitor"; Flags: nowait postinstall skipifsilent
