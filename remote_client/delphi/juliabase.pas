unit juliabase;

(*
=======================================================================================

  Delphi Wrapper für den Chantal Remote-Client

  Diese Unit bietet nur eine einzige Funktion an, nämlich execute_jb.  Diese
  Funktion erhält drei Strings als Parameter, nämlich den Loginnamen, das
  Paßwort, und den Befehlsstring.  Um beispielsweise eine eine neue Probe
  anzulegen, kann man aufrufen:

      execute_jb('b.bunny', 'bugspasswort', 'new_samples(1, u"Peters Büro")');

  Es gibt auch noch einen vierten, optionalen Parameter, der boolsch ist.  Ist
  er True, wird der Befehlsstring auf dem Testserver ausgeführt.  Per Default
  ist er False, so daß der Befehlsstring mit der richtigen Datenbank ausgeführt
  wird.

  Außerdem bietet diese Unit drei globale Variablen, mit denen man
  Einstellungen vornehmen kann:

      package_path enthält den Pfad zum Python-Package des Remote-Clients
      python_path enthält den Pfad zum Python-Interpreter
      open_error_page_in_browser ist per Default False.  Wenn es True ist, wird
        im Fehlerfall, d.h. wenn ein Webformular falsch oder unvollständig
        ausgefüllt wurde, automatisch im Browser geöffnet.

=======================================================================================
*)

interface

uses SysUtils;

type
  EJuliaBaseError = class(Exception)
  public
    ErrorCode: integer;
    constructor Create(ErrorCode:integer; message_:string; testserver:boolean);
  end;

var
  package_path, module, python_path:String;
  open_error_page_in_browser: boolean;

function execute_jb(const login, password, commands: String; testserver:boolean=false): String;

implementation

uses Windows, ShellAPI;

// Entnommen aus http://www.delphi-forum.de/topic_ConsolenOutput+in+Memo+pipen+UND+in+Konsole_98927,0.html

function ExecConsoleCommand(const ACommand, AInput: String; var AOutput, AErrors: String;
                            var AExitCode: Cardinal): Boolean;
  var
    dw: dword;
    StartupInfo: TStartupInfo;
    ProcessInfo: TProcessInformation;
    SecurityAttr: TSecurityAttributes;
    PipeInputRead, PipeInputWrite,
    PipeOutputRead, PipeOutputWrite,
    PipeErrorsRead, PipeErrorsWrite: THandle;

  // Pipe in einen String auslesen
  procedure ReadPipeToString(const hPipe: THandle; var Result: String);
    var
      AvailableBytes,
      ReadBytes: Cardinal;
      Buffer: String;
  begin
    PeekNamedPipe(hPipe, NIL, 0, NIL, @AvailableBytes, NIL); // wieviel ist da
    while (AvailableBytes > 0) do begin // überhaupt was da?
      SetLength(Buffer,AvailableBytes); // Buffer
      if ReadFile(hPipe,PChar(Buffer)^,AvailableBytes,ReadBytes,NIL) then // Lesen hat geklappt
        if (ReadBytes > 0) then begin // Daten angekommen?
          SetLength(Buffer,ReadBytes); // falls weniger kam, als da ist (warum auch immer)
          Result := Result +Buffer; // an den Ergebnis-String
        end;
      PeekNamedPipe(hPipe, NIL, 0, NIL, @AvailableBytes, NIL); // noch was da?
    end;
  end;

