Rem  Visual Basic wrapper for the remote client
Rem  ==========================================
Rem
Rem  See also http://www.juliabase.org/programming/remote_client.html for further
Rem  information.
Rem  
Rem  This unit exports only one function, namely execute_jb.  This function has
Rem  three parameters, namely the login name, the password, and the command
Rem  string.  For example, in order to set a sample's current location, you may
Rem  use this program:
Rem
Rem  .. code-block:: visualbasic
Rem
Rem      Imports System
Rem      Imports Juliabase
Rem
Rem      Public Module ModuleMain
Rem          Sub Main()
Rem              JB_Package_Path = "D:\JuliaBase\remote_client\"
Rem              JB_Module_Name = "jb_remote_inm"
Rem
Rem              Execute_JB("juliabase", "12345",
Rem                     "sample = Sample('14-JS-1');" &
Rem                     "sample.current_location = 'small lab';" &
Rem                     "sample.edit_description = 'location changed';" &
Rem                     "sample.submit()")
Rem          End Sub
Rem      End Module
Rem  
Rem  Additionally, there is a forth, optional parameter, which is boolean.  If
Rem  it's true, the command is executed on the test server.  By default, it is
Rem  false, so that the command is executed on the production server.
Rem  
Rem  Moreover, this unit contains four global variables that serve as settings
Rem  that you can modifiy.
Rem 
Rem  ``JB_Package_Path``
Rem    contains the directory of the institute's adaption of the remote client.
Rem    Default: :file:'c:\JuliaBase\remote_client\'
Rem
Rem  ``JB_Module_Name``
Rem    contains the module name of the institute's adaption of the remote client.
Rem    Default: ``jb_remote_inm``
Rem
Rem  ``JB_Interpreter_Path``
Rem    contains the path of the Python interpreter.  Default:
Rem    :file:'c:\Python36\python.exe'
Rem
Rem  ``JB_Open_Error_Page_In_Browser``
Rem    If ``True``, in case of error the error page will be automatically opened
Rem    in the browser.  Default: ``True``
Rem
Rem  =======================================================================================


Module Juliabase

    Public JB_Interpreter_Path = "c:\Python34\python.exe"
    Public JB_Package_Path = "c:\JuliaBase\remote_client\"
    Public JB_Module_Name = "jb_remote_inm"
    Public JB_Open_Error_Page_In_Browser = True

    Public Class JuliabaseException
        Inherits Exception
        Public code As Integer

        Public Sub New(ByVal code_ As Integer, ByVal message As String)
            MyBase.New(message)
            code = code_
            If JB_Open_Error_Page_In_Browser And code = 1 Then
                Dim closing_brace = message.IndexOf(")")
                Dim url = message.Substring(closing_brace + 2)
                System.Diagnostics.Process.Start(url)
            End If
        End Sub
    End Class

    Function SanitizeString(ByVal unsanitized As String)
       SanitizeString = Replace(Replace(unsanitized, "\", "\\"), """", "\""")
    End Function
   
    Function Execute_JB(ByVal login As String, ByVal password As String, ByVal commands As String,
        Optional ByVal testserver As Boolean = False) As String

        Dim pythonCode = "import sys" & Environment.NewLine &
                         "sys.path.append(""" & SanitizeString(JB_Package_Path) & """)" & Environment.NewLine &
                         "from " & JB_Module_Name & " import *" & Environment.NewLine &
                         "login(""" & SanitizeString(login) & """, """ & SanitizeString(password) & """, testserver="
        If testserver Then
           pythonCode = pythonCode & "True"
        Else
           pythonCode = pythonCode & "False"
        End If
        pythonCode = pythonCode & ")" & Environment.NewLine & commands & Environment.NewLine &
                     "logout()" & Environment.NewLine
        Dim pr As New Process
        With pr.StartInfo
            .FileName = JB_Interpreter_Path
            .Arguments = ""
            .UseShellExecute = False
            .ErrorDialog = False
            .CreateNoWindow = True
            .RedirectStandardInput = True
            .RedirectStandardOutput = True
            .RedirectStandardError = True
        End With
        pr.Start()
        Dim stdin = pr.StandardInput
        Dim stdout = pr.StandardOutput
        Dim stderr = pr.StandardError
        stdin.Write(pythonCode)
        stdin.Close()
        pr.WaitForExit()
        If pr.ExitCode <> 0 Then
            Dim juliabase_exception_prefix = "jb_remote.common.JuliaBaseError: "
            Dim error_output = stderr.ReadToEnd
            Dim error_lines = error_output.Split(New String() {Environment.NewLine}, StringSplitOptions.None)
            Dim error_line = error_lines(error_lines.Length - 2)
            If error_line.StartsWith(juliabase_exception_prefix) Then
                error_line = error_line.Substring(juliabase_exception_prefix.Length)
                Dim closing_brace = error_line.IndexOf(")")
                Dim error_code As Integer = Int(Mid(error_line, 2, closing_brace - 1))
                Dim error_message = error_line.Substring(closing_brace + 2)
                Throw New JuliabaseException(Error_code, error_message)
            Else
                Dim error_message = error_output
                Throw New System.Exception(error_message)
            End If
        End If
        Execute_JB = stdout.ReadToEnd
    End Function

End Module
