using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace DocIntelLauncher
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            string checkDir = AppDomain.CurrentDomain.BaseDirectory;
            string batPath;
            string workingDir;

            if (File.Exists(Path.Combine(checkDir, "document-intelligence", "start.bat")))
            {
                batPath = Path.Combine(checkDir, "document-intelligence", "start.bat");
                workingDir = Path.Combine(checkDir, "document-intelligence");
            }
            else if (File.Exists(Path.Combine(checkDir, "start.bat")))
            {
                batPath = Path.Combine(checkDir, "start.bat");
                workingDir = checkDir;
            }
            else
            {
                MessageBox.Show("Не найден start.bat в директории: " + checkDir, "DocIntel", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = "cmd.exe";
            psi.Arguments = "/c chcp 65001 >nul && call \"" + batPath + "\"";
            psi.WorkingDirectory = workingDir;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;

            try
            {
                Process proc = Process.Start(psi);
                if (proc != null)
                {
                    proc.WaitForExit();
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show("Ошибка запуска Document Intelligence:\n" + ex.Message, "DocIntel", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }
}
