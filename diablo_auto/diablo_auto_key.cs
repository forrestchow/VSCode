// ============================================================
// 暗黑破坏神 自动按键工具  v3.0  (右键触发 + Z键停止)
// ============================================================
// 逻辑: 启动后监听 → 游戏内按右键开始自动按键 → 按Z停止回到监听
// ============================================================
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace DiabloAutoKey
{
    // ==================== Win32 API ====================
    internal class WinAPI
    {
        [DllImport("user32.dll")]
        public static extern IntPtr GetForegroundWindow();

        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

        [DllImport("user32.dll")]
        public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);

        [DllImport("user32.dll")]
        public static extern short GetAsyncKeyState(int vKey);

        [DllImport("user32.dll")]
        public static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);

        [StructLayout(LayoutKind.Sequential)]
        public struct KEYBDINPUT { public ushort wVk; public ushort wScan; public uint dwFlags; public uint time; public IntPtr dwExtraInfo; }

        [StructLayout(LayoutKind.Sequential)]
        public struct MOUSEINPUT { public int dx; public int dy; public uint mouseData; public uint dwFlags; public uint time; public IntPtr dwExtraInfo; }

        [StructLayout(LayoutKind.Sequential)]
        public struct HARDWAREINPUT { public uint uMsg; public ushort wParamL; public ushort wParamH; }

        [StructLayout(LayoutKind.Explicit, Size = 40)]
        public struct INPUT
        {
            [FieldOffset(0)] public uint type;
            [FieldOffset(8)] public MOUSEINPUT mi;
            [FieldOffset(8)] public KEYBDINPUT ki;
            [FieldOffset(8)] public HARDWAREINPUT hi;
        }

        public const uint INPUT_KEYBOARD = 1;
        public const uint INPUT_MOUSE = 0;
        public const uint KEYEVENTF_KEYUP = 0x0002;
        public const uint MOUSEEVENTF_RIGHTDOWN = 0x0008;
        public const uint MOUSEEVENTF_RIGHTUP = 0x0010;
        public const uint MOUSEEVENTF_LEFTDOWN = 0x0002;
        public const uint MOUSEEVENTF_LEFTUP = 0x0004;
        public const uint MOUSEEVENTF_MIDDLEDOWN = 0x0020;
        public const uint MOUSEEVENTF_MIDDLEUP = 0x0040;
        public const uint MOUSEEVENTF_XDOWN = 0x0080;
        public const uint MOUSEEVENTF_XUP = 0x0100;

        public const int KEY_DOWN = 0x8000;
    }

    // ==================== 目标进程信息 ====================
    class TargetInfo
    {
        public int Pid; public string ProcessName; public string WindowTitle;
        public bool HasWindow; public bool IsRunning;
        public override string ToString()
        { return (HasWindow ? "🪟" : "⚙") + " " + ProcessName + " (PID " + Pid + ") " + WindowTitle; }
    }

    // ==================== 主窗口 ====================
    public class MainForm : Form
    {
        // ---- 按键表 ----
        static readonly string[] KeyList = {
            "F1","F2","F3","F4","F5","F6","F7","F8",
            "1","2","3","4","5","6","7","8",
            "Q","W","E","R","T","Y","U","I","O","P",
            "A","S","D","F","G","H","J","K","L",
            "Z","X","C","V","B","N","M",
            "Space","Shift","Ctrl","Tab","Enter",
        };
        static readonly string[] MouseKeyList = {
            "鼠标右键 (Right Click)", "鼠标左键 (Left Click)", "鼠标中键 (Middle Click)",
            "鼠标X1键 (X1)", "鼠标X2键 (X2)",
        };
        static readonly Dictionary<string, ushort> VK = new Dictionary<string, ushort> {
            {"F1",0x70},{"F2",0x71},{"F3",0x72},{"F4",0x73},
            {"F5",0x74},{"F6",0x75},{"F7",0x76},{"F8",0x77},
            {"1",0x31},{"2",0x32},{"3",0x33},{"4",0x34},
            {"5",0x35},{"6",0x36},{"7",0x37},{"8",0x38},
            {"Q",0x51},{"W",0x57},{"E",0x45},{"R",0x52},
            {"T",0x54},{"Y",0x59},{"U",0x55},{"I",0x49},
            {"O",0x4F},{"P",0x50},
            {"A",0x41},{"S",0x53},{"D",0x44},{"F",0x46},
            {"G",0x47},{"H",0x48},{"J",0x4A},{"K",0x4B},
            {"L",0x4C},
            {"Z",0x5A},{"X",0x58},{"C",0x43},{"V",0x56},
            {"B",0x42},{"N",0x4E},{"M",0x4D},
            {"Space",0x20},{"Shift",0x10},{"Ctrl",0x11},
            {"Tab",0x09},{"Enter",0x0D},
            {"鼠标右键 (Right Click)",0x02},{"鼠标左键 (Left Click)",0x01},
            {"鼠标中键 (Middle Click)",0x04},{"鼠标X1键 (X1)",0x05},{"鼠标X2键 (X2)",0x06},
        };
        static readonly string[] DiabloProcesses = {
            "D2R","Diablo III","Diablo IV","Diablo IV Retail","Diablo","暗黑破坏神"
        };

        // ---- 状态枚举 ----
        enum WorkState { LISTENING, AUTO_CLICKING }

        // ---- 控件 ----
        ComboBox _cmbKey, _cmbKey2, _cmbTrigger, _cmbStop;
        TextBox _txtInterval, _txtInterval2;
        Button _btnToggle, _btnTest, _btnClearLog, _btnScan;
        Label _lblStatus, _lblCount, _lblTarget, _lblForeground, _lblAdmin;
        ListBox _logBox;
        System.Windows.Forms.Timer _pollTimer;

        // ---- 状态 ----
        volatile bool _running; volatile bool _stopReq;
        Thread _worker; int _keyCount;
        TargetInfo _target; List<TargetInfo> _targets;

        // 按键防抖
        bool _prevTrigger, _prevStop;

        // ============================================
        public MainForm()
        {
            bool isAdmin;
            try { isAdmin = new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator); }
            catch { isAdmin = false; }

            Text = "🎮 暗黑破坏神 自动按键 v3.0";
            ClientSize = new Size(620, 540);
            FormBorderStyle = FormBorderStyle.FixedSingle; MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            Font = new Font("Microsoft YaHei UI", 9F);

            _targets = new List<TargetInfo>();
            _BuildUI(isAdmin);
            _Log("程序启动 | 管理员: " + (isAdmin ? "是" : "否"));

            _pollTimer = new System.Windows.Forms.Timer { Interval = 300 };
            _pollTimer.Tick += (o, e) => _PollStatus();
            _pollTimer.Start();

            _DoScan();

            FormClosing += (o, e) => { _stopReq = true; _running = false; if (_worker != null && _worker.IsAlive) _worker.Join(1000); };
        }

        // ==================== UI ====================
        void _BuildUI(bool isAdmin)
        {
            var ct = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(12), ColumnCount = 1, RowCount = 5 };
            ct.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            ct.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            ct.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            ct.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            ct.RowStyles.Add(new RowStyle(SizeType.AutoSize));

            // 第1行: 设置
            var p1 = new Panel { Height = 130, Dock = DockStyle.Fill };
            _lblAdmin = new Label { Text = "🎮 暗黑破坏神 自动按键 v3.0" + (isAdmin ? "  [管理员]" : "  ⚠ 非管理员"), Location = new Point(0, 0), Size = new Size(590, 22), ForeColor = isAdmin ? Color.Green : Color.OrangeRed, Font = new Font("Microsoft YaHei UI", 9F, FontStyle.Bold) };
            p1.Controls.Add(_lblAdmin);

            // 行1: 按键1 + 间隔1 + 触发键
            new Label { Text = "⌨ 按键1:", Location = new Point(0, 26), Size = new Size(60, 24) }.Parent = p1;
            _cmbKey = new ComboBox { Location = new Point(60, 24), Size = new Size(80, 24), DropDownStyle = ComboBoxStyle.DropDownList };
            foreach (var k in KeyList) _cmbKey.Items.Add(k);
            _cmbKey.SelectedItem = "1";
            p1.Controls.Add(_cmbKey);

            new Label { Text = "⏱ 间隔1:", Location = new Point(148, 26), Size = new Size(58, 24) }.Parent = p1;
            _txtInterval = new TextBox { Text = "0", Location = new Point(206, 24), Size = new Size(50, 24) };
            p1.Controls.Add(_txtInterval);

            new Label { Text = "▶ 触发键:", Location = new Point(266, 26), Size = new Size(60, 24) }.Parent = p1;
            _cmbTrigger = new ComboBox { Location = new Point(326, 24), Size = new Size(140, 24), DropDownStyle = ComboBoxStyle.DropDown };
            foreach (var k in MouseKeyList) _cmbTrigger.Items.Add(k);
            foreach (var k in KeyList) _cmbTrigger.Items.Add(k);
            _cmbTrigger.Text = "F1";
            p1.Controls.Add(_cmbTrigger);

            // 行2: 按键2 + 间隔2 + 停止键
            new Label { Text = "⌨ 按键2:", Location = new Point(0, 52), Size = new Size(60, 24) }.Parent = p1;
            _cmbKey2 = new ComboBox { Location = new Point(60, 50), Size = new Size(80, 24), DropDownStyle = ComboBoxStyle.DropDown };
            foreach (var k in KeyList) _cmbKey2.Items.Add(k);
            foreach (var k in MouseKeyList) _cmbKey2.Items.Add(k);
            _cmbKey2.Text = "鼠标右键 (Right Click)";
            p1.Controls.Add(_cmbKey2);

            new Label { Text = "⏱ 间隔2:", Location = new Point(148, 52), Size = new Size(58, 24) }.Parent = p1;
            _txtInterval2 = new TextBox { Text = "3.0", Location = new Point(206, 50), Size = new Size(50, 24) };
            p1.Controls.Add(_txtInterval2);

            new Label { Text = "◼ 停止键:", Location = new Point(266, 52), Size = new Size(60, 24) }.Parent = p1;
            _cmbStop = new ComboBox { Location = new Point(326, 50), Size = new Size(140, 24), DropDownStyle = ComboBoxStyle.DropDown };
            foreach (var k in KeyList) _cmbStop.Items.Add(k);
            foreach (var k in MouseKeyList) _cmbStop.Items.Add(k);
            _cmbStop.Text = "F2";
            p1.Controls.Add(_cmbStop);

            _btnToggle = new Button { Text = "▶ 开始监听", Location = new Point(0, 100), Size = new Size(100, 27) };
            _btnToggle.Click += (o, e) => _Toggle();
            _btnTest = new Button { Text = "🔍 测试按键", Location = new Point(108, 100), Size = new Size(96, 27) };
            _btnTest.Click += (o, e) => _TestKey();
            _btnClearLog = new Button { Text = "📋 清空日志", Location = new Point(212, 100), Size = new Size(90, 27) };
            _btnClearLog.Click += (o, e) => _logBox.Items.Clear();
            _btnScan = new Button { Text = "🔎 扫描目标", Location = new Point(310, 100), Size = new Size(90, 27) };
            _btnScan.Click += (o, e) => _DoScan();
            p1.Controls.Add(_btnToggle); p1.Controls.Add(_btnTest); p1.Controls.Add(_btnClearLog); p1.Controls.Add(_btnScan);
            ct.Controls.Add(p1);

            // 第2行: 目标进程
            var p2 = new Panel { Height = 50, Dock = DockStyle.Fill };
            p2.Controls.Add(new Label { Text = "🎯 目标进程:", Location = new Point(0, 2), Size = new Size(80, 22) });
            _lblTarget = new Label { Text = "⚫ 未扫描", Location = new Point(80, 2), Size = new Size(510, 22), ForeColor = Color.Gray };
            p2.Controls.Add(_lblTarget);
            _lblForeground = new Label { Text = "  前台: ⚫ 待检测", Location = new Point(0, 24), Size = new Size(590, 22) };
            p2.Controls.Add(_lblForeground);
            ct.Controls.Add(p2);

            // 第3行: 状态
            var p3 = new Panel { Height = 48, Dock = DockStyle.Fill };
            _lblStatus = new Label { Text = "⏸ 未启动", Location = new Point(0, 0), Size = new Size(340, 22), Font = new Font("Microsoft YaHei UI", 9F, FontStyle.Bold) };
            _lblCount  = new Label { Text = "🔄 触发: 0", Location = new Point(340, 0), Size = new Size(250, 22) };
            p3.Controls.Add(_lblStatus); p3.Controls.Add(_lblCount);
            p3.Controls.Add(new Label { Text = "", BorderStyle = BorderStyle.Fixed3D, Location = new Point(0, 28), Size = new Size(590, 2) });
            ct.Controls.Add(p3);

            // 第4行: 日志
            _logBox = new ListBox { Dock = DockStyle.Fill, Font = new Font("Consolas", 9F), HorizontalScrollbar = true, IntegralHeight = false };
            ct.Controls.Add(_logBox);

            // 第5行: 提示
            ct.Controls.Add(new Label { Text = "💡 触发键和停止键可自由设置，支持鼠标和键盘按键", Height = 22, ForeColor = Color.Gray });
            Controls.Add(ct);
        }

        // ==================== 扫描 ====================
        void _DoScan()
        {
            _targets.Clear(); var seen = new HashSet<int>();
            int selfPid = Process.GetCurrentProcess().Id;
            foreach (Process p in Process.GetProcesses())
            {
                try {
                    int pid = p.Id; if (seen.Contains(pid) || pid == selfPid) continue;
                    string n = p.ProcessName, nl = n.ToLower(), t = p.MainWindowTitle;
                    bool match = false;
                    foreach (var kw in DiabloProcesses) if (nl.Contains(kw.ToLower())) { match = true; break; }
                    if (!match) continue;
                    seen.Add(pid);
                    _targets.Add(new TargetInfo { Pid = pid, ProcessName = n, WindowTitle = t, HasWindow = t != "", IsRunning = true });
                } catch { }
            }
            _Log("🔎 扫描完成, 找到 " + _targets.Count + " 个目标:");
            if (_targets.Count == 0) { _Log("  (无)"); _lblTarget.Text = "❌ 未找到"; _lblTarget.ForeColor = Color.Red; _target = null; return; }
            foreach (var t in _targets) _Log("  " + t.ToString());
            _target = _targets[0];
            _UpdateTargetDisplay();
        }

        void _UpdateTargetDisplay()
        {
            if (_target == null) { _lblTarget.Text = "❌ 未选择"; _lblTarget.ForeColor = Color.Red; return; }
            try { Process.GetProcessById(_target.Pid); _target.IsRunning = true; } catch { _target.IsRunning = false; }
            string s = (_target.IsRunning ? "🟢" : "🔴") + " " + _target.ProcessName + " PID=" + _target.Pid + " 「" + _target.WindowTitle + "」";
            _lblTarget.Text = s; _lblTarget.ForeColor = _target.IsRunning ? Color.Black : Color.Red;
        }

        // ==================== 开始/停止 ====================
        void _Toggle()
        {
            if (_running) _Stop(); else _Start();
        }

        void _Start()
        {
            double interval, interval2;
            if (!double.TryParse(_txtInterval.Text, out interval) || interval < 0)
            { MessageBox.Show("间隔1必须大于等于0", "错误"); return; }
            if (!double.TryParse(_txtInterval2.Text, out interval2) || interval2 < 0)
            { MessageBox.Show("间隔2必须大于等于0", "错误"); return; }
            if (!VK.ContainsKey(_cmbKey.Text))
            { MessageBox.Show("无效按键1", "错误"); return; }
            if (!VK.ContainsKey(_cmbKey2.Text))
            { MessageBox.Show("无效按键2", "错误"); return; }
            if (!VK.ContainsKey(_cmbTrigger.Text))
            { MessageBox.Show("无效触发键", "错误"); return; }
            if (!VK.ContainsKey(_cmbStop.Text))
            { MessageBox.Show("无效停止键", "错误"); return; }

            int triggerVk = VK[_cmbTrigger.Text];
            int stopVk = VK[_cmbStop.Text];

            _running = true; _stopReq = false; _keyCount = 0;
            _btnToggle.Text = "■ 停止";
            _lblCount.Text = "🔄 触发: 0";
            _SetStatus("🔴 监听中", Color.Crimson);
            _Log("▶ 启动 | 按键1=" + _cmbKey.Text + "(" + interval + "s)"
                + " 按键2=" + _cmbKey2.Text + "(" + interval2 + "s)"
                + " | 触发=" + _cmbTrigger.Text + " 停止=" + _cmbStop.Text);

            _worker = new Thread(() => _WorkLoop(
                interval, VK[_cmbKey.Text],
                interval2, VK[_cmbKey2.Text],
                triggerVk, stopVk
            )) { IsBackground = true };
            _worker.Start();
        }

        void _Stop()
        {
            _running = false; _stopReq = true; _btnToggle.Text = "▶ 开始监听";
            _SetStatus("⏸ 已停止", Color.Gray); _Log("⏸ 已停止");
        }

        // ==================== 核心工作线程 ====================
        void _WorkLoop(double interval, ushort vk1, double interval2, ushort vk2, int triggerVk, int stopVk)
        {
            WorkState state = WorkState.LISTENING;
            _prevTrigger = false; _prevStop = false;
            double elapsed1 = 0, elapsed2 = 0;
            bool held1 = false, held2 = false;

            while (!_stopReq)
            {
                if (!_running) { Thread.Sleep(80); continue; }

                bool active = _IsDiabloActive();

                // --- 按键检测 (通用) ---
                bool trigDown = (WinAPI.GetAsyncKeyState(triggerVk) & WinAPI.KEY_DOWN) != 0;
                bool stopDown = (WinAPI.GetAsyncKeyState(stopVk) & WinAPI.KEY_DOWN) != 0;

                bool trigPressed = trigDown && !_prevTrigger;
                _prevTrigger = trigDown;

                bool stopPressed = stopDown && !_prevStop;
                _prevStop = stopDown;

                string trigName = _cmbTrigger.Text;
                string stopName = _cmbStop.Text;

                // --- 状态机 ---
                switch (state)
                {
                    case WorkState.LISTENING:
                        if (!active)
                        {
                            _SafeSetStatus("🔴 监听中 (游戏不在前台)", Color.Gray);
                            Thread.Sleep(100);
                            continue;
                        }
                        _SafeSetStatus("🔴 监听中 — 按下 [" + trigName + "] 触发", Color.Crimson);

                        if (trigPressed && active)
                        {
                            state = WorkState.AUTO_CLICKING;
                            _SafeSetStatus("🟢 自动按键中 — 按下 [" + stopName + "] 停止", Color.Green);
                            _Log("🟢 [" + trigName + "] 触发 — 开始自动按键");
                        }
                        Thread.Sleep(80);
                        break;

                    case WorkState.AUTO_CLICKING:
                        if (!active)
                        {
                            _SafeSetStatus("🟡 自动按键中 (游戏不在前台 - 暂停)", Color.Orange);
                            Thread.Sleep(100);
                            continue;
                        }

                        if (stopPressed)
                        {
                            state = WorkState.LISTENING;
                            _SafeSetStatus("🔴 监听中 — 按下 [" + trigName + "] 触发", Color.Crimson);
                            _Log("🔴 [" + stopName + "] 停止 — 回到监听状态");
                            Thread.Sleep(200);
                            continue;
                        }

                        _SafeSetStatus("🟢 自动按键中 — 按下 [" + stopName + "] 停止", Color.Green);

                        // 两个按键独立定时器，各自按自己的间隔触发
                        double tick = 0.05;
                        bool keySent = false;
                        while (!_stopReq)
                        {
                            // 检测停止键
                            bool sCheck = (WinAPI.GetAsyncKeyState(stopVk) & WinAPI.KEY_DOWN) != 0;
                            if (sCheck && !_prevStop) { _prevStop = true; stopPressed = true; break; }
                            if (!sCheck) _prevStop = false;

                            // 切出游戏暂停计时
                            if (!_IsDiabloActive()) { Thread.Sleep(100); continue; }

                            elapsed1 += tick; elapsed2 += tick;
                            keySent = false;

                            // 0 = 按住不放, >0 = 按间隔连点
                            if (interval == 0) { if (!held1) { _KeyDown(vk1); held1 = true; keySent = true; } }
                            else if (elapsed1 >= interval) { _PressKey(vk1); elapsed1 -= interval; keySent = true; }
                            if (interval2 == 0) { if (!held2) { _KeyDown(vk2); held2 = true; keySent = true; } }
                            else if (elapsed2 >= interval2) { _PressKey(vk2); elapsed2 -= interval2; keySent = true; }

                            if (keySent)
                            {
                                Interlocked.Increment(ref _keyCount);
                                BeginInvoke((Action)(() => _lblCount.Text = "🔄 触发: " + _keyCount));
                            }

                            int ms = (int)(tick * 1000);
                            Thread.Sleep(ms);
                        }

                        if (stopPressed)
                        {
                            // 释放按住未放的键
                            if (held1) { _KeyUp(vk1); held1 = false; }
                            if (held2) { _KeyUp(vk2); held2 = false; }
                            state = WorkState.LISTENING;
                            _SafeSetStatus("🔴 监听中 — 按下 [" + trigName + "] 触发", Color.Crimson);
                            _Log("🔴 [" + stopName + "] 停止 — 回到监听状态");
                            stopPressed = false;
                            Thread.Sleep(200);
                        }
                        break;
                }
            }
            // 线程退出时释放按住未放的键
            if (held1) { _KeyUp(vk1); held1 = false; }
            if (held2) { _KeyUp(vk2); held2 = false; }
        }

        // ==================== 工具方法 ====================
        bool _IsDiabloActive()
        {
            if (_target == null || !_target.IsRunning)
            { string t = _GetForegroundTitle(); return t.Contains("暗黑") || t.Contains("Diablo"); }
            uint pid; WinAPI.GetWindowThreadProcessId(WinAPI.GetForegroundWindow(), out pid);
            return pid == _target.Pid;
        }

        string _GetForegroundTitle()
        { var sb = new StringBuilder(256); WinAPI.GetWindowText(WinAPI.GetForegroundWindow(), sb, sb.Capacity); return sb.ToString(); }

        uint _KeyDown(ushort vk)
        {
            if (vk <= 6) {
                uint f = 0;
                switch (vk) { case 0x01: f = WinAPI.MOUSEEVENTF_LEFTDOWN; break; case 0x02: f = WinAPI.MOUSEEVENTF_RIGHTDOWN; break; case 0x04: f = WinAPI.MOUSEEVENTF_MIDDLEDOWN; break; case 0x05: case 0x06: f = WinAPI.MOUSEEVENTF_XDOWN; break; }
                var inp = new WinAPI.INPUT[1]; inp[0].type = WinAPI.INPUT_MOUSE; inp[0].mi.dwFlags = f; return WinAPI.SendInput(1, inp, Marshal.SizeOf(typeof(WinAPI.INPUT)));
            }
            var inp2 = new WinAPI.INPUT[1]; inp2[0].type = WinAPI.INPUT_KEYBOARD; inp2[0].ki.wVk = vk; return WinAPI.SendInput(1, inp2, Marshal.SizeOf(typeof(WinAPI.INPUT)));
        }

        uint _KeyUp(ushort vk)
        {
            if (vk <= 6) {
                uint f = 0;
                switch (vk) { case 0x01: f = WinAPI.MOUSEEVENTF_LEFTUP; break; case 0x02: f = WinAPI.MOUSEEVENTF_RIGHTUP; break; case 0x04: f = WinAPI.MOUSEEVENTF_MIDDLEUP; break; case 0x05: case 0x06: f = WinAPI.MOUSEEVENTF_XUP; break; }
                var inp = new WinAPI.INPUT[1]; inp[0].type = WinAPI.INPUT_MOUSE; inp[0].mi.dwFlags = f; return WinAPI.SendInput(1, inp, Marshal.SizeOf(typeof(WinAPI.INPUT)));
            }
            var inp2 = new WinAPI.INPUT[1]; inp2[0].type = WinAPI.INPUT_KEYBOARD; inp2[0].ki.wVk = vk; inp2[0].ki.dwFlags = WinAPI.KEYEVENTF_KEYUP; return WinAPI.SendInput(1, inp2, Marshal.SizeOf(typeof(WinAPI.INPUT)));
        }

        uint _PressKey(ushort vk)
        {
            _KeyDown(vk); _KeyUp(vk); return 2;
        }

        void _TestKey()
        {
            if (!VK.ContainsKey(_cmbKey.Text)) { MessageBox.Show("无效按键", "错误"); return; }
            ushort vk = VK[_cmbKey.Text];
            string t = _GetForegroundTitle(); uint fgPid;
            WinAPI.GetWindowThreadProcessId(WinAPI.GetForegroundWindow(), out fgPid);
            bool matchByPid = (_target != null && _target.IsRunning && fgPid == _target.Pid);
            bool matchByTitle = t.Contains("暗黑") || t.Contains("Diablo");
            uint r = _PressKey(vk);
            _Log("🔍 [测试] 发送 " + _cmbKey.Text + " | SendInput=" + r
                + " | 前台PID=" + fgPid + " | 目标PID=" + (_target != null ? _target.Pid.ToString() : "无")
                + " | PID匹配=" + (matchByPid ? "✅" : "❌") + " | 标题匹配=" + (matchByTitle ? "✅" : "❌")
                + " | 「" + (t.Length > 30 ? t.Substring(0, 30) + "..." : t) + "」");
        }

        void _PollStatus()
        {
            if (IsDisposed) return;
            if (_target != null) { try { Process.GetProcessById(_target.Pid); _target.IsRunning = true; } catch { _target.IsRunning = false; } _UpdateTargetDisplay(); }
            string t = _GetForegroundTitle(); uint fgPid;
            WinAPI.GetWindowThreadProcessId(WinAPI.GetForegroundWindow(), out fgPid);
            bool match;
            if (_target != null && _target.IsRunning) { match = (fgPid == _target.Pid); }
            else { match = t.Contains("暗黑") || t.Contains("Diablo"); }
            _lblForeground.Text = "🪟 前台: PID=" + fgPid + (match ? " ✅ 匹配" : " ❌ 不匹配")
                + "  「" + (t.Length > 40 ? t.Substring(0, 40) + "..." : t) + "」";
        }

        void _SetStatus(string text, Color c) { _lblStatus.Text = text; _lblStatus.ForeColor = c; }

        void _SafeSetStatus(string text, Color c)
        {
            BeginInvoke((Action)(() => { _lblStatus.Text = text; _lblStatus.ForeColor = c; }));
        }

        void _Log(string msg)
        {
            string line = "[" + DateTime.Now.ToString("HH:mm:ss") + "] " + msg;
            if (IsHandleCreated) BeginInvoke((Action)(() => { _logBox.Items.Add(line); _logBox.TopIndex = _logBox.Items.Count - 1; }));
            else _logBox.Items.Add(line);
        }

        void _SafeLog(string msg)
        {
            if (_stopReq) return;
            string line = "[" + DateTime.Now.ToString("HH:mm:ss") + "] " + msg;
            try { if (IsHandleCreated) BeginInvoke((Action)(() => { _logBox.Items.Add(line); _logBox.TopIndex = _logBox.Items.Count - 1; })); } catch { }
        }
    }

    // ==================== 入口 ====================
    static class Program
    {
        [STAThread]
        static void Main()
        { Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false); Application.Run(new MainForm()); }
    }
}
