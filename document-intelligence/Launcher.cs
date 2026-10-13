using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Threading;
using System.Windows.Forms;

namespace DocIntelLauncher
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new LauncherForm());
        }
    }

    public class LauncherForm : Form
    {
        private Label lblTitle;
        private Label lblSubtitle;
        private Label lblAiStatus;
        private Label lblJavaStatus;
        private Label lblElectronStatus;
        private ProgressBar progressBar;
        private Button btnRestartUi;
        private Button btnStopAll;

        private Process procPython;
        private Process procJava;
        private Process procElectron;

        private string baseDir;
        private Thread workerThread;
        private volatile bool isStopping = false;

        public LauncherForm()
        {
            baseDir = AppDomain.CurrentDomain.BaseDirectory;
            InitializeComponent();
            this.FormClosing += LauncherForm_FormClosing;

            workerThread = new Thread(RunStartupSequence);
            workerThread.IsBackground = true;
            workerThread.Start();
        }

        private void InitializeComponent()
        {
            this.Text = "Document Intelligence Launcher";
            this.Size = new Size(520, 360);
            this.StartPosition = FormStartPosition.CenterScreen;
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.BackColor = Color.FromArgb(26, 26, 46);
            this.ForeColor = Color.FromArgb(224, 224, 224);
            this.Font = new Font("Segoe UI", 9F, FontStyle.Regular);

            lblTitle = new Label();
            lblTitle.Text = "📄 Document Intelligence";
            lblTitle.Font = new Font("Segoe UI", 16F, FontStyle.Bold);
            lblTitle.ForeColor = Color.FromArgb(79, 195, 247);
            lblTitle.Location = new Point(24, 20);
            lblTitle.AutoSize = true;
            this.Controls.Add(lblTitle);

            lblSubtitle = new Label();
            lblSubtitle.Text = "Интеллектуальная система анализа и структурирования документов";
            lblSubtitle.ForeColor = Color.FromArgb(160, 160, 176);
            lblSubtitle.Location = new Point(26, 52);
            lblSubtitle.AutoSize = true;
            this.Controls.Add(lblSubtitle);

            // Карточки статуса
            int startY = 90;
            lblAiStatus = CreateStatusLabel("🤖 Python AI Service (порт 8000):", "Инициализация...", startY);
            lblJavaStatus = CreateStatusLabel("☕ Java Backend (порт 8085):", "Ожидание...", startY + 36);
            lblElectronStatus = CreateStatusLabel("🖥️ Electron Desktop UI:", "Ожидание готовности серверов...", startY + 72);

            progressBar = new ProgressBar();
            progressBar.Location = new Point(28, startY + 120);
            progressBar.Size = new Size(450, 14);
            progressBar.Style = ProgressBarStyle.Marquee;
            progressBar.MarqueeAnimationSpeed = 30;
            this.Controls.Add(progressBar);

            btnRestartUi = new Button();
            btnRestartUi.Text = "🔄 Перезапустить UI";
            btnRestartUi.Location = new Point(160, startY + 155);
            btnRestartUi.Size = new Size(150, 34);
            btnRestartUi.BackColor = Color.FromArgb(30, 42, 74);
            btnRestartUi.ForeColor = Color.FromArgb(79, 195, 247);
            btnRestartUi.FlatStyle = FlatStyle.Flat;
            btnRestartUi.FlatAppearance.BorderColor = Color.FromArgb(42, 58, 94);
            btnRestartUi.Click += (s, e) => LaunchElectron();
            this.Controls.Add(btnRestartUi);

            btnStopAll = new Button();
            btnStopAll.Text = "🛑 Остановить всё";
            btnStopAll.Location = new Point(320, startY + 155);
            btnStopAll.Size = new Size(158, 34);
            btnStopAll.BackColor = Color.FromArgb(45, 25, 35);
            btnStopAll.ForeColor = Color.FromArgb(239, 83, 80);
            btnStopAll.FlatStyle = FlatStyle.Flat;
            btnStopAll.FlatAppearance.BorderColor = Color.FromArgb(70, 35, 45);
            btnStopAll.Click += (s, e) => this.Close();
            this.Controls.Add(btnStopAll);
        }

        private Label CreateStatusLabel(string prefix, string initialStatus, int y)
        {
            Label lbl = new Label();
            lbl.Text = prefix + "  " + initialStatus;
            lbl.Location = new Point(28, y);
            lbl.Size = new Size(450, 24);
            lbl.Font = new Font("Segoe UI", 9.5F, FontStyle.Regular);
            this.Controls.Add(lbl);
            return lbl;
        }

        private void SetStatus(Label lbl, string prefix, string status, Color color)
        {
            if (this.InvokeRequired)
            {
                this.BeginInvoke(new Action(() => SetStatus(lbl, prefix, status, color)));
                return;
            }
            lbl.Text = prefix + "  " + status;
            lbl.ForeColor = color;
        }

        private void RunStartupSequence()
        {
            try
            {
                // 1. Проверяем свободны ли порты или уже работают сервисы
                if (CheckHealth())
                {
                    SetStatus(lblAiStatus, "🤖 Python AI Service (порт 8000):", "Уже запущен ✓", Color.FromArgb(102, 187, 106));
                    SetStatus(lblJavaStatus, "☕ Java Backend (порт 8085):", "Уже запущен ✓", Color.FromArgb(102, 187, 106));
                }
                else
                {
                    // Запуск Python
                    SetStatus(lblAiStatus, "🤖 Python AI Service (порт 8000):", "Запуск PaddleOCR...", Color.FromArgb(255, 167, 38));
                    StartPythonService();

                    // Запуск Java
                    SetStatus(lblJavaStatus, "☕ Java Backend (порт 8085):", "Запуск Spring Boot...", Color.FromArgb(255, 167, 38));
                    StartJavaBackend();

                    // Ожидание готовности
                    bool ready = false;
                    for (int i = 0; i < 35; i++)
                    {
                        if (isStopping) return;
                        Thread.Sleep(1000);
                        if (CheckHealth())
                        {
                            ready = true;
                            break;
                        }
                    }

                    if (ready)
                    {
                        SetStatus(lblAiStatus, "🤖 Python AI Service (порт 8000):", "Работает ✓", Color.FromArgb(102, 187, 106));
                        SetStatus(lblJavaStatus, "☕ Java Backend (порт 8085):", "Работает ✓", Color.FromArgb(102, 187, 106));
                    }
                    else
                    {
                        SetStatus(lblJavaStatus, "☕ Java Backend (порт 8085):", "Запуск занимает больше времени...", Color.FromArgb(255, 167, 38));
                    }
                }

                // Запуск Electron
                SetStatus(lblElectronStatus, "🖥️ Electron Desktop UI:", "Запуск окна приложения...", Color.FromArgb(79, 195, 247));
                LaunchElectron();
                SetStatus(lblElectronStatus, "🖥️ Electron Desktop UI:", "Приложение открыто ✓", Color.FromArgb(102, 187, 106));

                if (this.InvokeRequired)
                {
                    this.BeginInvoke(new Action(() => { progressBar.Style = ProgressBarStyle.Blocks; progressBar.Value = 100; }));
                }
            }
            catch (Exception ex)
            {
                SetStatus(lblJavaStatus, "Ошибка запуска:", ex.Message, Color.FromArgb(239, 83, 80));
            }
        }

        private void StartPythonService()
        {
            string aiDir = Path.Combine(baseDir, "ai-service");
            string pythonExe = Path.Combine(aiDir, "venv", "Scripts", "python.exe");
            if (!File.Exists(pythonExe))
            {
                pythonExe = "python.exe";
            }

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = pythonExe;
            psi.Arguments = "run.py";
            psi.WorkingDirectory = aiDir;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            psi.WindowStyle = ProcessWindowStyle.Hidden;

            procPython = Process.Start(psi);
        }

        private void StartJavaBackend()
        {
            string javaDir = Path.Combine(baseDir, "java-backend");
            string jarPath = Path.Combine(javaDir, "target", "document-intelligence-0.1.0.jar");

            ProcessStartInfo psi = new ProcessStartInfo();
            if (File.Exists(jarPath))
            {
                psi.FileName = "java.exe";
                psi.Arguments = "-jar \"" + jarPath + "\"";
            }
            else
            {
                psi.FileName = "cmd.exe";
                psi.Arguments = "/c mvn.cmd spring-boot:run";
            }
            psi.WorkingDirectory = javaDir;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            psi.WindowStyle = ProcessWindowStyle.Hidden;

            procJava = Process.Start(psi);
        }

        private bool CheckHealth()
        {
            try
            {
                HttpWebRequest req = (HttpWebRequest)WebRequest.Create("http://localhost:8085/api/health");
                req.Timeout = 1500;
                using (HttpWebResponse resp = (HttpWebResponse)req.GetResponse())
                {
                    return resp.StatusCode == HttpStatusCode.OK;
                }
            }
            catch
            {
                return false;
            }
        }

        private void LaunchElectron()
        {
            string electronDir = Path.Combine(baseDir, "electron-app");
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = "cmd.exe";
            psi.Arguments = "/c npm start";
            psi.WorkingDirectory = electronDir;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;

            procElectron = Process.Start(psi);
        }

        private void LauncherForm_FormClosing(object sender, FormClosingEventArgs e)
        {
            isStopping = true;
            StopAllProcesses();
        }

        private void StopAllProcesses()
        {
            try
            {
                if (procElectron != null && !procElectron.HasExited)
                {
                    procElectron.Kill();
                }
            }
            catch { }

            try
            {
                if (procPython != null && !procPython.HasExited)
                {
                    procPython.Kill();
                }
            }
            catch { }

            try
            {
                if (procJava != null && !procJava.HasExited)
                {
                    procJava.Kill();
                }
            }
            catch { }

            // Дополнительно глушим дочерние процессы Electron и освобождаем порты
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo("cmd.exe", "/c taskkill /F /IM electron.exe /T 2>nul");
                psi.CreateNoWindow = true;
                psi.UseShellExecute = false;
                Process.Start(psi);
            }
            catch { }
        }
    }
}

