; Per-user Windows installer for the self-contained bundle (scripts/package/build_bundle.py).
; Build: ISCC.exe /DAppVersion=<version> /DSourceDir=<unpacked ProsperoAdventure> /DOutputDir=<dir> adventure.iss
; Installs into %LOCALAPPDATA%\Programs\Prospero Adventure without administrator rights. The
; workspace in %LOCALAPPDATA%\ProsperoAdventure is never installed, replaced or removed here.

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
; Fixed for every Adventure release, and unrelated to Prospero's Study.
AppId={{3F27ECCE-E3AF-4F43-8FCF-0262D666DA39}
AppName=Prospero Adventure
AppVersion={#AppVersion}
AppVerName=Prospero Adventure {#AppVersion}
AppPublisher=Prospero Adventure
AppPublisherURL=https://github.com/vantaloomin/prosperos-adventure
DefaultDirName={autopf}\Prospero Adventure
DisableDirPage=auto
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=ProsperoAdventure-{#AppVersion}-win-x64-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=Prospero Adventure
UninstallDisplayIcon={app}\runtime\python.exe
; A running Adventure holds files in {app}; Restart Manager offers to close it first.
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
Name: "{autoprograms}\Prospero Adventure"; Filename: "{app}\runtime\python.exe"; Parameters: "-I -m adventure.launch"; WorkingDir: "{app}"; Comment: "Start Prospero Adventure"
Name: "{autodesktop}\Prospero Adventure"; Filename: "{app}\runtime\python.exe"; Parameters: "-I -m adventure.launch"; WorkingDir: "{app}"; Comment: "Start Prospero Adventure"; Tasks: desktopicon

[Run]
Filename: "{app}\runtime\python.exe"; Parameters: "-I -m adventure.launch"; WorkingDir: "{app}"; Description: "Start Prospero Adventure"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Bytecode written at run time. The workspace and its backups stay where they are.
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\runtime"
