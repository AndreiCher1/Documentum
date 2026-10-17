using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;

namespace DocIntel
{
    static class Program
    {
        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Auto)]
        public static extern bool SetEnvironmentVariable(string lpName, string lpValue);

        [STAThread]
        static void Main(string[] args)
        {
            try
            {
                SetEnvironmentVariable("ELECTRON_RUN_AS_NODE", null);
                Environment.SetEnvironmentVariable("ELECTRON_RUN_AS_NODE", null, EnvironmentVariableTarget.Process);
            }
            catch { }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            if (args != null && args.Length > 0)
            {
                string arg = args[0].ToLowerInvariant();
                if (arg == "--stop" || arg == "-stop" || arg == "/stop")
                {
                    StopAllServices();
                    return;
                }
                if (arg == "--status" || arg == "-status")
                {
                    ShowStatusDialog();
                    return;
                }
            }

            // Normal launch: start splash form and background orchestrator
            Application.Run(new SplashForm());
        }

        public static void StopAllServices()
        {
            LauncherOrchestrator.Log("Stopping all DocIntel services...");
            if (LauncherOrchestrator.StartedAiProcess != null)
            {
                try { LauncherOrchestrator.StartedAiProcess.Kill(); } catch { }
            }
            if (LauncherOrchestrator.StartedJavaProcess != null)
            {
                try { LauncherOrchestrator.StartedJavaProcess.Kill(); } catch { }
            }

            PortManager.KillProcessesOnPort(8000);
            PortManager.KillProcessesOnPort(8085);
            PortManager.KillProcessByName("DocIntel-UI");
        }

        private static void ShowStatusDialog()
        {
            bool p8000 = PortManager.IsPortListening(8000);
            bool p8085 = PortManager.IsPortListening(8085);
            string msg = string.Format(
                "DocIntel System Status:\n\n" +
                "• Python AI Service (порт 8000): {0}\n" +
                "• Java Backend API (порт 8085): {1}\n\n" +
                "DocIntel root launcher: Готов к работе.",
                p8000 ? "ONLINE" : "OFFLINE",
                p8085 ? "ONLINE" : "OFFLINE"
            );
            MessageBox.Show(msg, "DocIntel Status", MessageBoxButtons.OK, MessageBoxIcon.Information);
        }
    }

    public class ModernProgressBar : Control
    {
        private System.Windows.Forms.Timer _timer;
        private int _marqueePos = 0;

        public ModernProgressBar()
        {
            this.SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer, true);
            this.Height = 6;
            _timer = new System.Windows.Forms.Timer();
            _timer.Interval = 20;
            _timer.Tick += (s, e) =>
            {
                _marqueePos = (_marqueePos + 4) % (Math.Max(this.Width, 100) + 120);
                this.Invalidate();
            };
            _timer.Start();
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing && _timer != null)
            {
                _timer.Stop();
                _timer.Dispose();
                _timer = null;
            }
            base.Dispose(disposing);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;

            // Background track
            using (var brushBg = new SolidBrush(Color.FromArgb(30, 41, 59))) // Slate-800
            {
                e.Graphics.FillRectangle(brushBg, this.ClientRectangle);
            }

            // Animated gradient pulse
            int barWidth = 140;
            int startX = _marqueePos - barWidth;
            Rectangle barRect = new Rectangle(startX, 0, barWidth, this.Height);

            if (barRect.Right > 0 && barRect.Left < this.Width)
            {
                using (var brushBar = new LinearGradientBrush(
                    new Point(startX, 0),
                    new Point(startX + barWidth, 0),
                    Color.FromArgb(56, 189, 248),   // Sky-400
                    Color.FromArgb(99, 102, 241)))  // Indigo-500
                {
                    e.Graphics.FillRectangle(brushBar, barRect);
                }
            }
        }
    }

    public class SplashForm : Form
    {
        private Label lblTitle;
        private Label lblVersion;
        private Label lblSubtitle;
        private Label lblStatus;
        private ModernProgressBar progressBar;
        private Panel pnlCard;
        private Thread workerThread;
        private bool isClosingRequested = false;

        public SplashForm()
        {
            InitializeComponent();
            SetupAppIcon();
        }

        private void SetupAppIcon()
        {
            try
            {
                using (Bitmap bmp = new Bitmap(32, 32))
                {
                    using (Graphics g = Graphics.FromImage(bmp))
                    {
                        g.SmoothingMode = SmoothingMode.AntiAlias;
                        using (Brush b = new SolidBrush(Color.FromArgb(15, 23, 42)))
                        {
                            g.FillRectangle(b, 0, 0, 32, 32);
                        }
                        using (Brush b = new SolidBrush(Color.FromArgb(56, 189, 248)))
                        {
                            g.FillEllipse(b, 3, 3, 26, 26);
                        }
                        using (Font f = new Font("Segoe UI", 12f, FontStyle.Bold))
                        using (Brush b = new SolidBrush(Color.FromArgb(15, 23, 42)))
                        {
                            g.DrawString("D", f, b, 9, 6);
                        }
                    }
                    IntPtr hIcon = bmp.GetHicon();
                    this.Icon = Icon.FromHandle(hIcon);
                }
            }
            catch { }
        }

        private void InitializeComponent()
        {
            this.SuspendLayout();

            this.FormBorderStyle = FormBorderStyle.None;
            this.StartPosition = FormStartPosition.CenterScreen;
            this.Size = new Size(520, 230);
            this.BackColor = Color.FromArgb(11, 17, 32); // Deep Slate
            this.ShowInTaskbar = true;
            this.TopMost = true;

            pnlCard = new Panel();
            pnlCard.Dock = DockStyle.Fill;
            pnlCard.Padding = new Padding(28);
            pnlCard.Paint += (s, e) =>
            {
                e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
                using (Pen p = new Pen(Color.FromArgb(30, 41, 59), 1.5f)) // Slate-800
                {
                    e.Graphics.DrawRectangle(p, 0, 0, this.Width - 1, this.Height - 1);
                }
            };
            this.Controls.Add(pnlCard);

            // Title
            lblTitle = new Label();
            lblTitle.Text = "DocIntel";
            lblTitle.Font = new Font("Segoe UI", 21f, FontStyle.Bold);
            lblTitle.ForeColor = Color.FromArgb(248, 250, 252); // Slate-50
            lblTitle.Location = new Point(28, 24);
            lblTitle.AutoSize = true;
            pnlCard.Controls.Add(lblTitle);

            // Version Pill
            lblVersion = new Label();
            lblVersion.Text = "v0.1.0 Enterprise";
            lblVersion.Font = new Font("Segoe UI", 8f, FontStyle.Bold);
            lblVersion.ForeColor = Color.FromArgb(56, 189, 248); // Sky-400
            lblVersion.BackColor = Color.FromArgb(15, 23, 42);   // Slate-900
            lblVersion.Location = new Point(160, 34);
            lblVersion.Padding = new Padding(4, 2, 4, 2);
            lblVersion.AutoSize = true;
            pnlCard.Controls.Add(lblVersion);

            // Subtitle
            lblSubtitle = new Label();
            lblSubtitle.Text = "Корпоративная платформа интеллектуального анализа документов";
            lblSubtitle.Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);
            lblSubtitle.ForeColor = Color.FromArgb(148, 163, 184); // Slate-400
            lblSubtitle.Location = new Point(30, 66);
            lblSubtitle.AutoSize = true;
            pnlCard.Controls.Add(lblSubtitle);

            // Status label
            lblStatus = new Label();
            lblStatus.Text = "Инициализация системы...";
            lblStatus.Font = new Font("Segoe UI", 9f, FontStyle.Regular);
            lblStatus.ForeColor = Color.FromArgb(226, 232, 240); // Slate-200
            lblStatus.Location = new Point(30, 126);
            lblStatus.Size = new Size(460, 22);
            pnlCard.Controls.Add(lblStatus);

            // Modern Progress Bar
            progressBar = new ModernProgressBar();
            progressBar.Location = new Point(30, 154);
            progressBar.Size = new Size(460, 5);
            pnlCard.Controls.Add(progressBar);

            this.ResumeLayout(false);

            this.Load += SplashForm_Load;
            this.FormClosing += SplashForm_FormClosing;
        }

        private void SplashForm_Load(object sender, EventArgs e)
        {
            workerThread = new Thread(RunStartupSequence);
            workerThread.IsBackground = true;
            workerThread.Start();
        }

        private void SplashForm_FormClosing(object sender, FormClosingEventArgs e)
        {
            isClosingRequested = true;
        }

        public void SetStatus(string text)
        {
            if (isClosingRequested) return;

            if (this.InvokeRequired)
            {
                try
                {
                    this.BeginInvoke(new Action<string>(SetStatus), text);
                }
                catch { }
                return;
            }
            lblStatus.Text = text;
        }

        private void RunStartupSequence()
        {
            try
            {
                LauncherOrchestrator.Execute(this);
            }
            catch (Exception ex)
            {
                LauncherOrchestrator.Log("CRITICAL ERROR in RunStartupSequence: " + ex.ToString());
                if (isClosingRequested) return;

                this.Invoke(new Action(() =>
                {
                    MessageBox.Show(
                        "Ошибка при запуске DocIntel:\n\n" + ex.Message,
                        "DocIntel Error",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error
                    );
                    this.Close();
                }));
            }
        }
    }

    public static class LauncherOrchestrator
    {
        public static Process StartedAiProcess = null;
        public static Process StartedJavaProcess = null;
        private static readonly object _logLock = new object();

        public static void Log(string message)
        {
            lock (_logLock)
            {
                try
                {
                    string logPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "launcher.log");
                    File.AppendAllText(logPath, string.Format("[{0:yyyy-MM-dd HH:mm:ss}] {1}\r\n", DateTime.Now, message));
                }
                catch { }
            }
        }

        public static void SafeAppendText(string path, string text)
        {
            lock (_logLock)
            {
                try { File.AppendAllText(path, text); } catch { }
            }
        }

        public static void Execute(SplashForm splash)
        {
            Log("=== Starting DocIntel Orchestration ===");
            string appDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\', '/');
            string docDir = Directory.Exists(Path.Combine(appDir, "document-intelligence"))
                ? Path.Combine(appDir, "document-intelligence")
                : appDir;

            Log("appDir: " + appDir);
            Log("docDir: " + docDir);

            string aiDir = Path.Combine(docDir, "ai-service");
            string javaDir = Path.Combine(docDir, "java-backend");
            string electronDir = Path.Combine(docDir, "electron-app");
            string portableDir = Path.Combine(docDir, "portable-ui");

            splash.SetStatus("Проверка окружения и портов...");

            // 1. Check Python and dependencies
            string pythonExe = ResolvePythonExecutable(aiDir, splash);
            Log("Resolved Python: " + pythonExe);

            // 2. Launch Python AI Service (Port 8000)
            if (!PortManager.IsPortListening(8000))
            {
                splash.SetStatus("Запуск AI сервиса (порт 8000)...");
                string pyScript = Path.Combine(aiDir, "run.py");
                string pyLog = Path.Combine(aiDir, "ai.log");
                Log("Starting Python AI Service: " + pythonExe + " \"" + pyScript + "\"");
                StartedAiProcess = StartSilentProcess(pythonExe, "\"" + pyScript + "\"", aiDir, pyLog);
                Log("StartedAiProcess PID: " + (StartedAiProcess != null ? StartedAiProcess.Id.ToString() : "NULL"));

                for (int i = 0; i < 40; i++)
                {
                    if (PortManager.IsPortListening(8000))
                    {
                        Log("Port 8000 bound successfully");
                        break;
                    }
                    Thread.Sleep(250);
                }
            }
            else
            {
                Log("Port 8000 already active");
            }

            // 3. Clean up stale H2 lock if port 8085 is not listening
            string lockFile = Path.Combine(javaDir, "data", "docintelldb.lock.db");
            if (File.Exists(lockFile) && !PortManager.IsPortListening(8085))
            {
                try
                {
                    File.Delete(lockFile);
                    Log("Removed stale H2 lock file: " + lockFile);
                }
                catch { }
            }

            // 4. Check Java and launch Backend (Port 8085)
            string javaExe = ResolveJavaExecutable();
            string jarPath = Path.Combine(javaDir, "target", "document-intelligence-0.1.0.jar");
            string backendLog = Path.Combine(javaDir, "backend.log");
            Log("Resolved Java: " + javaExe);
            Log("JAR Path (" + (File.Exists(jarPath) ? "EXISTS" : "NOT FOUND") + "): " + jarPath);

            if (!PortManager.IsPortListening(8085))
            {
                splash.SetStatus("Запуск Java бэкенда (порт 8085)...");
                if (File.Exists(jarPath))
                {
                    Log("Starting Java Backend via JAR: " + javaExe + " -jar \"" + jarPath + "\"");
                    StartedJavaProcess = StartSilentProcess(javaExe, "-jar \"" + jarPath + "\"", javaDir, backendLog);
                }
                else
                {
                    Log("Starting Java Backend via Maven...");
                    string mvn = FindExecutableInPath("mvn.cmd");
                    if (string.IsNullOrEmpty(mvn)) mvn = "mvn.cmd";
                    StartedJavaProcess = StartSilentProcess("cmd.exe", "/c " + mvn + " spring-boot:run", javaDir, backendLog);
                }
                Log("StartedJavaProcess PID: " + (StartedJavaProcess != null ? StartedJavaProcess.Id.ToString() : "NULL"));
            }
            else
            {
                Log("Port 8085 already active");
            }

            // 5. Wait for backend health (poll http://localhost:8085/api/health)
            splash.SetStatus("Ожидание готовности серверов...");
            Log("Waiting for backend health...");
            for (int i = 0; i < 40; i++)
            {
                if (CheckBackendHealth())
                {
                    Log("Backend is healthy!");
                    break;
                }
                Thread.Sleep(1000);
            }

            splash.SetStatus("Запуск интерфейса системы...");

            // 6. Launch UI
            Log("Launching UI...");
            Process uiProcess = LaunchUI(docDir, portableDir, electronDir, splash);
            Log("UI Process: " + (uiProcess != null ? uiProcess.ProcessName + " (PID " + uiProcess.Id + ")" : "NULL"));

            // 7. Hide Splash Form
            splash.Invoke(new Action(() =>
            {
                splash.Hide();
            }));

            // 8. Monitor UI lifecycle: wait until user closes UI, then cleanup background services
            Log("Monitoring UI lifecycle...");
            MonitorAndCleanup(uiProcess);

            Log("UI closed. Terminating background services.");
            // Close launcher process cleanly
            splash.Invoke(new Action(() =>
            {
                splash.Close();
                Application.Exit();
            }));
        }

        private static string ResolvePythonExecutable(string aiDir, SplashForm splash)
        {
            string venvPy = Path.Combine(aiDir, "venv", "Scripts", "python.exe");
            string venvPyw = Path.Combine(aiDir, "venv", "Scripts", "pythonw.exe");

            if (File.Exists(venvPy)) return venvPy;
            if (File.Exists(venvPyw)) return venvPyw;

            // Search for system Python
            string sysPython = FindSystemPython();
            if (!string.IsNullOrEmpty(sysPython))
            {
                string reqPath = Path.Combine(aiDir, "requirements.txt");
                if (File.Exists(reqPath))
                {
                    splash.SetStatus("Первый запуск: создание Python окружения...");
                    try
                    {
                        var p1 = StartSilentProcess(sysPython, "-m venv venv", aiDir);
                        if (p1 != null) p1.WaitForExit(60000);

                        string newVenvPip = Path.Combine(aiDir, "venv", "Scripts", "pip.exe");
                        if (File.Exists(newVenvPip))
                        {
                            splash.SetStatus("Установка библиотек AI (pip install)...");
                            var p2 = StartSilentProcess(newVenvPip, "install -r requirements.txt", aiDir);
                            if (p2 != null) p2.WaitForExit(300000);
                        }
                    }
                    catch { }
                }

                if (File.Exists(venvPy)) return venvPy;
                if (File.Exists(venvPyw)) return venvPyw;
                return sysPython;
            }

            MessageBox.Show(
                "Python 3.10+ не найден на компьютере.\n\n" +
                "Для работы сервиса распознавания документов установите Python с сайта python.org\n" +
                "(Обязательно выберите галочку 'Add Python to PATH' при установке).",
                "DocIntel - Требуется Python",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning
            );

            return "python.exe";
        }

        private static string FindSystemPython()
        {
            string py = FindExecutableInPath("pythonw.exe");
            if (!string.IsNullOrEmpty(py)) return py;

            py = FindExecutableInPath("python.exe");
            if (!string.IsNullOrEmpty(py)) return py;

            string[] candidates = new string[]
            {
                @"C:\Python314\pythonw.exe", @"C:\Python314\python.exe",
                @"C:\Python313\pythonw.exe", @"C:\Python313\python.exe",
                @"C:\Python312\pythonw.exe", @"C:\Python312\python.exe",
                @"C:\Python311\pythonw.exe", @"C:\Python311\python.exe",
                @"C:\Python310\pythonw.exe", @"C:\Python310\python.exe"
            };

            foreach (var c in candidates)
            {
                if (File.Exists(c)) return c;
            }

            string localApp = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            if (!string.IsNullOrEmpty(localApp))
            {
                string pyRoot = Path.Combine(localApp, "Programs", "Python");
                if (Directory.Exists(pyRoot))
                {
                    var dirs = Directory.GetDirectories(pyRoot, "Python*");
                    foreach (var d in dirs)
                    {
                        string targetPyw = Path.Combine(d, "pythonw.exe");
                        if (File.Exists(targetPyw)) return targetPyw;
                        string targetPy = Path.Combine(d, "python.exe");
                        if (File.Exists(targetPy)) return targetPy;
                    }
                }
            }

            return null;
        }

        private static string ResolveJavaExecutable()
        {
            string javaw = FindExecutableInPath("javaw.exe");
            if (!string.IsNullOrEmpty(javaw)) return javaw;

            string javaHome = Environment.GetEnvironmentVariable("JAVA_HOME");
            if (!string.IsNullOrEmpty(javaHome))
            {
                string target = Path.Combine(javaHome, "bin", "javaw.exe");
                if (File.Exists(target)) return target;
                target = Path.Combine(javaHome, "bin", "java.exe");
                if (File.Exists(target)) return target;
            }

            string java = FindExecutableInPath("java.exe");
            if (!string.IsNullOrEmpty(java)) return java;

            // Check standard Adoptium / Oracle install paths
            string progFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
            if (!string.IsNullOrEmpty(progFiles))
            {
                string adoptium = Path.Combine(progFiles, "Eclipse Adoptium");
                if (Directory.Exists(adoptium))
                {
                    var jdkDirs = Directory.GetDirectories(adoptium, "jdk*");
                    foreach (var jd in jdkDirs)
                    {
                        string jw = Path.Combine(jd, "bin", "javaw.exe");
                        if (File.Exists(jw)) return jw;
                    }
                }

                string javaDir = Path.Combine(progFiles, "Java");
                if (Directory.Exists(javaDir))
                {
                    var jdkDirs = Directory.GetDirectories(javaDir, "jdk*");
                    foreach (var jd in jdkDirs)
                    {
                        string jw = Path.Combine(jd, "bin", "javaw.exe");
                        if (File.Exists(jw)) return jw;
                    }
                }
            }

            return "javaw.exe";
        }

        private static Process LaunchUI(string docDir, string portableDir, string electronDir, SplashForm splash)
        {
            try
            {
                Program.SetEnvironmentVariable("ELECTRON_RUN_AS_NODE", null);
                Environment.SetEnvironmentVariable("ELECTRON_RUN_AS_NODE", null);
            }
            catch { }

            // Priority 1: Portable Standalone Executable (DocIntel-UI.exe)
            string portableExe = Path.Combine(portableDir, "DocIntel-UI.exe");
            if (File.Exists(portableExe))
            {
                Log("Starting portable UI: " + portableExe);
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = portableExe;
                psi.WorkingDirectory = portableDir;
                psi.UseShellExecute = false;
                if (psi.EnvironmentVariables.ContainsKey("ELECTRON_RUN_AS_NODE"))
                {
                    psi.EnvironmentVariables.Remove("ELECTRON_RUN_AS_NODE");
                }
                return Process.Start(psi);
            }

            // Priority 2: Local Electron Binary in electron-app\node_modules
            string localElectron = Path.Combine(electronDir, "node_modules", "electron", "dist", "electron.exe");
            if (File.Exists(localElectron))
            {
                Log("Starting local Electron: " + localElectron);
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = localElectron;
                psi.Arguments = "\"" + electronDir + "\"";
                psi.WorkingDirectory = electronDir;
                psi.UseShellExecute = false;
                if (psi.EnvironmentVariables.ContainsKey("ELECTRON_RUN_AS_NODE"))
                {
                    psi.EnvironmentVariables.Remove("ELECTRON_RUN_AS_NODE");
                }
                return Process.Start(psi);
            }

            // Priority 3: Check if node_modules needs npm install
            if (Directory.Exists(electronDir) && !Directory.Exists(Path.Combine(electronDir, "node_modules")))
            {
                string npm = FindExecutableInPath("npm.cmd");
                if (!string.IsNullOrEmpty(npm))
                {
                    splash.SetStatus("Установка пакетов интерфейса (npm install)...");
                    try
                    {
                        var pNpm = StartSilentProcess(npm, "install --no-audit --no-fund", electronDir);
                        if (pNpm != null) pNpm.WaitForExit(180000);

                        if (File.Exists(localElectron))
                        {
                            ProcessStartInfo psi = new ProcessStartInfo();
                            psi.FileName = localElectron;
                            psi.Arguments = "\"" + electronDir + "\"";
                            psi.WorkingDirectory = electronDir;
                            psi.UseShellExecute = false;
                            return Process.Start(psi);
                        }
                    }
                    catch { }
                }
            }

            // Priority 4: Microsoft Edge App Window mode (Zero-dependency fallback)
            try
            {
                Log("Launching Edge App mode fallback");
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = "msedge.exe";
                psi.Arguments = "--app=\"http://localhost:8085\"";
                psi.UseShellExecute = true;
                return Process.Start(psi);
            }
            catch { }

            // Priority 5: Default Web Browser
            Log("Launching default browser fallback");
            return Process.Start("http://localhost:8085");
        }

        private static void MonitorAndCleanup(Process uiProcess)
        {
            // 1. Wait up to 12 seconds for UI process to actually appear
            bool uiDetected = false;
            for (int i = 0; i < 24; i++)
            {
                Process[] p1 = Process.GetProcessesByName("DocIntel-UI");
                Process[] p2 = Process.GetProcessesByName("electron");
                if (p1.Length > 0 || p2.Length > 0)
                {
                    uiDetected = true;
                    Log(string.Format("UI process confirmed active (DocIntel-UI: {0}, electron: {1})", p1.Length, p2.Length));
                    break;
                }
                Thread.Sleep(500);
            }

            if (!uiDetected && uiProcess != null && !uiProcess.HasExited)
            {
                // Fallback for non-electron (e.g. Edge App mode or browser)
                string procName = "";
                try { procName = uiProcess.ProcessName.ToLowerInvariant(); } catch { }
                if (procName != "docintel-ui" && procName != "electron")
                {
                    Log("Waiting for non-electron process: " + procName);
                    try { uiProcess.WaitForExit(); } catch { }
                    Program.StopAllServices();
                    return;
                }
            }

            // 2. Poll until ALL UI windows/processes are closed
            int emptyCount = 0;
            while (true)
            {
                Thread.Sleep(1000);
                Process[] p1 = Process.GetProcessesByName("DocIntel-UI");
                Process[] p2 = Process.GetProcessesByName("electron");

                if (p1.Length == 0 && p2.Length == 0)
                {
                    emptyCount++;
                    if (emptyCount >= 3)
                    {
                        Log("All UI processes exited. Initiating service shutdown.");
                        break;
                    }
                }
                else
                {
                    emptyCount = 0;
                }
            }

            // User closed the window: cleanly terminate background servers
            Program.StopAllServices();
        }

        private static Process StartSilentProcess(string fileName, string arguments, string workingDirectory, string logFile = null)
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = fileName;
                psi.Arguments = arguments;
                psi.WorkingDirectory = workingDirectory;
                psi.CreateNoWindow = true;
                psi.UseShellExecute = false;
                psi.WindowStyle = ProcessWindowStyle.Hidden;

                if (!string.IsNullOrEmpty(logFile))
                {
                    psi.RedirectStandardOutput = true;
                    psi.RedirectStandardError = true;
                    Process proc = new Process();
                    proc.StartInfo = psi;
                    proc.OutputDataReceived += (s, e) =>
                    {
                        if (e.Data != null) SafeAppendText(logFile, e.Data + "\r\n");
                    };
                    proc.ErrorDataReceived += (s, e) =>
                    {
                        if (e.Data != null) SafeAppendText(logFile, "[ERR] " + e.Data + "\r\n");
                    };
                    proc.Start();
                    proc.BeginOutputReadLine();
                    proc.BeginErrorReadLine();
                    return proc;
                }
                else
                {
                    return Process.Start(psi);
                }
            }
            catch (Exception ex)
            {
                Log("StartSilentProcess EXCEPTION: " + fileName + " " + arguments + " -> " + ex.Message);
                return null;
            }
        }

        private static bool CheckBackendHealth()
        {
            try
            {
                HttpWebRequest req = (HttpWebRequest)WebRequest.Create("http://localhost:8085/api/health");
                req.Timeout = 1500;
                req.Method = "GET";
                using (HttpWebResponse resp = (HttpWebResponse)req.GetResponse())
                {
                    if (resp.StatusCode == HttpStatusCode.OK)
                    {
                        using (StreamReader reader = new StreamReader(resp.GetResponseStream()))
                        {
                            string body = reader.ReadToEnd();
                            return body.Contains("healthy") || body.Contains("running");
                        }
                    }
                }
            }
            catch { }
            return false;
        }

        private static string FindExecutableInPath(string exeName)
        {
            string pathEnv = Environment.GetEnvironmentVariable("PATH");
            if (string.IsNullOrEmpty(pathEnv)) return null;

            string[] paths = pathEnv.Split(';');
            foreach (string p in paths)
            {
                try
                {
                    string trimmed = p.Trim('\"', ' ', '\'');
                    if (!string.IsNullOrEmpty(trimmed) && Directory.Exists(trimmed))
                    {
                        string fullPath = Path.Combine(trimmed, exeName);
                        if (File.Exists(fullPath)) return fullPath;
                    }
                }
                catch { }
            }
            return null;
        }
    }

    public static class PortManager
    {
        public static bool IsPortListening(int port)
        {
            try
            {
                IPGlobalProperties ipProps = IPGlobalProperties.GetIPGlobalProperties();
                IPEndPoint[] listeners = ipProps.GetActiveTcpListeners();
                for (int i = 0; i < listeners.Length; i++)
                {
                    if (listeners[i].Port == port) return true;
                }
            }
            catch { }
            return false;
        }

        public static void KillProcessesOnPort(int port)
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = "netstat.exe";
                psi.Arguments = "-ano -p tcp";
                psi.CreateNoWindow = true;
                psi.UseShellExecute = false;
                psi.RedirectStandardOutput = true;

                using (Process proc = Process.Start(psi))
                {
                    if (proc == null) return;
                    string output = proc.StandardOutput.ReadToEnd();
                    proc.WaitForExit(3000);

                    string[] lines = output.Split(new char[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);
                    string portSuffix = ":" + port;

                    foreach (string line in lines)
                    {
                        string[] tokens = line.Split(new char[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                        if (tokens.Length >= 5 && tokens[0].Equals("TCP", StringComparison.OrdinalIgnoreCase))
                        {
                            if (tokens[1].EndsWith(portSuffix))
                            {
                                int pid;
                                if (int.TryParse(tokens[tokens.Length - 1], out pid) && pid > 0)
                                {
                                    // 1. Try Process.Kill()
                                    try
                                    {
                                        Process targetProc = Process.GetProcessById(pid);
                                        targetProc.Kill();
                                        LauncherOrchestrator.Log(string.Format("Killed process {0} on port {1}", pid, port));
                                    }
                                    catch { }

                                    // 2. Fallback to taskkill /F /T to terminate child trees
                                    try
                                    {
                                        ProcessStartInfo tk = new ProcessStartInfo("taskkill.exe", "/F /T /PID " + pid);
                                        tk.CreateNoWindow = true;
                                        tk.UseShellExecute = false;
                                        using (var pTk = Process.Start(tk))
                                        {
                                            if (pTk != null) pTk.WaitForExit(2000);
                                        }
                                    }
                                    catch { }
                                }
                            }
                        }
                    }
                }
            }
            catch { }
        }

        public static void KillProcessByName(string processName)
        {
            try
            {
                Process[] procs = Process.GetProcessesByName(processName);
                foreach (var p in procs)
                {
                    try { p.Kill(); } catch { }
                }
            }
            catch { }
        }
    }
}
