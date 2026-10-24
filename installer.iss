; IN-code Windows 安装包脚本（Inno Setup 6）
; 先运行 python build.py 生成 dist\IN-code，再执行本脚本

#define APP_NAME "IN-code"
#define APP_VERSION "1.0"
#define SRC_DIR "dist\IN-code"
#define OUT_DIR "installer"

[Setup]
AppName={#APP_NAME}
AppVersion={#APP_VERSION}
AppPublisher=IN-code
DefaultDirName={autopf}\IN-code
DefaultGroupName={#APP_NAME}
OutputDir={#OUT_DIR}
OutputBaseFilename=IN-code-Setup-{#APP_VERSION}
Compression=lzma2/normal
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
; 模型约4.7GB，超过单文件4.2GB上限，开启分卷（每片2GB，兼容FAT32）
DiskSpanning=yes
DiskSliceSize=2000000000
SlicesPerDisk=1

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："

[Files]
; 打包产物整体安装（含 runtime\llama 引擎、models\GGUF 模型、assets 资源）
Source: "{#SRC_DIR}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#APP_NAME}"; Filename: "{app}\IN-code.exe"
Name: "{autodesktop}\{#APP_NAME}"; Filename: "{app}\IN-code.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\IN-code.exe"; Description: "立即运行 {#APP_NAME}"; Flags: nowait postinstall skipifsilent
