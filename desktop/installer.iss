; DOE-RSM のWindows用インストーラー（Inno Setup）。.github/workflows/build-windows.yml から
;   iscc /DAppVersion=0.3.0 /DSourceDir=<アプリのフォルダ> /DOutputDir=<出力先> desktop\installer.iss
; で作る。管理者権限なしで、ユーザーごとに %LOCALAPPDATA%\Programs\DOE-RSM に入れる。

[Setup]
AppId={{8B4D2F1E-7C3A-4E5B-9A61-2D8F0C7E5B13}
AppName=DOE-RSM
AppVersion={#AppVersion}
AppVerName=DOE-RSM {#AppVersion}
AppPublisher=DOE-RSM
DefaultDirName={localappdata}\Programs\DOE-RSM
DefaultGroupName=DOE-RSM
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=DOE-RSM-Setup-{#AppVersion}
SetupIconFile={#SourceDir}\DOE-RSM.ico
UninstallDisplayIcon={app}\DOE-RSM.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; 更新時に古い部品が残らないよう、同梱のPythonは入れ直す
Type: filesandordirs; Name: "{app}\python"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\DOE-RSM"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\DOE-RSM.pyw"""; WorkingDir: "{userdocs}"; IconFilename: "{app}\DOE-RSM.ico"
Name: "{autodesktop}\DOE-RSM"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\DOE-RSM.pyw"""; WorkingDir: "{userdocs}"; IconFilename: "{app}\DOE-RSM.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\DOE-RSM.pyw"""; Description: "{cm:LaunchProgram,DOE-RSM}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
