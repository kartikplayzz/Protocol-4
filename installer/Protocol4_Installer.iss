; Inno Setup Script for Protocol-4 Maharashtra Police Legal Intelligence Studio
#define MyAppName "Protocol-4 Legal Intelligence Studio"
#define MyAppVersion "4.5.0"
#define MyAppPublisher "Protocol-4 Intelligence Engineering"
#define MyAppURL "https://github.com/kartikplayzz/Protocol-4"
#define MyAppExeName "Protocol4_Desktop.exe"

[Setup]
AppId={{9F821A83-7E5C-4B9F-83AA-7662F9C4A112}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\Protocol-4 Legal Intelligence
DisableProgramGroupPage=yes
LicenseFile=LICENSE
PrivilegesRequired=lowest
OutputDir=dist\installer
OutputBaseFilename=Protocol-4-Setup-v4.5
SetupIconFile=assets\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\Protocol4_Desktop\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Protocol4_Desktop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "Fast_Installer_Protocol.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "GUIDEBOOK.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\assets\icon.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
