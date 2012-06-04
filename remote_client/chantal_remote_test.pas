program chantal_remote_test;

{$APPTYPE CONSOLE}

uses
  SysUtils, chantal;

begin
  writeln(execute_chantal('login', 'password',
	  'sample = Sample("10-TB-Dummy"); sample.purpose = u"Hallöchen"; sample.edit_description = "."; sample.submit()'));
  readln;
end.
