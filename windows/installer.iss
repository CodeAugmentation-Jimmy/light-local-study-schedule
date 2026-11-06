#define AppName "学习日程"
#define AppVersion "1.2.3"

[Setup]
#ifdef IntegrationTest
AppId=StudyScheduleIntegrationTest_1_2_0
AppName=学习日程安装验证
UninstallDisplayName=学习日程安装验证
#else
AppId={{F0891BCD-B377-45A4-90CF-93E40BC991F9}
AppName={#AppName}
#endif
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
DefaultDirName={localappdata}\Programs\StudySchedule
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
#ifdef IntegrationTest
OutputDir=..\build\windows\installer-test
OutputBaseFilename=StudySchedule-TestSetup
#else
OutputDir=..\dist
OutputBaseFilename=StudySchedule-Setup-{#AppVersion}
#endif
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\StudySchedule.exe
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
AppMutex=Local\StudyScheduleDesktop
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: chinesesimplified; MessagesFile: languages\ChineseSimplified.isl

[Tasks]
Name: desktopicon; Description: 创建桌面快捷方式; GroupDescription: 快捷方式：

[Files]
Source: ..\build\windows\app\StudySchedule\*; DestDir: {app}; Flags: ignoreversion recursesubdirs createallsubdirs
Source: ..\电脑版安装说明.txt; DestDir: {app}; Flags: ignoreversion
Source: ..\安卓使用与同步说明.md; DestDir: {app}; Flags: ignoreversion
Source: Python-LICENSE.txt; DestDir: {app}; Flags: ignoreversion
Source: Tcl-LICENSE.txt; DestDir: {app}; Flags: ignoreversion
Source: Tk-LICENSE.txt; DestDir: {app}; Flags: ignoreversion
Source: THIRD_PARTY_NOTICES.txt; DestDir: {app}; Flags: ignoreversion

[Icons]
Name: {autoprograms}\{#AppName}; Filename: {app}\StudySchedule.exe
Name: {autodesktop}\{#AppName}; Filename: {app}\StudySchedule.exe; Tasks: desktopicon
Name: {autoprograms}\学习日程使用说明; Filename: {app}\电脑版安装说明.txt

[Run]
Filename: {app}\StudySchedule.exe; Description: 启动学习日程; Flags: nowait postinstall skipifsilent

[Code]
var
  LegacyPage: TInputDirWizardPage;
  ImportCheck: TNewCheckBox;

procedure ImportCheckClick(Sender: TObject);
begin
  LegacyPage.Edits[0].Enabled := ImportCheck.Checked;
  LegacyPage.Buttons[0].Enabled := ImportCheck.Checked;
end;

procedure InitializeWizard;
var
  Candidate: String;
begin
  LegacyPage := CreateInputDirPage(wpSelectDir, '导入旧版学习记录（可选）',
    '选择原来保存“日程程序.py”和“学习记录.json”的文件夹。',
    '记录和手机配对信息将复制到安装版的数据目录，原文件保留。安装版已有数据时不会导入或覆盖。', False, '');
  LegacyPage.Add('旧版程序文件夹：');
  ImportCheck := TNewCheckBox.Create(LegacyPage);
  ImportCheck.Parent := LegacyPage.Surface;
  ImportCheck.Caption := '导入已有的学习记录和配对信息';
  ImportCheck.Left := 0;
  ImportCheck.Top := LegacyPage.Buttons[0].Top + LegacyPage.Buttons[0].Height + ScaleY(16);
  ImportCheck.Width := LegacyPage.SurfaceWidth;
  ImportCheck.Height := ScaleY(24);
  ImportCheck.OnClick := @ImportCheckClick;
  Candidate := ExpandFileName(ExpandConstant('{src}\..'));
  if not FileExists(Candidate + '\学习记录.json') then Candidate := ExpandConstant('{src}');
  if FileExists(Candidate + '\学习记录.json') then
  begin
    LegacyPage.Values[0] := Candidate;
    ImportCheck.Checked := True;
  end;
  ImportCheckClick(ImportCheck);
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = LegacyPage.ID) and FileExists(ExpandConstant('{localappdata}\StudySchedule\学习记录.json'));
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = LegacyPage.ID) and ImportCheck.Checked then
    if not FileExists(LegacyPage.Values[0] + '\学习记录.json') then
    begin
      MsgBox('所选文件夹中没有“学习记录.json”，请重新选择，或者取消勾选导入。', mbError, MB_OK);
      Result := False;
    end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Code: Integer;
  Success: Boolean;
begin
  if (CurStep = ssPostInstall) and ImportCheck.Checked and (not WizardSilent) and
     (not FileExists(ExpandConstant('{localappdata}\StudySchedule\学习记录.json'))) then
  begin
    Success := Exec(ExpandConstant('{app}\StudySchedule.exe'),
      '--import-legacy "' + LegacyPage.Values[0] + '"', '', SW_HIDE, ewWaitUntilTerminated, Code);
    if (not Success) or (Code <> 0) then
      MsgBox('程序已经安装，但旧记录导入未完成。请保留旧版文件夹，勿删除原记录。可先从旧版与手机同步，再在安装版与手机同步来合并记录。', mbError, MB_OK);
  end;
end;
