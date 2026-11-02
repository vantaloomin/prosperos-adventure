; Per-user Windows installer for the self-contained bundle (scripts/package/build_bundle.py).
; Build: ISCC.exe /DAppVersion=<version> /DSourceDir=<unpacked ProsperoDungeon> /DOutputDir=<dir> dungeon.iss
; Installs into %LOCALAPPDATA%\Programs\Prospero Dungeon without administrator rights. The
; workspace in %LOCALAPPDATA%\ProsperoDungeon is never installed, replaced or removed here.

#ifndef AppVersion
  #error Pass /DAppVersion=<version>
#endif
#ifndef SourceDir
  #error Pass /DSourceDir=<unpacked bundle>
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif

[Setup]
; Fixed for every Dungeon release, and unrelated to Prospero's Study.
AppId={{82941F85-FF26-49CE-80BA-9B592D72162F}
AppName=Prospero Dungeon
AppVersion={#AppVersion}
AppVerName=Prospero Dungeon {#AppVersion}
AppPublisher=Prospero Dungeon
AppPublisherURL=https://github.com/vantaloomin/prosperos-dungeon
DefaultDirName={autopf}\Prospero Dungeon
DisableDirPage=auto
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=ProsperoDungeon-{#AppVersion}-win-x64-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=Prospero Dungeon
UninstallDisplayIcon={app}\runtime\python.exe
; A running Dungeon holds files in {app}; Restart Manager offers to close it first.
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[InstallDelete]
; An upgrade starts from clean program files, so modules removed in a release do not linger.
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\runtime"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Prospero Dungeon"; Filename: "{app}\runtime\python.exe"; Parameters: "-I -m dungeon.launch"; WorkingDir: "{app}"; Comment: "Start Prospero Dungeon"
Name: "{autodesktop}\Prospero Dungeon"; Filename: "{app}\runtime\python.exe"; Parameters: "-I -m dungeon.launch"; WorkingDir: "{app}"; Comment: "Start Prospero Dungeon"; Tasks: desktopicon

[Run]
Filename: "{app}\runtime\python.exe"; Parameters: "-I -m dungeon.launch"; WorkingDir: "{app}"; Description: "Start Prospero Dungeon"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Bytecode written at run time. The workspace and its backups stay where they are.
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\runtime"
