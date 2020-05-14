unit juliabase;

{ This file is part of JuliaBase-Institute, see http://www.juliabase.org.
  Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany

  This program is free software: you can redistribute it and/or modify it under
  the terms of the GNU General Public License as published by the Free Software
  Foundation, either version 3 of the License, or (at your option) any later
  version.

  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
  FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
  details.

  You should have received a copy of the GNU General Public License along with
  this program.  If not, see <http://www.gnu.org/licenses/>.
  }

(*
  Delphi wrapper for the remote client
  ====================================

  See also http://www.juliabase.org/programming/remote_client.html for further
  information.
  
  This unit exports only one function, namely execute_jb.  This function has
  three parameters, namely the login name, the password, and the command
  string.  For example, in order to set a sample's current location, you may
  use this program:

  .. code-block:: delphi

      program juliabase_example;

      {$APPTYPE CONSOLE}

      uses
        SysUtils, juliabase;
      var
        result : String

      begin
        execute_jb('juliabase', '12345',
             'sample = Sample("14-JS-1");' +
             'sample.current_location = "Sean''s office";' +
             'sample.edit_description = "location changed";' +
             'sample.submit()');
      end.
  
  Additionally, there is a forth, optional parameter, which is boolean.  If
  it's true, the command is executed on the test server.  By default, it is
  false, so that the command is executed on the production server.
  
  Moreover, this unit contains four global variables that serve as settings
  that you can modifiy.
 
  ``jb_package_path``
    contains the directory of the institute's adaption of the remote client.
    Default: :file:'c:/JuliaBase/remote_client'

  ``jb_module_name``
    contains the module name of the institute's adaption of the remote client.
    Default: ``jb_remote_inm``

  ``jb_interpreter_path``
    contains the path of the Python interpreter.  Default:
    :file:'c:/Python3.6/python.exe'

  ``jb_open_error_page_in_browser``
    If ``true``, in case of error the error page will be automatically opened
    in the browser.  Default: ``false``

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
  jb_package_path, jb_module_name, jb_interpreter_path: String;
  jb_open_error_page_in_browser: boolean;

function execute_jb(const login, password, commands: String; testserver: boolean=false): String;

implementation

uses Windows, ShellAPI;

// Taken from
// http://www.delphi-forum.de/topic_ConsolenOutput+in+Memo+pipen+UND+in+Konsole_98927,0.html

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

  procedure ReadPipeToString(const hPipe: THandle; var Result: String);
  var
    AvailableBytes, ReadBytes: Cardinal;
    Buffer: String;
  begin
    PeekNamedPipe(hPipe, NIL, 0, NIL, @AvailableBytes, NIL);
    while (AvailableBytes > 0) do
    begin
      SetLength(Buffer, AvailableBytes);
      if ReadFile(hPipe, PChar(Buffer)^, AvailableBytes, ReadBytes, NIL) then
        if (ReadBytes > 0) then begin
          SetLength(Buffer, ReadBytes);
          Result := Result + Buffer;
        end;
      PeekNamedPipe(hPipe, NIL, 0, NIL, @AvailableBytes, NIL);
    end;
  end;

begin
  AOutput := '';
  AErrors := '';
  // initialize and fill Win-API structures
  FillChar(ProcessInfo, SizeOf(TProcessInformation), 0);
  FillChar(SecurityAttr, SizeOf(TSecurityAttributes), 0);
  SecurityAttr.nLength := SizeOf(SecurityAttr);
  SecurityAttr.bInheritHandle := TRUE;
  SecurityAttr.lpSecurityDescriptor := NIL;
  CreatePipe(PipeInputRead, PipeInputWrite, @SecurityAttr, 0);
  CreatePipe(PipeOutputRead, PipeOutputWrite, @SecurityAttr, 0);
  CreatePipe(PipeErrorsRead, PipeErrorsWrite, @SecurityAttr, 0);
  FillChar(StartupInfo, SizeOf(TStartupInfo), 0);
  StartupInfo.cb := SizeOf(StartupInfo);
  StartupInfo.hStdInput := PipeInputRead;
  StartupInfo.hStdOutput := PipeOutputWrite;
  StartupInfo.hStdError := PipeErrorsWrite;
  StartupInfo.wShowWindow := SW_HIDE;
  StartupInfo.dwFlags := STARTF_USESHOWWINDOW or STARTF_USESTDHANDLES;
  // msdn2.microsoft.com/...ibrary/ms682425.aspx
  Result := CreateProcess(NIL, PChar(ACommand), NIL, NIL, TRUE, 
                          CREATE_DEFAULT_ERROR_MODE
                          or CREATE_NEW_CONSOLE
                          or NORMAL_PRIORITY_CLASS,
                          NIL, NIL, StartupInfo, ProcessInfo);
  WriteFile(PipeInputWrite, AInput[1], length(AInput), dw, nil);
  if Result then
  begin // process started sucessfully?
    repeat
      GetExitCodeProcess(ProcessInfo.hProcess, AExitCode); // msdn2.microsoft.com/...ibrary/ms683189.aspx
      ReadPipeToString(PipeOutputRead, AOutput);
      ReadPipeToString(PipeErrorsRead, AErrors);
      if (AExitCode = STILL_ACTIVE) then
        Sleep(1);
    until (AExitCode <> STILL_ACTIVE);
    CloseHandle(ProcessInfo.hThread);
    CloseHandle(ProcessInfo.hProcess);
  end;
  CloseHandle(PipeOutputWrite);
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
  if jb_open_error_page_in_browser and (ErrorCode = 1) then
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
  full_input := format('import sys; sys.path.append("%s");from %s import *;' +
                       'login("%s", "%s", testserver=%s);%s;logout()'#26,
		       [jb_package_path, jb_module_name, login, password, testserver_string, commands]);
  if not ExecConsoleCommand(jb_interpreter_path, utf8encode(full_input), output, errors, exit_code) then
  begin
    raise Exception.Create('error: Could not start ' + jb_interpreter_path)
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
  jb_package_path := 'c:/JuliaBase/remote_client';
  jb_module_name := 'jb_remote_inm';
  jb_interpreter_path := 'c:/Python36/python.exe';
  jb_open_error_page_in_browser := true
end.
