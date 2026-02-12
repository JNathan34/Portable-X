; PortableX installer
#define MyAppName "PortableX"
#define MyAppVersion "1.5"
#define MyAppPublisher "PortableX"
#define MyAppExeName "PortableX.exe"

[Setup]
AppId={{C9A26D5E-6A0F-4E2D-9F30-6B6B4D04B9A3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={src}
DefaultGroupName={#MyAppName}
DisableDirPage=no
UsePreviousAppDir=no
AppendDefaultDirName=no
AllowRootDirectory=yes
DirExistsWarning=no
DisableProgramGroupPage=yes
OutputBaseFilename=Portable X Installer
OutputDir=dist
SetupIconFile=install.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
WizardImageFile=wizard-large.png
WizardSmallImageFile=wizard-small.png
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "dist\PortableX\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
Source: "icon.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "PortableApps\*"; DestDir: "{app}\PortableApps"; Flags: recursesubdirs createallsubdirs; Excludes: "PortableX\Data\_tmp\*;PortableX\Data\tmp\*"
Source: "folder icons\*"; DestDir: "{app}\PortableApps\PortableX\folder icons"; Flags: recursesubdirs createallsubdirs
Source: "PortableApps\PortableX\Graphics\browsericons\brave.png"; Flags: dontcopy
Source: "PortableApps\PortableX\Graphics\browsericons\chrome.png"; Flags: dontcopy
Source: "PortableApps\PortableX\Graphics\browsericons\edge.png"; Flags: dontcopy
Source: "PortableApps\PortableX\Graphics\browsericons\firefox.png"; Flags: dontcopy
Source: "PortableApps\PortableX\Graphics\browsericons\opera.png"; Flags: dontcopy
Source: "PortableApps\PortableX\Graphics\browsericons\operagx.png"; Flags: dontcopy

[Dirs]
Name: "{app}\PortableApps\PortableX\Data"
Name: "{app}\Videos"
Name: "{app}\Pictures"
Name: "{app}\Music"
Name: "{app}\Downloads"
Name: "{app}\documents"

[INI]
FileName: "{app}\Videos\desktop.ini"; Section: ".ShellClassInfo"; Key: "IconResource"; String: "..\PortableApps\PortableX\folder icons\videos.ico,0"
FileName: "{app}\Videos\desktop.ini"; Section: ".ShellClassInfo"; Key: "IconFile"; String: "..\PortableApps\PortableX\folder icons\videos.ico"
FileName: "{app}\Videos\desktop.ini"; Section: ".ShellClassInfo"; Key: "IconIndex"; String: "0"
FileName: "{app}\Pictures\desktop.ini"; Section: ".ShellClassInfo"; Key: "IconResource"; String: "..\PortableApps\PortableX\folder icons\pictures.ico,0"
FileName: "{app}\Pictures\desktop.ini"; Section: ".ShellClassInfo"; Key: "IconFile"; String: "..\PortableApps\PortableX\folder icons\pictures.ico"
FileName: "{app}\Pictures\desktop.ini"; Section: ".ShellClassInfo"; Key: "IconIndex"; String: "0"
FileName: "{app}\Music\desktop.ini"; Section: ".ShellClassInfo"; Key: "IconResource"; String: "..\PortableApps\PortableX\folder icons\music.ico,0"
FileName: "{app}\Music\desktop.ini"; Section: ".ShellClassInfo"; Key: "IconFile"; String: "..\PortableApps\PortableX\folder icons\music.ico"
FileName: "{app}\Music\desktop.ini"; Section: ".ShellClassInfo"; Key: "IconIndex"; String: "0"
FileName: "{app}\Downloads\desktop.ini"; Section: ".ShellClassInfo"; Key: "IconResource"; String: "..\PortableApps\PortableX\folder icons\downloads.ico,0"
FileName: "{app}\Downloads\desktop.ini"; Section: ".ShellClassInfo"; Key: "IconFile"; String: "..\PortableApps\PortableX\folder icons\downloads.ico"
FileName: "{app}\Downloads\desktop.ini"; Section: ".ShellClassInfo"; Key: "IconIndex"; String: "0"
FileName: "{app}\documents\desktop.ini"; Section: ".ShellClassInfo"; Key: "IconResource"; String: "..\PortableApps\PortableX\folder icons\documents.ico,0"
FileName: "{app}\documents\desktop.ini"; Section: ".ShellClassInfo"; Key: "IconFile"; String: "..\PortableApps\PortableX\folder icons\documents.ico"
FileName: "{app}\documents\desktop.ini"; Section: ".ShellClassInfo"; Key: "IconIndex"; String: "0"

[Run]
Filename: "{cmd}"; Parameters: "/c attrib +r ""{app}\Videos"""; Flags: runhidden
Filename: "{cmd}"; Parameters: "/c attrib +r ""{app}\Pictures"""; Flags: runhidden
Filename: "{cmd}"; Parameters: "/c attrib +r ""{app}\Music"""; Flags: runhidden
Filename: "{cmd}"; Parameters: "/c attrib +r ""{app}\Downloads"""; Flags: runhidden
Filename: "{cmd}"; Parameters: "/c attrib +r ""{app}\documents"""; Flags: runhidden
Filename: "{cmd}"; Parameters: "/c attrib +s +h ""{app}\Videos\desktop.ini"""; Flags: runhidden
Filename: "{cmd}"; Parameters: "/c attrib +s +h ""{app}\Pictures\desktop.ini"""; Flags: runhidden
Filename: "{cmd}"; Parameters: "/c attrib +s +h ""{app}\Music\desktop.ini"""; Flags: runhidden
Filename: "{cmd}"; Parameters: "/c attrib +s +h ""{app}\Downloads\desktop.ini"""; Flags: runhidden
Filename: "{cmd}"; Parameters: "/c attrib +s +h ""{app}\documents\desktop.ini"""; Flags: runhidden
Filename: "{cmd}"; Parameters: "/c attrib +h ""{app}\unins000.exe"""; Flags: runhidden
Filename: "{cmd}"; Parameters: "/c attrib +h ""{app}\unins000.dat"""; Flags: runhidden
Filename: "{cmd}"; Parameters: "/c attrib +h ""{app}\icon.png"""; Flags: runhidden
Filename: "{app}\PortableX.exe"; Parameters: "--show-notice"; Description: "Open Portable X"; Flags: postinstall nowait skipifsilent
Filename: "{cmd}"; Parameters: "/c start """" /min cmd /c ""ping 127.0.0.1 -n 6 >nul & del /f /q """"{srcexe}"""""""; Description: "Delete installer after finish"; Flags: postinstall unchecked skipifsilent runhidden nowait

[Code]
var
  BrowserPage: TWizardPage;
  BrowserRadios: array of TRadioButton;
  BrowserIcons: array of TBitmapImage;

function URLDownloadToFile(Caller: Integer; URL: string; FileName: string; Reserved: Integer; StatusCB: Integer): Integer;
  external 'URLDownloadToFileW@urlmon.dll stdcall';

function GetBrowserChoiceIndex: Integer;
var
  i: Integer;
begin
  Result := 0;
  for i := 0 to GetArrayLength(BrowserRadios) - 1 do begin
    if BrowserRadios[i].Checked then begin
      Result := i;
      Exit;
    end;
  end;
end;

function BrowserLabel(Index: Integer): string;
begin
  case Index of
    0: Result := 'System default';
    1: Result := 'Microsoft Edge';
    2: Result := 'Chrome Portable';
    3: Result := 'Firefox Portable';
    4: Result := 'Opera Portable';
    5: Result := 'Opera GX Portable';
    6: Result := 'Brave Portable';
  else
    Result := '';
  end;
end;

function BrowserIconFile(Index: Integer): string;
begin
  case Index of
    1: Result := 'edge.png';
    2: Result := 'chrome.png';
    3: Result := 'firefox.png';
    4: Result := 'opera.png';
    5: Result := 'operagx.png';
    6: Result := 'brave.png';
  else
    Result := '';
  end;
end;

function BrowserDownloadUrl(Index: Integer): string;
begin
  case Index of
    2: Result := 'https://download2.portableapps.com/portableapps/GoogleChromePortable/GoogleChromePortable_144.0.7559.133_online.paf.exe';
    3: Result := 'https://download2.portableapps.com/portableapps/FirefoxPortable/FirefoxPortable_147.0.3_English.paf.exe';
    4: Result := 'https://download2.portableapps.com/portableapps/OperaPortable/OperaPortable_127.0.5778.14.paf.exe';
    5: Result := 'https://download2.portableapps.com/portableapps/OperaGXPortable/OperaGXPortable_126.0.5750.112.paf.exe';
    6: Result := 'https://github.com/portapps/brave-portable/releases/download/1.85.118-98/brave-portable-win64-1.85.118-98-setup.exe';
  else
    Result := '';
  end;
end;

function DownloadFile(const Url, Dest: string): Boolean;
var
  hr: Integer;
begin
  Result := False;
  if (Url = '') or (Dest = '') then
    Exit;
  if FileExists(Dest) then
    DeleteFile(Dest);
  hr := URLDownloadToFile(0, Url, Dest, 0, 0);
  Result := hr = 0;
end;

function DownloadBrowserInstaller(Index: Integer; var DestPath: string): Boolean;
var
  url: string;
  name: string;
begin
  Result := False;
  url := BrowserDownloadUrl(Index);
  if url = '' then
    Exit;
  name := ExtractFileName(url);
  if name = '' then
    name := 'browser-installer.exe';
  DestPath := ExpandConstant('{tmp}\') + name;
  Result := DownloadFile(url, DestPath);
end;

procedure CopyDir(const SourceDir, DestDir: string);
var
  FindRec: TFindRec;
begin
  if not DirExists(SourceDir) then
    Exit;

  ForceDirectories(DestDir);

  if FindFirst(SourceDir + '\*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
            CopyDir(SourceDir + '\' + FindRec.Name, DestDir + '\' + FindRec.Name)
          else
            FileCopy(SourceDir + '\' + FindRec.Name, DestDir + '\' + FindRec.Name, False);
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

procedure FinalizeBraveInstall;
var
  srcDir: string;
  dstDir: string;
  appInfoSrc: string;
  appInfoDst: string;
begin
  srcDir := ExpandConstant('{app}\PortableApps\brave-portable');
  dstDir := ExpandConstant('{app}\PortableApps\BravePortable');

  if DirExists(srcDir) and not DirExists(dstDir) then
    RenameFile(srcDir, dstDir);

  if DirExists(dstDir) then begin
  appInfoSrc := ExpandConstant('{app}\PortableApps\PortableX\Data\brave appinfo\appinfo');
  if not DirExists(appInfoSrc) then
    appInfoSrc := ExpandConstant('{app}\brave appinfo\appinfo');
    appInfoDst := ExpandConstant('{app}\PortableApps\BravePortable\app\appinfo');
    if DirExists(appInfoSrc) then
      CopyDir(appInfoSrc, appInfoDst);
  end;
end;


procedure InitializeWizard;
var
  i: Integer;
  top: Integer;
  iconFile: string;
begin
  BrowserPage := CreateCustomPage(wpSelectDir,
    'Default Browser',
    'Select the browser PortableX should use for web links.');

  SetArrayLength(BrowserRadios, 7);
  SetArrayLength(BrowserIcons, 7);

  for i := 0 to 6 do begin
    top := ScaleY(4) + i * ScaleY(24);

    iconFile := BrowserIconFile(i);
    if iconFile <> '' then begin
      ExtractTemporaryFile(iconFile);
      BrowserIcons[i] := TBitmapImage.Create(BrowserPage);
      BrowserIcons[i].Parent := BrowserPage.Surface;
      BrowserIcons[i].Left := ScaleX(4);
      BrowserIcons[i].Top := top + ScaleY(2);
      BrowserIcons[i].Width := ScaleX(16);
      BrowserIcons[i].Height := ScaleY(16);
      BrowserIcons[i].Stretch := True;
      BrowserIcons[i].PngImage.LoadFromFile(AddBackslash(ExpandConstant('{tmp}')) + iconFile);
    end else begin
      BrowserIcons[i] := nil;
    end;

    BrowserRadios[i] := TRadioButton.Create(BrowserPage);
    BrowserRadios[i].Parent := BrowserPage.Surface;
    BrowserRadios[i].Caption := BrowserLabel(i);
    BrowserRadios[i].Left := ScaleX(26);
    BrowserRadios[i].Top := top;
    BrowserRadios[i].Width := BrowserPage.SurfaceWidth - BrowserRadios[i].Left;
    BrowserRadios[i].Anchors := [akLeft, akTop, akRight];
    BrowserRadios[i].TabOrder := i;
  end;

  BrowserRadios[0].Checked := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  IniPath: string;
  Choice: Integer;
  BrowserChoice: string;
  BrowserPath: string;
  Response: Integer;
  ResultCode: Integer;
  InstallerPath: string;
begin
  if CurStep = ssInstall then begin
    IniPath := ExpandConstant('{app}\PortableApps\PortableX\Data\settings.ini');
    Choice := GetBrowserChoiceIndex;
    BrowserChoice := 'system';
    BrowserPath := '';

    case Choice of
      0: begin BrowserChoice := 'system'; BrowserPath := ''; end;
      1: begin BrowserChoice := 'edge'; BrowserPath := ''; end;
      2: begin BrowserChoice := 'chrome'; BrowserPath := 'PortableApps/GoogleChromePortable/GoogleChromePortable.exe'; end;
      3: begin BrowserChoice := 'firefox'; BrowserPath := 'PortableApps/FirefoxPortable/FirefoxPortable.exe'; end;
      4: begin BrowserChoice := 'opera'; BrowserPath := 'PortableApps/OperaPortable/OperaPortable.exe'; end;
      5: begin BrowserChoice := 'operagx'; BrowserPath := 'PortableApps/OperaGXPortable/OperaGXPortable.exe'; end;
      6: begin BrowserChoice := 'brave'; BrowserPath := 'PortableApps/BravePortable/brave-portable.exe'; end;
    end;

    SetIniString('Settings', 'BrowserChoice', BrowserChoice, IniPath);
    if BrowserPath = '' then
      DeleteIniEntry('Settings', 'BrowserPath', IniPath)
    else
      SetIniString('Settings', 'BrowserPath', BrowserPath, IniPath);
  end;

  if CurStep = ssPostInstall then begin
    Choice := GetBrowserChoiceIndex;
    if Choice >= 2 then begin
      Response := MsgBox('Install the selected browser now? This will download it from the internet.', mbConfirmation, MB_YESNO);
      if Response = IDYES then begin
        if not DownloadBrowserInstaller(Choice, InstallerPath) then begin
          MsgBox('Download failed. Please check your internet connection and try again.', mbError, MB_OK);
          Exit;
        end;
        if Choice = 6 then begin
          if Exec(InstallerPath, '', '', SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode) then
            FinalizeBraveInstall;
        end else begin
          Exec(InstallerPath, '', '', SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode);
        end;
        if FileExists(InstallerPath) then
          DeleteFile(InstallerPath);
      end;
    end;
  end;
end;
