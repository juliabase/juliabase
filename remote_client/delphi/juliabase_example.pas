program juliabase_example;

{$APPTYPE CONSOLE}

uses
  SysUtils, juliabase;
var
   result : String

begin
  writeln(execute_jb('juliabase', '12345',
	  'sample = Sample("14-JS-1"); sample.current_location = "Optics lab"; ' +
          'sample.edit_description = "location changed"; sample.submit()'));
  readln;
end.
