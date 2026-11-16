#define MyAppName "BankMorabianFardis"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "سازمان فرهنگی شهرداری فردیس"
[Setup]
AppId={{A94D5E35-88B4-4F6D-8B7A-BC8A5C4C9021}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\BankMorabianFardis
DefaultGroupName=بانک اطلاعات مربیان فردیس
OutputDir=dist
OutputBaseFilename=BankMorabianFardis-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\BankMorabianFardis.exe
[Files]
Source: "dist\BankMorabianFardis\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\بانک اطلاعات مربیان فردیس"; Filename: "{app}\BankMorabianFardis.exe"
Name: "{autodesktop}\بانک اطلاعات مربیان فردیس"; Filename: "{app}\BankMorabianFardis.exe"
[Run]
Filename: "{app}\BankMorabianFardis.exe"; Description: "اجرای بانک اطلاعات مربیان فردیس"; Flags: postinstall nowait skipifsilent