begin
  AOutput := '';
  AErrors := '';
  // Win-API-Strukturen initialisieren/füllen
  FillChar(ProcessInfo,SizeOf(TProcessInformation),0);
  FillChar(SecurityAttr,SizeOf(TSecurityAttributes),0);
  SecurityAttr.nLength := SizeOf(SecurityAttr);
  SecurityAttr.bInheritHandle := TRUE;
  SecurityAttr.lpSecurityDescriptor := NIL;
  CreatePipe(PipeInputRead,PipeInputWrite,@SecurityAttr,0);
  CreatePipe(PipeOutputRead,PipeOutputWrite,@SecurityAttr,0);
  CreatePipe(PipeErrorsRead,PipeErrorsWrite,@SecurityAttr,0);
  FillChar(StartupInfo,SizeOf(TStartupInfo),0);
  StartupInfo.cb := SizeOf(StartupInfo);
  StartupInfo.hStdInput := PipeInputRead;
  StartupInfo.hStdOutput := PipeOutputWrite;
  StartupInfo.hStdError := PipeErrorsWrite;
  StartupInfo.wShowWindow := SW_HIDE;
  StartupInfo.dwFlags := STARTF_USESHOWWINDOW or STARTF_USESTDHANDLES;
  // msdn2.microsoft.com/...ibrary/ms682425.aspx
  Result := CreateProcess(NIL,PChar(ACommand),NIL,NIL,TRUE,
                          CREATE_DEFAULT_ERROR_MODE
                          or CREATE_NEW_CONSOLE
                          or NORMAL_PRIORITY_CLASS,
                          NIL,NIL,StartupInfo,ProcessInfo);
  WriteFile(PipeInputWrite, AInput[1], length(AInput), dw, nil);
  if Result then begin // Prozess erfolgreich gestartet?
    repeat
      GetExitCodeProcess(ProcessInfo.hProcess,AExitCode); // msdn2.microsoft.com/...ibrary/ms683189.aspx
      ReadPipeToString(PipeOutputRead,AOutput); // Ausgaben lesen
      ReadPipeToString(PipeErrorsRead,AErrors); // Fehler lesen
      if (AExitCode = STILL_ACTIVE) then
        Sleep(1);
    until (AExitCode <> STILL_ACTIVE); // bis der Prozess sich selbst beendet hat
    CloseHandle(ProcessInfo.hThread); // Handles freigeben
    CloseHandle(ProcessInfo.hProcess);
  end;
  CloseHandle(PipeOutputWrite); // Pipes schließen
  CloseHandle(PipeErrorsWrite);
  CloseHandle(PipeOutputRead);
  CloseHandle(PipeErrorsRead);
end;

constructor EJuliaBaseError.Create(ErrorCode:integer; message_:string; testserver:boolean);
var
  url: String;
  closing_brace: Integer;
begin
  inherited Create(message_);
  self.ErrorCode := ErrorCode;
  if open_error_page_in_browser and (ErrorCode = 1) then
  begin
    closing_brace := Pos(')', message_);
    url := copy(message_, closing_brace + 2, length(message_) - closing_brace - 1);
    ShellExecute(0, 'open', PChar(url), nil, nil, SW_SHOWNORMAL)
  end
end;
  
function execute_jb(const login, password, commands: String; testserver:boolean=false): String;
const
  juliabase_exception_prefix = 'jb_remote.common.JuliaBaseError: ';
var
  output, errors, full_input, testserver_string, last_line: String;
  exit_code: Cardinal;
  line_ending, closing_brace: integer;
begin
  if testserver then testserver_string := 'True' else testserver_string := 'False';
  full_input := format('# -*- coding: utf-8 -*-'#13#10'import sys; sys.path.append("%s");from %s import *;' +
                       'login("%s", "%s", testserver=%s);%s;logout()'#26,
		       [package_path, module, login, password, testserver_string, commands]);
  if not ExecConsoleCommand(python_path, utf8encode(full_input), output, errors, exit_code) then
  begin
    raise Exception.Create('error: Could not start ' + python_path)
  end;
  if errors <> '' then
  begin
    last_line := copy(errors, 1, length(errors) - 2);
    repeat
      line_ending := Pos(''#13#10, last_line);
      if line_ending <> 0 then delete(last_line, 1, line_ending + 1)
    until line_ending = 0;
    if copy(last_line, 1, length(juliabase_exception_prefix)) = juliabase_exception_prefix then
    begin
      delete(last_line, 1, length(juliabase_exception_prefix));
      closing_brace := Pos(')', last_line);
      raise EJuliaBaseError.Create(StrToInt(copy(last_line, 2, closing_brace - 2)), last_line, testserver)
    end else raise Exception.Create(''#13#10 + errors)
  end;
  result := utf8decode(output)
end;

begin
  package_path := 'c:/JuliaBase/remote_client';
  module := 'jb_remote_inm'
  python_path := 'c:/Python2.7/python.exe';
  open_error_page_in_browser := false
end.
