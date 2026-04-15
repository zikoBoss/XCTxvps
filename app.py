import os
import sys
import resource
import gc
import threading
import time
import psutil
import socket
import platform
import re
import base64
import uuid
import ast
import signal
import warnings
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for, send_file
import subprocess
import json
import shutil
import zipfile
import tarfile
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict

warnings.filterwarnings('ignore')

# ============================================================
# إعدادات الموارد غير المحدودة
# ============================================================
def set_unlimited_resources():
    """تعيين موارد غير محدودة للنظام"""
    try:
        resource.setrlimit(resource.RLIMIT_AS, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        resource.setrlimit(resource.RLIMIT_DATA, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        resource.setrlimit(resource.RLIMIT_STACK, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        resource.setrlimit(resource.RLIMIT_NOFILE, (999999, 999999))
        resource.setrlimit(resource.RLIMIT_NPROC, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        print("[🔥 UNLIMITED] Resource limits removed - INFINITY MODE ACTIVE")
        return True
    except Exception as e:
        print(f"[⚠️ UNLIMITED] Partial mode: {e}")
        return False

UNLIMITED_ACTIVE = set_unlimited_resources()

def unlimited_memory_monitor():
    """مراقبة وتحرير الذاكرة بشكل مستمر"""
    while True:
        time.sleep(30)
        try:
            gc.collect()
            try:
                with open('/proc/sys/vm/drop_caches', 'w') as f:
                    f.write('3')
            except:
                pass
        except:
            pass

threading.Thread(target=unlimited_memory_monitor, daemon=True).start()

# ============================================================
# إعدادات Flask
# ============================================================
app = Flask(__name__)
app.secret_key = secrets.token_hex(64)
app.permanent_session_lifetime = timedelta(days=30)
app.config['MAX_CONTENT_LENGTH'] = None
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# ============================================================
# المسارات والإعدادات الأساسية
# ============================================================
BASE_PATH = '/home/container'
USERS_FOLDER = os.path.join(BASE_PATH, 'users_data')
USERS_FILE = os.path.join(BASE_PATH, 'users.json')
PROCESSES_FILE = os.path.join(BASE_PATH, 'processes.json')
SCHEDULES_FILE = os.path.join(BASE_PATH, 'schedules.json')
LOGS_FILE = os.path.join(BASE_PATH, 'activity.log')
USER_SESSIONS_FILE = os.path.join(BASE_PATH, 'user_sessions.json')
BACKUPS_FOLDER = os.path.join(BASE_PATH, 'backups')
TEMP_FOLDER = os.path.join(BASE_PATH, 'temp')
PACKAGES_FILE = os.path.join(BASE_PATH, 'packages.json')
NETWORK_STATS_FILE = os.path.join(BASE_PATH, 'network_stats.json')
DOCKER_FILE = os.path.join(BASE_PATH, 'docker.json')

MASTER_USERNAME = "VeNoM"
MASTER_PASSWORD_HASH = hashlib.sha256("VeNoM".encode()).hexdigest()

# إنشاء المجلدات الأساسية
for folder in [USERS_FOLDER, TEMP_FOLDER, BACKUPS_FOLDER,
               os.path.join(BASE_PATH, 'docker'), os.path.join(BASE_PATH, 'scripts')]:
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

# ============================================================
# دوال مساعدة للملفات
# ============================================================
def init_json_file(file_path, default_data):
    if not os.path.exists(file_path):
        with open(file_path, 'w') as f:
            json.dump(default_data, f, indent=2)

init_json_file(USERS_FILE, {})
init_json_file(PROCESSES_FILE, {})
init_json_file(SCHEDULES_FILE, {})
init_json_file(USER_SESSIONS_FILE, {})
init_json_file(PACKAGES_FILE, {'pip': [], 'apt': [], 'custom': []})
init_json_file(NETWORK_STATS_FILE, {'history': [], 'total_in': 0, 'total_out': 0})
init_json_file(DOCKER_FILE, {'containers': [], 'images': []})

def log_activity(username, action, details=""):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOGS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] [{username}] {action} | {details}\n")
    except:
        pass

def load_json_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_json_file(file_path, data):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[ERROR] Save failed: {e}")
        return False

def load_users():
    return load_json_file(USERS_FILE)

def save_users(users):
    save_json_file(USERS_FILE, users)

def load_processes():
    return load_json_file(PROCESSES_FILE)

def save_processes(processes):
    save_json_file(PROCESSES_FILE, processes)

def load_schedules():
    return load_json_file(SCHEDULES_FILE)

def save_schedules(schedules):
    save_json_file(SCHEDULES_FILE, schedules)

def load_user_sessions():
    return load_json_file(USER_SESSIONS_FILE)

def save_user_sessions(sessions):
    save_json_file(USER_SESSIONS_FILE, sessions)

def load_packages():
    return load_json_file(PACKAGES_FILE)

def save_packages(packages):
    save_json_file(PACKAGES_FILE, packages)

def get_user_path(username):
    if username == MASTER_USERNAME:
        return BASE_PATH
    return os.path.join(USERS_FOLDER, username)

def ensure_user_folder(username):
    if username == MASTER_USERNAME:
        return
    user_path = get_user_path(username)
    if not os.path.exists(user_path):
        os.makedirs(user_path, exist_ok=True)
        welcome_file = os.path.join(user_path, 'welcome.txt')
        with open(welcome_file, 'w', encoding='utf-8') as f:
            f.write(f"""🎉 Welcome to UNLIMITED VPS!
👤 Username: {username}
📅 Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔥 Resources: UNLIMITED

📚 Quick Commands:
  • python3 -m pip install <package>
  • apt-get install <package>
  • git clone <repo>

💡 Enjoy unlimited resources!
""")

def is_path_allowed(username, requested_path):
    if username == MASTER_USERNAME:
        return True
    user_path = get_user_path(username)
    try:
        real_requested = os.path.realpath(requested_path)
        real_user_path = os.path.realpath(user_path)
        return real_requested.startswith(real_user_path) or real_requested == real_user_path
    except:
        return False

def can_user_login(username):
    sessions = load_user_sessions()
    user_config = load_users().get(username, {})
    max_sessions = user_config.get('max_sessions', 999) if isinstance(user_config, dict) else 999
    return sessions.get(username, 0) < max_sessions

def register_session(username):
    sessions = load_user_sessions()
    sessions[username] = sessions.get(username, 0) + 1
    save_user_sessions(sessions)

def unregister_session(username):
    sessions = load_user_sessions()
    if username in sessions and sessions[username] > 0:
        sessions[username] -= 1
    save_user_sessions(sessions)

def get_system_stats():
    try:
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(BASE_PATH)
        net_io = psutil.net_io_counters()
        
        return {
            'cpu': psutil.cpu_percent(interval=0.1),
            'memory': {
                'total': mem.total,
                'available': mem.available,
                'used': mem.used,
                'percent': mem.percent
            },
            'disk': {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': disk.percent
            },
            'network': {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv
            },
            'uptime': time.time() - psutil.boot_time(),
            'processes': len(psutil.pids()),
            'hostname': socket.gethostname(),
            'platform': platform.platform(),
            'python_version': platform.python_version()
        }
    except Exception as e:
        return {'error': str(e)}

def auto_install_dependencies(filepath):
    """تحليل الملف وتثبيت المكتبات المطلوبة تلقائياً"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        packages = []
        if filepath.endswith('.py'):
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            packages.append(alias.name.split('.')[0])
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            packages.append(node.module.split('.')[0])
            except:
                packages = re.findall(r'^(?:import|from)\s+(\w+)', content, re.MULTILINE)
                
        elif filepath.endswith('.js'):
            packages = re.findall(r'require\([\'"]([^\'"]+)[\'"]\)', content)
            packages.extend(re.findall(r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]', content))
            
        elif filepath.endswith('requirements.txt'):
            with open(filepath, 'r') as f:
                packages = [p.strip().split('==')[0].split('>=')[0].split('<=')[0] for p in f.readlines() if p.strip()]
        
        # المكتبات الأساسية التي لا تحتاج تثبيت
        std_libs = ['os', 'sys', 'time', 'json', 're', 'math', 'random', 'datetime', 
                    'threading', 'subprocess', 'collections', 'io', 'typing', 'abc',
                    'flask', 'requests', 'numpy', 'pandas', 'psutil']
        
        installed = []
        for pkg in set(packages):
            if pkg and not pkg.startswith('.') and pkg not in std_libs:
                try:
                    subprocess.run([sys.executable, '-m', 'pip', 'install', pkg], 
                                 capture_output=True, timeout=60, check=False)
                    installed.append(pkg)
                    print(f"[AUTO-INSTALL] ✅ {pkg}")
                except:
                    pass
        return installed
    except Exception as e:
        print(f"[AUTO-INSTALL ERROR] {e}")
        return []

# ============================================================
# متغيرات العمليات المشغلة
# ============================================================
running_processes = {}
file_processes = {}

# ============================================================
# دوال الديكوريتور (الصلاحيات)
# ============================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def master_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or session.get('username') != MASTER_USERNAME:
            return jsonify({'success': False, 'error': 'Access denied. Master only.'}), 403
        return f(*args, **kwargs)
    return decorated_function

# ============================================================
# قالب HTML الرئيسي (مع 3 أشرطة جانبية)
# ============================================================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ˣᶜᵀ 𝒙 𝑻𝒆𝒂𝑴 - UNLIMITED VPS ∞</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🔥</text></svg>">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 50%, #0d1329 100%);
            font-family: 'Cairo', 'Segoe UI', 'Tahoma', sans-serif;
            color: #00ffcc;
            min-height: 100vh;
        }
        
        /* ===== الأشرطة الجانبية ===== */
        .sidebar {
            height: 100%;
            width: 0;
            position: fixed;
            z-index: 1000;
            top: 0;
            right: 0;
            background: linear-gradient(145deg, #0a0e27, #1a1f3a);
            overflow-x: hidden;
            transition: 0.3s;
            padding-top: 60px;
            border-right: 1px solid #00ffcc;
            box-shadow: -5px 0 20px rgba(0,0,0,0.5);
        }
        
        .sidebar.active {
            width: 320px;
        }
        
        .sidebar-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 20px;
            border-bottom: 1px solid #00ffcc55;
            position: absolute;
            top: 0;
            right: 0;
            left: 0;
        }
        
        .sidebar-header h3 {
            color: #ff66cc;
            text-shadow: 0 0 10px #ff66cc88;
        }
        
        .sidebar .close-btn {
            font-size: 30px;
            background: none;
            border: none;
            color: #00ffcc;
            cursor: pointer;
            padding: 0 10px;
        }
        
        .sidebar .close-btn:hover {
            color: #ff66cc;
        }
        
        .sidebar ul {
            list-style: none;
            padding: 0;
        }
        
        .sidebar ul li {
            padding: 15px 25px;
            font-size: 1.1em;
            border-bottom: 1px solid #00ffcc22;
            cursor: pointer;
            transition: 0.2s;
        }
        
        .sidebar ul li:hover {
            background: #00ffcc22;
            padding-right: 35px;
        }
        
        .profile-content {
            padding: 20px;
        }
        
        /* ===== الشريط العلوي ===== */
        .top-bar {
            display: flex;
            align-items: center;
            padding: 12px 20px;
            background: rgba(0,0,0,0.8);
            border-bottom: 1px solid #00ffcc;
            position: sticky;
            top: 0;
            z-index: 100;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .menu-btn {
            background: #00ffcc22;
            border: 1px solid #00ffcc;
            color: #00ffcc;
            padding: 10px 18px;
            margin: 0 5px;
            border-radius: 8px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .menu-btn:hover {
            background: #00ffcc;
            color: #0a0e27;
            transform: translateY(-2px);
        }
        
        .top-title {
            flex: 1;
            text-align: center;
            font-size: 1.3em;
            font-weight: bold;
            background: linear-gradient(90deg, #00ffcc, #ff66cc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .back-btn {
            background: #ffcc0022;
            border: 1px solid #ffcc00;
            color: #ffcc00;
            padding: 10px 18px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .back-btn:hover {
            background: #ffcc00;
            color: #0a0e27;
        }
        
        .logout-btn {
            background: linear-gradient(45deg, #dc3545, #ff6b6b);
            color: white;
            border: none;
            padding: 10px 18px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .logout-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 15px #dc354555;
        }
        
        /* ===== المحتوى الرئيسي ===== */
        .main-content {
            padding: 20px;
            max-width: 1600px;
            margin: 0 auto;
        }
        
        /* ===== بطاقات الإحصائيات ===== */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }
        
        .stat-card {
            background: linear-gradient(145deg, rgba(0,0,0,0.8), rgba(20,20,40,0.8));
            border: 1px solid #00ffcc55;
            border-radius: 12px;
            padding: 15px;
            text-align: center;
            transition: all 0.3s;
        }
        
        .stat-card:hover {
            transform: translateY(-3px);
            border-color: #00ffcc;
            box-shadow: 0 5px 20px #00ffcc33;
        }
        
        .stat-label { font-size: 0.85em; color: #aaa; margin-bottom: 5px; }
        .stat-value { font-size: 1.8em; font-weight: bold; color: #00ffcc; }
        .stat-sub { font-size: 0.75em; color: #888; }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #333;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 10px;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #00ffcc, #00ff88);
            width: 0%;
            transition: width 0.5s;
        }
        
        /* ===== التبويبات ===== */
        .tabs-container {
            background: rgba(0,0,0,0.6);
            border: 1px solid #00ffcc44;
            border-radius: 15px;
            padding: 20px;
            min-height: 450px;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        /* ===== الأزرار ===== */
        button, .btn {
            background: linear-gradient(145deg, #0a0e27, #1a1f3a);
            border: 1px solid #00ffcc;
            color: #00ffcc;
            padding: 8px 16px;
            border-radius: 8px;
            cursor: pointer;
            margin: 3px;
            transition: all 0.3s;
            font-size: 0.9em;
        }
        
        button:hover, .btn:hover {
            background: #00ffcc;
            color: #0a0e27;
            transform: translateY(-2px);
        }
        
        .success-btn {
            background: linear-gradient(45deg, #28a745, #5cb85c);
            color: white;
            border: none;
        }
        
        .danger-btn {
            background: linear-gradient(45deg, #dc3545, #ff6b6b);
            color: white;
            border: none;
        }
        
        .master-btn {
            background: linear-gradient(45deg, #ff66cc, #ff3399);
            color: white;
            border: none;
        }
        
        /* ===== المدخلات ===== */
        input, textarea, select {
            background: rgba(10,14,39,0.9);
            border: 1px solid #00ffcc55;
            color: #00ffcc;
            padding: 10px 14px;
            border-radius: 8px;
            margin: 3px;
            font-family: inherit;
        }
        
        input:focus, textarea:focus, select:focus {
            outline: none;
            border-color: #00ffcc;
            box-shadow: 0 0 10px #00ffcc33;
        }
        
        /* ===== التيرمنال ===== */
        .terminal {
            background: #000;
            color: #00ff00;
            font-family: 'Courier New', monospace;
            padding: 15px;
            height: 350px;
            overflow-y: auto;
            white-space: pre-wrap;
            font-size: 0.85em;
            border-radius: 10px;
            border: 1px solid #00ff0055;
        }
        
        /* ===== قائمة الملفات ===== */
        .file-list { list-style: none; }
        .file-item {
            padding: 12px;
            border-bottom: 1px solid #00ffcc22;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            transition: all 0.2s;
        }
        .file-item:hover { background: rgba(0,255,204,0.05); }
        
        .running-indicator {
            color: #28a745;
            font-size: 0.75em;
            animation: blink 1s infinite;
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        /* ===== متجاوب ===== */
        @media (max-width: 768px) {
            .top-bar { flex-direction: column; }
            .top-title { font-size: 1em; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            .sidebar.active { width: 280px; }
        }
        
        .unlimited-badge {
            background: linear-gradient(45deg, #ff6600, #ff9900);
            color: black;
            padding: 3px 12px;
            border-radius: 20px;
            font-size: 0.75em;
            font-weight: bold;
            animation: pulse 1.5s infinite;
            display: inline-block;
        }
        
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }
        
        hr {
            border: none;
            border-top: 1px solid #00ffcc33;
            margin: 15px 0;
        }
    </style>
</head>
<body>
    <!-- الشريط العلوي مع 3 أزرار -->
    <div class="top-bar">
        <button class="menu-btn" onclick="toggleSidebar('mainMenu')">☰ القائمة الرئيسية</button>
        <button class="menu-btn" onclick="toggleSidebar('profileMenu'); loadProfileData()">👤 الملف الشخصي</button>
        <button class="menu-btn" onclick="toggleSidebar('toolsMenu')">⚙️ أدوات سريعة</button>
        <span class="top-title">🔥 ˣᶜᵀ 𝒙 𝑻𝒆𝒂𝑴 <span class="unlimited-badge">∞ UNLIMITED</span></span>
        <button onclick="goBack()" class="back-btn">↩️ رجوع</button>
        <a href="/logout"><button class="logout-btn">🚪 خروج</button></a>
    </div>

    <!-- الشريط الجانبي 1: القائمة الرئيسية -->
    <div id="mainMenu" class="sidebar">
        <div class="sidebar-header">
            <h3>📋 القائمة الرئيسية</h3>
            <button class="close-btn" onclick="toggleSidebar('mainMenu')">×</button>
        </div>
        <ul>
            <li onclick="showTab('files'); toggleSidebar('mainMenu')">📁 مستعرض الملفات</li>
            <li onclick="showTab('terminal'); toggleSidebar('mainMenu')">🖥️ تنفيذ الأوامر</li>
            <li onclick="showTab('processes'); toggleSidebar('mainMenu')">⚙️ إدارة العمليات</li>
            <li onclick="showTab('network'); toggleSidebar('mainMenu')">🌐 الشبكة والمنافذ</li>
            <li onclick="showTab('editor'); toggleSidebar('mainMenu')">📝 محرر الأكواد</li>
            <li onclick="showTab('info'); toggleSidebar('mainMenu')">ℹ️ معلومات النظام</li>
            {% if session.username == 'VeNoM' %}
                <hr>
                <li onclick="showTab('users'); toggleSidebar('mainMenu')">👑 إدارة المستخدمين</li>
                <li onclick="showTab('schedules'); toggleSidebar('mainMenu')">⏰ المهام المجدولة</li>
                <li onclick="showTab('backups'); toggleSidebar('mainMenu')">💾 النسخ الاحتياطي</li>
                <li onclick="showTab('packages'); toggleSidebar('mainMenu')">📦 إدارة الحزم</li>
                <li onclick="showTab('docker'); toggleSidebar('mainMenu')">🐳 Docker</li>
                <li onclick="showTab('logs'); toggleSidebar('mainMenu')">📝 سجل النشاطات</li>
            {% endif %}
        </ul>
    </div>

    <!-- الشريط الجانبي 2: الملف الشخصي -->
    <div id="profileMenu" class="sidebar">
        <div class="sidebar-header">
            <h3>👤 الملف الشخصي</h3>
            <button class="close-btn" onclick="toggleSidebar('profileMenu')">×</button>
        </div>
        <div class="profile-content">
            <div style="text-align:center; font-size:4em;">👤</div>
            <h2 style="text-align:center; color:#ff66cc;">{{ session.username }}</h2>
            <hr>
            <div id="profileDetails">
                <p style="text-align:center;">⏳ جاري تحميل البيانات...</p>
            </div>
            <hr>
            <h4>📊 استهلاك الموارد</h4>
            <div id="userResourceUsage"></div>
        </div>
    </div>

    <!-- الشريط الجانبي 3: الأدوات السريعة -->
    <div id="toolsMenu" class="sidebar">
        <div class="sidebar-header">
            <h3>⚡ أدوات سريعة</h3>
            <button class="close-btn" onclick="toggleSidebar('toolsMenu')">×</button>
        </div>
        <ul>
            <li onclick="runQuickAction('update'); toggleSidebar('toolsMenu')">🔄 تحديث النظام</li>
            <li onclick="runQuickAction('clean'); toggleSidebar('toolsMenu')">🧹 تنظيف الكاش</li>
            <li onclick="showTab('network'); toggleSidebar('toolsMenu'); setTimeout(() => document.getElementById('scanHost').focus(), 300);">🔍 فحص المنافذ</li>
            <li onclick="createBackupPrompt(); toggleSidebar('toolsMenu')">💾 إنشاء نسخة احتياطية</li>
            <li onclick="killAllProcesses(); toggleSidebar('toolsMenu')">⏹️ إيقاف جميع العمليات</li>
        </ul>
    </div>

    <!-- المحتوى الرئيسي -->
    <div class="main-content">
        <!-- إحصائيات النظام -->
        <div class="stats-grid" id="stats">
            <div class="stat-card">
                <div class="stat-label">💻 المعالج</div>
                <div class="stat-value" id="cpu">0%</div>
                <div class="progress-bar"><div class="progress-fill" id="cpuFill"></div></div>
            </div>
            <div class="stat-card">
                <div class="stat-label">🧠 الذاكرة</div>
                <div class="stat-value" id="ram">0%</div>
                <div class="stat-sub" id="ramText">0 / 0 GB</div>
                <div class="progress-bar"><div class="progress-fill" id="ramFill"></div></div>
            </div>
            <div class="stat-card">
                <div class="stat-label">💾 القرص</div>
                <div class="stat-value" id="disk">0%</div>
                <div class="progress-bar"><div class="progress-fill" id="diskFill"></div></div>
            </div>
            <div class="stat-card">
                <div class="stat-label">⏱️ مدة التشغيل</div>
                <div class="stat-value" id="uptime">0h</div>
                <div class="stat-sub" id="uptimeFull">0d 0h 0m</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">🔄 العمليات</div>
                <div class="stat-value" id="processes">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">🌐 الشبكة</div>
                <div class="stat-value" id="netSpeed">0 KB/s</div>
                <div class="stat-sub">↓ <span id="netIn">0</span> MB | ↑ <span id="netOut">0</span> MB</div>
            </div>
        </div>

        <!-- التبويبات -->
        <div class="tabs-container">
            <!-- تبويب الملفات -->
            <div id="files" class="tab-content active">
                <div style="margin-bottom:15px; display:flex; flex-wrap:wrap; gap:8px; align-items:center;">
                    <input type="file" id="uploadFile" multiple style="max-width:200px;">
                    <button onclick="uploadFiles()" class="success-btn">📤 رفع</button>
                    <button onclick="refreshFiles()">🔄 تحديث</button>
                    <button onclick="createFolder()">📁 مجلد جديد</button>
                    <button onclick="createFile()">📄 ملف جديد</button>
                    <button onclick="downloadSelected()">⬇️ تحميل</button>
                    <span style="margin-right:auto;">📍 <span id="currentPathDisplay"></span></span>
                </div>
                <div id="fileBrowser"></div>
            </div>

            <!-- تبويب التيرمنال -->
            <div id="terminal" class="tab-content">
                <div class="terminal" id="terminalOutput">
$ ========================================
$ 🔥 ˣᶜᵀ 𝒙 𝑻𝒆𝒂𝑴 UNLIMITED VPS 🔥
$ ========================================
                </div>
                <div style="display:flex; margin-top:10px; gap:8px;">
                    <span style="color:#00ffcc; padding:10px;">$</span>
                    <input type="text" id="cmdInput" placeholder="أدخل الأمر..." style="flex:1;" onkeypress="if(event.keyCode==13) execCommand()">
                    <button onclick="execCommand()" class="success-btn">⚡ تنفيذ</button>
                    <button onclick="clearTerminal()">🗑️ مسح</button>
                </div>
            </div>

            <!-- تبويب العمليات -->
            <div id="processes" class="tab-content">
                <div style="margin-bottom:15px; display:flex; flex-wrap:wrap; gap:8px;">
                    <input type="text" id="procName" placeholder="اسم العملية" style="width:150px;">
                    <input type="text" id="procCommand" placeholder="الأمر (مثال: python3 bot.py)" style="width:350px;">
                    <button onclick="startProcess()" class="success-btn">▶️ تشغيل</button>
                    <button onclick="refreshProcesses()">🔄 تحديث</button>
                    <button onclick="killAllProcesses()" class="danger-btn">⏹️ إيقاف الكل</button>
                </div>
                <div id="processList"></div>
            </div>

            <!-- تبويب الشبكة -->
            <div id="network" class="tab-content">
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px;">
                    <div>
                        <h3>🌐 إحصائيات الشبكة</h3>
                        <div id="networkStats"></div>
                    </div>
                    <div>
                        <h3>🔍 فاحص المنافذ</h3>
                        <input type="text" id="scanHost" placeholder="المضيف" value="localhost">
                        <input type="text" id="scanPorts" placeholder="المنافذ" value="80,443,8080,3000,5000,8000">
                        <button onclick="scanPorts()">🔍 فحص</button>
                        <div id="scanResults" style="margin-top:15px;"></div>
                    </div>
                </div>
            </div>

            <!-- تبويب المحرر -->
            <div id="editor" class="tab-content">
                <div style="margin-bottom:15px; display:flex; flex-wrap:wrap; gap:8px;">
                    <input type="text" id="editFilePath" placeholder="مسار الملف..." style="flex:1;">
                    <button onclick="loadFileForEdit()">📂 تحميل</button>
                    <button onclick="saveFileFromEditor()" class="success-btn">💾 حفظ</button>
                    <select id="editorLang">
                        <option value="python">Python</option>
                        <option value="javascript">JavaScript</option>
                        <option value="html">HTML</option>
                        <option value="css">CSS</option>
                        <option value="json">JSON</option>
                        <option value="bash">Bash</option>
                    </select>
                </div>
                <textarea id="codeEditor" style="width:100%; min-height:400px; background:#0a0e27; color:#00ffcc; font-family:'Courier New',monospace; padding:15px; border:1px solid #00ffcc55; border-radius:8px;" placeholder="// اختر ملف أو ابدأ البرمجة..."></textarea>
            </div>

            <!-- تبويب معلومات النظام -->
            <div id="info" class="tab-content">
                <pre id="sysInfo" style="background:#0a0e27; padding:20px; border-radius:10px; overflow-x:auto; font-size:0.9em; color:#00ffcc;"></pre>
            </div>

            {% if session.username == 'VeNoM' %}
            <!-- تبويب المستخدمين -->
            <div id="users" class="tab-content">
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px;">
                    <div>
                        <h3>➕ إضافة مستخدم</h3>
                        <input type="text" id="newUsername" placeholder="اسم المستخدم" style="width:100%;">
                        <input type="password" id="newPassword" placeholder="كلمة المرور" style="width:100%;">
                        <input type="number" id="maxSessions" placeholder="الحد الأقصى للجلسات" value="999" style="width:100%;">
                        <input type="date" id="expiryDate" placeholder="تاريخ الانتهاء" style="width:100%;">
                        <button onclick="addUser()" class="success-btn">➕ إضافة</button>
                    </div>
                    <div>
                        <h3>👥 المستخدمين</h3>
                        <div id="userList"></div>
                    </div>
                </div>
            </div>

            <!-- تبويب المهام المجدولة -->
            <div id="schedules" class="tab-content">
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px;">
                    <div>
                        <h3>⏰ إضافة مهمة</h3>
                        <input type="text" id="cronName" placeholder="اسم المهمة" style="width:100%;">
                        <input type="text" id="cronCommand" placeholder="الأمر" style="width:100%;">
                        <input type="text" id="cronSchedule" placeholder="الجدول (*/5 * * * *)" value="*/5 * * * *" style="width:100%;">
                        <button onclick="addSchedule()" class="success-btn">➕ إضافة</button>
                    </div>
                    <div>
                        <h3>📋 المهام النشطة</h3>
                        <div id="scheduleList"></div>
                    </div>
                </div>
            </div>

            <!-- تبويب النسخ الاحتياطي -->
            <div id="backups" class="tab-content">
                <div style="margin-bottom:15px;">
                    <button onclick="createBackup()" class="success-btn">💾 إنشاء نسخة</button>
                    <button onclick="refreshBackups()">🔄 تحديث</button>
                </div>
                <div id="backupList"></div>
            </div>

            <!-- تبويب الحزم -->
            <div id="packages" class="tab-content">
                <div style="margin-bottom:15px;">
                    <input type="text" id="pipPackage" placeholder="pip package">
                    <button onclick="installPip()" class="success-btn">📥 تثبيت pip</button>
                </div>
                <div id="packageList"></div>
            </div>

            <!-- تبويب Docker -->
            <div id="docker" class="tab-content">
                <div style="margin-bottom:15px;">
                    <input type="text" id="dockerImage" placeholder="الصورة (nginx:latest)">
                    <input type="text" id="dockerName" placeholder="اسم الحاوية">
                    <button onclick="runDocker()" class="success-btn">🐳 تشغيل</button>
                    <button onclick="refreshDocker()">🔄 تحديث</button>
                </div>
                <div id="dockerContainers"></div>
            </div>

            <!-- تبويب السجلات -->
            <div id="logs" class="tab-content">
                <div style="margin-bottom:15px;">
                    <button onclick="refreshLogs()">🔄 تحديث</button>
                    <button onclick="clearLogs()" class="danger-btn">🗑️ مسح</button>
                </div>
                <pre id="logViewer" style="background:#0a0e27; padding:15px; border-radius:10px; max-height:400px; overflow-y:auto; font-size:0.8em; color:#00ffcc;"></pre>
            </div>
            {% endif %}
        </div>
    </div>

    <script>
        let currentPath = '{{ user_path }}';
        let runningFileProcesses = {};
        
        // ===== دوال الأشرطة الجانبية =====
        function toggleSidebar(id) {
            const sidebar = document.getElementById(id);
            sidebar.classList.toggle('active');
        }
        
        window.onclick = function(event) {
            if (!event.target.matches('.menu-btn') && !event.target.closest('.sidebar')) {
                document.querySelectorAll('.sidebar').forEach(s => s.classList.remove('active'));
            }
        }
        
        // ===== تحميل بيانات الملف الشخصي =====
        async function loadProfileData() {
            try {
                const res = await fetch('/api/profile');
                const data = await res.json();
                document.getElementById('profileDetails').innerHTML = `
                    <p><strong>📅 تاريخ الإنشاء:</strong><br>${data.created || 'غير معروف'}</p>
                    <p><strong>⏰ تاريخ الانتهاء:</strong><br>${data.expiry || '∞ غير محدود'}</p>
                    <p><strong>🔢 الحد الأقصى للجلسات:</strong><br>${data.max_sessions || 999}</p>
                    <p><strong>📂 المسار:</strong><br>${data.user_path}</p>
                `;
                document.getElementById('userResourceUsage').innerHTML = `
                    <p>💾 المساحة المستخدمة: <strong>${data.disk_usage_gb.toFixed(2)} GB</strong></p>
                    <p>⚙️ العمليات النشطة: <strong>${data.running_procs}</strong></p>
                    <p>🔐 الجلسات النشطة: <strong>${data.active_sessions}</strong></p>
                `;
            } catch(e) {
                console.error('Error loading profile:', e);
            }
        }
        
        // ===== زر الرجوع =====
        function goBack() {
            if (currentPath !== '{{ user_path }}') {
                let parent = currentPath.substring(0, currentPath.lastIndexOf('/'));
                if(!parent || parent === '/home/container/users_data') parent = '{{ user_path }}';
                currentPath = parent;
                refreshFiles();
            }
        }
        
        // ===== عرض التبويب =====
        function showTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            
            if(tabId === 'files') refreshFiles();
            if(tabId === 'processes') refreshProcesses();
            if(tabId === 'info') refreshSysInfo();
            if(tabId === 'network') refreshNetwork();
            if(tabId === 'users') refreshUsers();
            if(tabId === 'schedules') refreshSchedules();
            if(tabId === 'backups') refreshBackups();
            if(tabId === 'packages') refreshPackages();
            if(tabId === 'docker') refreshDocker();
            if(tabId === 'logs') refreshLogs();
        }
        
        // ===== تحديث الإحصائيات =====
        async function updateStats() {
            try {
                const res = await fetch('/api/system');
                const data = await res.json();
                
                document.getElementById('cpu').innerText = data.cpu.toFixed(1) + '%';
                document.getElementById('cpuFill').style.width = Math.min(data.cpu, 100) + '%';
                
                const ramPercent = data.memory.percent;
                const ramUsed = (data.memory.used / 1024**3).toFixed(2);
                const ramTotal = (data.memory.total / 1024**3).toFixed(2);
                document.getElementById('ram').innerText = ramPercent.toFixed(1) + '%';
                document.getElementById('ramText').innerText = ramUsed + ' / ' + ramTotal + ' GB';
                document.getElementById('ramFill').style.width = Math.min(ramPercent, 100) + '%';
                
                document.getElementById('disk').innerText = data.disk.percent.toFixed(1) + '%';
                document.getElementById('diskFill').style.width = Math.min(data.disk.percent, 100) + '%';
                
                const uptime = data.uptime;
                const days = Math.floor(uptime / 86400);
                const hours = Math.floor((uptime % 86400) / 3600);
                const mins = Math.floor((uptime % 3600) / 60);
                document.getElementById('uptime').innerText = days + 'd ' + hours + 'h';
                document.getElementById('uptimeFull').innerText = days + 'd ' + hours + 'h ' + mins + 'm';
                
                document.getElementById('processes').innerText = data.processes;
                
                const netIn = (data.network.bytes_recv / 1024**2).toFixed(2);
                const netOut = (data.network.bytes_sent / 1024**2).toFixed(2);
                document.getElementById('netIn').innerText = netIn;
                document.getElementById('netOut').innerText = netOut;
            } catch(e) {}
        }
        
        // ===== مدير الملفات =====
        async function refreshFiles() {
            const res = await fetch(`/api/files?path=${encodeURIComponent(currentPath)}`);
            const data = await res.json();
            if(!data.success) {
                document.getElementById('fileBrowser').innerHTML = `<div style="color:#ff6666;">خطأ: ${data.error}</div>`;
                return;
            }
            document.getElementById('currentPathDisplay').innerText = data.path;
            let html = `<ul class="file-list">`;
            if(data.can_go_up) {
                html += `<li class="file-item"><span>📁 ..</span><button onclick="goBack()">⬆️ للأعلى</button></li>`;
            }
            data.files.forEach(file => {
                const icon = file.is_dir ? '📁' : '📄';
                const size = !file.is_dir ? `(${(file.size/1024).toFixed(1)} KB)` : '';
                const isRunning = runningFileProcesses[file.name] ? true : false;
                
                html += `<li class="file-item">
                    <span>${icon} ${file.name} <small style="color:#888;">${size}</small> ${isRunning ? '<span class="running-indicator">● قيد التشغيل</span>' : ''}</span>
                    <div>
                        ${file.is_dir ? `<button onclick="enterFolder('${file.name}')">📂 فتح</button>` : ''}
                        ${!file.is_dir ? `<button onclick="editFile('${file.name}')">✏️ تعديل</button>` : ''}
                        ${!file.is_dir ? (isRunning ? 
                            `<button onclick="stopFile('${file.name}')" class="danger-btn">⏹️ إيقاف</button>` : 
                            `<button onclick="runFile('${file.name}')" class="success-btn">▶️ تشغيل</button>`
                        ) : ''}
                        <button onclick="deleteFile('${file.name}')" class="danger-btn">🗑️</button>
                    </div>
                </li>`;
            });
            html += `</ul>`;
            document.getElementById('fileBrowser').innerHTML = html;
        }
        
        function enterFolder(name) {
            currentPath = currentPath + '/' + name;
            refreshFiles();
        }
        
        async function runFile(filename) {
            const res = await fetch('/api/file/run', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({filename: filename, path: currentPath})
            });
            const data = await res.json();
            if(data.success) {
                runningFileProcesses[filename] = data.process_id;
                alert('✅ تم تشغيل: ' + filename + (data.installed ? '\\n📦 تم تثبيت: ' + data.installed.join(', ') : ''));
                refreshFiles();
            } else {
                alert('❌ خطأ: ' + data.error);
            }
        }
        
        async function stopFile(filename) {
            if(!runningFileProcesses[filename]) return;
            const res = await fetch('/api/file/stop', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({filename: filename, process_id: runningFileProcesses[filename]})
            });
            const data = await res.json();
            if(data.success) {
                delete runningFileProcesses[filename];
                refreshFiles();
            }
        }
        
        async function uploadFiles() {
            const files = document.getElementById('uploadFile').files;
            if(!files.length) return alert('اختر ملفات أولاً');
            for(let file of files) {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('path', currentPath);
                await fetch('/api/files/upload', {method: 'POST', body: formData});
            }
            refreshFiles();
            alert('✅ تم رفع الملفات بنجاح!');
        }
        
        async function createFolder() {
            const name = prompt('اسم المجلد:');
            if(!name) return;
            await fetch('/api/files/folder', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path: currentPath, name: name})
            });
            refreshFiles();
        }
        
        async function createFile() {
            const name = prompt('اسم الملف:');
            if(!name) return;
            await fetch('/api/files/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path: currentPath, name: name})
            });
            refreshFiles();
        }
        
        async function deleteFile(name) {
            if(!confirm('هل أنت متأكد من حذف ' + name + '؟')) return;
            await fetch('/api/files/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path: currentPath, name: name})
            });
            refreshFiles();
        }
        
        async function editFile(name) {
            const res = await fetch(`/api/files/content?path=${currentPath}/${name}`);
            const data = await res.json();
            if(data.success) {
                document.getElementById('editFilePath').value = currentPath + '/' + name;
                document.getElementById('codeEditor').value = data.content;
                showTab('editor');
            }
        }
        
        // ===== التيرمنال =====
        async function execCommand() {
            const cmd = document.getElementById('cmdInput').value;
            if(!cmd) return;
            const terminal = document.getElementById('terminalOutput');
            terminal.innerText += `\\n$ ${cmd}`;
            terminal.scrollTop = terminal.scrollHeight;
            
            const res = await fetch('/api/exec', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: cmd, cwd: currentPath})
            });
            const data = await res.json();
            const output = data.stdout || data.stderr || data.error || '';
            terminal.innerText += `\\n${output}`;
            terminal.scrollTop = terminal.scrollHeight;
            document.getElementById('cmdInput').value = '';
        }
        
        function clearTerminal() {
            document.getElementById('terminalOutput').innerText = '$ ';
        }
        
        // ===== العمليات =====
        async function startProcess() {
            const name = document.getElementById('procName').value;
            const command = document.getElementById('procCommand').value;
            if(!name || !command) { alert('أدخل الاسم والأمر'); return; }
            const res = await fetch('/api/process/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: name, command: command, cwd: currentPath})
            });
            const data = await res.json();
            alert(data.message);
            refreshProcesses();
        }
        
        async function refreshProcesses() {
            const res = await fetch('/api/process/list');
            const procs = await res.json();
            let html = '<ul class="file-list">';
            for(const [name, info] of Object.entries(procs)) {
                html += `<li class="file-item">
                    <div>
                        <strong>${name}</strong>
                        <div style="font-size:0.8em; color:#888;">${info.command}</div>
                    </div>
                    <div>
                        <span style="color:${info.status === 'running' ? '#28a745' : '#dc3545'};">${info.status}</span>
                        <button onclick="stopProcess('${name}')" class="danger-btn">⏹️ إيقاف</button>
                    </div>
                </li>`;
            }
            html += '</ul>';
            document.getElementById('processList').innerHTML = html;
        }
        
        async function stopProcess(name) {
            await fetch('/api/process/stop', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: name})
            });
            refreshProcesses();
        }
        
        async function killAllProcesses() {
            if(!confirm('إيقاف جميع العمليات؟')) return;
            await fetch('/api/process/stop-all', {method: 'POST'});
            refreshProcesses();
        }
        
        // ===== الشبكة =====
        async function refreshNetwork() {
            const res = await fetch('/api/network/stats');
            const data = await res.json();
            document.getElementById('networkStats').innerHTML = `
                <p>📥 المستلم: ${(data.bytes_recv/1024**2).toFixed(2)} MB</p>
                <p>📤 المرسل: ${(data.bytes_sent/1024**2).toFixed(2)} MB</p>
                <p>📦 الحزم الواردة: ${data.packets_recv}</p>
                <p>📦 الحزم الصادرة: ${data.packets_sent}</p>
            `;
        }
        
        async function scanPorts() {
            const host = document.getElementById('scanHost').value;
            const ports = document.getElementById('scanPorts').value;
            document.getElementById('scanResults').innerHTML = '⏳ جاري الفحص...';
            
            const res = await fetch('/api/network/scan', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({host, ports: ports.split(',').map(p => parseInt(p.trim()))})
            });
            const data = await res.json();
            
            let html = '<ul>';
            data.results.forEach(r => {
                html += `<li style="color:${r.open ? '#28a745' : '#dc3545'};">المنفذ ${r.port}: ${r.open ? 'مفتوح' : 'مغلق'}</li>`;
            });
            html += '</ul>';
            document.getElementById('scanResults').innerHTML = html;
        }
        
        // ===== المحرر =====
        async function loadFileForEdit() {
            const path = document.getElementById('editFilePath').value;
            const res = await fetch(`/api/files/content?path=${path}`);
            const data = await res.json();
            if(data.success) {
                document.getElementById('codeEditor').value = data.content;
            }
        }
        
        async function saveFileFromEditor() {
            const path = document.getElementById('editFilePath').value;
            const content = document.getElementById('codeEditor').value;
            const res = await fetch('/api/files/save', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path, content})
            });
            const data = await res.json();
            alert(data.success ? '✅ تم الحفظ!' : '❌ خطأ');
        }
        
        // ===== معلومات النظام =====
        async function refreshSysInfo() {
            const res = await fetch('/api/sysinfo');
            const data = await res.json();
            document.getElementById('sysInfo').innerText = data.info;
        }
        
        async function runQuickAction(action) {
            const res = await fetch('/api/system/action', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action})
            });
            const data = await res.json();
            alert(data.message || data.output);
        }
        
        // ===== المستخدمين =====
        async function refreshUsers() {
            const res = await fetch('/api/users/list');
            const data = await res.json();
            let html = '<ul class="file-list">';
            data.users.forEach(user => {
                html += `<li class="file-item">
                    <span>👤 ${user.username}</span>
                    <span>${user.active_sessions}/${user.max_sessions}</span>
                    ${user.username !== 'VeNoM' ? `<button onclick="deleteUser('${user.username}')" class="danger-btn">🗑️</button>` : ''}
                </li>`;
            });
            html += '</ul>';
            document.getElementById('userList').innerHTML = html;
        }
        
        async function addUser() {
            const username = document.getElementById('newUsername').value;
            const password = document.getElementById('newPassword').value;
            const maxSessions = document.getElementById('maxSessions').value;
            const expiry = document.getElementById('expiryDate').value;
            if(!username || !password) return alert('أدخل الاسم وكلمة المرور');
            const res = await fetch('/api/users/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username, password, max_sessions: maxSessions, expiry})
            });
            const data = await res.json();
            alert(data.message);
            refreshUsers();
        }
        
        async function deleteUser(username) {
            if(!confirm('حذف ' + username + '؟')) return;
            await fetch('/api/users/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username})
            });
            refreshUsers();
        }
        
        // ===== المهام المجدولة =====
        async function refreshSchedules() {
            const res = await fetch('/api/schedules/list');
            const data = await res.json();
            let html = '<ul class="file-list">';
            data.schedules.forEach(s => {
                html += `<li class="file-item">${s.name} - ${s.command}</li>`;
            });
            html += '</ul>';
            document.getElementById('scheduleList').innerHTML = html;
        }
        
        async function addSchedule() {
            const name = document.getElementById('cronName').value;
            const command = document.getElementById('cronCommand').value;
            const schedule = document.getElementById('cronSchedule').value;
            if(!name || !command) return;
            const res = await fetch('/api/schedules/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name, command, schedule})
            });
            const data = await res.json();
            alert(data.message);
            refreshSchedules();
        }
        
        // ===== النسخ الاحتياطي =====
        async function refreshBackups() {
            const res = await fetch('/api/backups/list');
            const data = await res.json();
            let html = '<ul class="file-list">';
            data.backups.forEach(b => {
                html += `<li class="file-item">💾 ${b.name} (${b.size})</li>`;
            });
            html += '</ul>';
            document.getElementById('backupList').innerHTML = html;
        }
        
        async function createBackup() {
            const res = await fetch('/api/backups/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({type: 'full'})
            });
            const data = await res.json();
            alert(data.message);
            refreshBackups();
        }
        
        function createBackupPrompt() {
            if(confirm('إنشاء نسخة احتياطية كاملة؟')) {
                createBackup();
            }
        }
        
        // ===== الحزم =====
        async function refreshPackages() {
            const res = await fetch('/api/packages/list');
            const data = await res.json();
            let html = '<h4>pip:</h4><ul>';
            data.pip.forEach(p => html += `<li>${p}</li>`);
            html += '</ul>';
            document.getElementById('packageList').innerHTML = html;
        }
        
        async function installPip() {
            const pkg = document.getElementById('pipPackage').value;
            if(!pkg) return;
            const res = await fetch('/api/packages/install/pip', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({package: pkg})
            });
            const data = await res.json();
            alert(data.message);
            refreshPackages();
        }
        
        // ===== Docker =====
        async function refreshDocker() {
            const res = await fetch('/api/docker/list');
            const data = await res.json();
            let html = '<h4>الحاويات:</h4><ul>';
            data.containers.forEach(c => html += `<li>${c.name} (${c.status})</li>`);
            html += '</ul>';
            document.getElementById('dockerContainers').innerHTML = html;
        }
        
        async function runDocker() {
            const image = document.getElementById('dockerImage').value;
            const name = document.getElementById('dockerName').value;
            if(!image) return;
            const res = await fetch('/api/docker/run', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({image, name})
            });
            const data = await res.json();
            alert(data.message);
            refreshDocker();
        }
        
        // ===== السجلات =====
        async function refreshLogs() {
            const res = await fetch('/api/logs');
            const data = await res.json();
            document.getElementById('logViewer').innerText = data.logs || 'لا توجد سجلات';
        }
        
        async function clearLogs() {
            if(!confirm('مسح جميع السجلات؟')) return;
            await fetch('/api/logs/clear', {method: 'POST'});
            refreshLogs();
        }
        
        // ===== التحديث التلقائي =====
        setInterval(updateStats, 3000);
        setInterval(() => {
            if(document.getElementById('processes').classList.contains('active')) refreshProcesses();
            if(document.getElementById('network').classList.contains('active')) refreshNetwork();
        }, 5000);
        
        updateStats();
        refreshFiles();
    </script>
</body>
</html>
'''

# ============================================================
# قالب تسجيل الدخول
# ============================================================
LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ˣᶜᵀ 𝒙 𝑻𝒆𝒂𝑴 - تسجيل الدخول</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 50%, #0d1329 100%);
            font-family: 'Cairo', sans-serif;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .login-container {
            background: linear-gradient(145deg, rgba(0,0,0,0.9), rgba(20,20,40,0.9));
            border: 2px solid #00ffcc;
            border-radius: 20px;
            padding: 50px;
            width: 420px;
            text-align: center;
            box-shadow: 0 0 50px #00ffcc33;
        }
        h1 {
            font-size: 2.2em;
            background: linear-gradient(90deg, #00ffcc, #ff66cc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .sub { color: #ff66cc; margin-bottom: 35px; }
        input {
            width: 100%;
            padding: 14px;
            margin: 10px 0;
            background: rgba(10,14,39,0.9);
            border: 1px solid #00ffcc55;
            color: #00ffcc;
            border-radius: 8px;
            font-size: 1em;
        }
        input:focus {
            outline: none;
            border-color: #00ffcc;
            box-shadow: 0 0 15px #00ffcc33;
        }
        button {
            width: 100%;
            padding: 14px;
            background: linear-gradient(45deg, #00ffcc, #00ff88);
            color: #0a0e27;
            border: none;
            border-radius: 8px;
            font-weight: bold;
            cursor: pointer;
            margin-top: 25px;
            font-size: 1.1em;
        }
        button:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px #00ffcc55;
        }
        .error {
            color: #ff3333;
            margin-top: 15px;
            padding: 10px;
            background: rgba(255,51,51,0.1);
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>🔥 ˣᶜᵀ 𝒙 𝑻𝒆𝒂𝑴</h1>
        <div class="sub">UNLIMITED VPS</div>
        <form method="POST" action="/login">
            <input type="text" name="username" placeholder="👤 اسم المستخدم" required>
            <input type="password" name="password" placeholder="🔒 كلمة المرور" required>
            <button type="submit">🔓 تسجيل الدخول</button>
        </form>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
    </div>
</body>
</html>
'''

# ============================================================
# Routes
# ============================================================
@app.route('/')
@login_required
def index():
    username = session.get('username')
    user_path = get_user_path(username)
    return render_template_string(HTML_TEMPLATE, session=session, user_path=user_path)

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'GET':
        return render_template_string(LOGIN_TEMPLATE, error=None)
    
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    if username == MASTER_USERNAME and password_hash == MASTER_PASSWORD_HASH:
        session.permanent = True
        session['logged_in'] = True
        session['username'] = username
        register_session(username)
        log_activity(username, "LOGIN", "Master logged in")
        return redirect(url_for('index'))
    
    users = load_users()
    if username in users:
        user_data = users[username]
        if isinstance(user_data, dict):
            if user_data.get('expiry'):
                try:
                    expiry = datetime.fromisoformat(user_data['expiry'])
                    if datetime.now() > expiry:
                        return render_template_string(LOGIN_TEMPLATE, error='انتهت صلاحية الحساب')
                except:
                    pass
            
            if user_data.get('password') == password_hash and can_user_login(username):
                session.permanent = True
                session['logged_in'] = True
                session['username'] = username
                register_session(username)
                ensure_user_folder(username)
                log_activity(username, "LOGIN", "User logged in")
                return redirect(url_for('index'))
    
    return render_template_string(LOGIN_TEMPLATE, error='❌ اسم المستخدم أو كلمة المرور غير صحيحة')

@app.route('/logout')
def logout():
    if 'username' in session:
        unregister_session(session['username'])
        log_activity(session['username'], "LOGOUT", "Logged out")
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/api/profile')
@login_required
def get_profile():
    username = session.get('username')
    users = load_users()
    user_data = users.get(username, {})
    sessions = load_user_sessions()
    
    user_path = get_user_path(username)
    total_size = 0
    if os.path.exists(user_path):
        for dirpath, dirnames, filenames in os.walk(user_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
    
    user_procs = [p for p in running_processes.values() if p['owner'] == username]
    user_procs.extend([p for p in file_processes.values() if p['username'] == username])
    
    return jsonify({
        'username': username,
        'created': user_data.get('created', datetime.now().isoformat()) if isinstance(user_data, dict) else datetime.now().isoformat(),
        'expiry': user_data.get('expiry', '∞ غير محدود') if isinstance(user_data, dict) else '∞ غير محدود',
        'max_sessions': user_data.get('max_sessions', 999) if isinstance(user_data, dict) else 999,
        'active_sessions': sessions.get(username, 0),
        'user_path': user_path,
        'disk_usage_gb': total_size / (1024**3),
        'running_procs': len(user_procs)
    })

@app.route('/api/system')
@login_required
def system_info():
    return jsonify(get_system_stats())

@app.route('/api/sysinfo')
@login_required
def sysinfo():
    try:
        info = f"""
🔥 UNLIMITED VPS - System Information
========================================
Hostname: {socket.gethostname()}
Platform: {platform.platform()}
Processor: {platform.processor()}
Python: {platform.python_version()}

💻 CPU:
  Cores: {psutil.cpu_count()}
  Usage: {psutil.cpu_percent()}%

🧠 Memory:
  Total: {psutil.virtual_memory().total / 1024**3:.2f} GB
  Available: {psutil.virtual_memory().available / 1024**3:.2f} GB
  Usage: {psutil.virtual_memory().percent}%

💾 Disk:
  Total: {psutil.disk_usage(BASE_PATH).total / 1024**3:.2f} GB
  Used: {psutil.disk_usage(BASE_PATH).used / 1024**3:.2f} GB
  Free: {psutil.disk_usage(BASE_PATH).free / 1024**3:.2f} GB

⏱️ Uptime: {timedelta(seconds=int(time.time() - psutil.boot_time()))}

🔥 RESOURCES: UNLIMITED MODE ACTIVE
========================================
"""
        return jsonify({'info': info})
    except Exception as e:
        return jsonify({'info': f'Error: {e}'})

@app.route('/api/system/action', methods=['POST'])
@login_required
def system_action():
    action = request.json.get('action')
    
    if action == 'clean':
        try:
            gc.collect()
            return jsonify({'success': True, 'message': '🧹 تم تنظيف الكاش'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    elif action == 'update':
        try:
            result = subprocess.run(['apt-get', 'update'], capture_output=True, text=True, timeout=120)
            return jsonify({'success': True, 'output': result.stdout})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    return jsonify({'success': False, 'error': 'إجراء غير معروف'})

@app.route('/api/files', methods=['GET'])
@login_required
def list_files():
    username = session.get('username')
    requested_path = request.args.get('path', get_user_path(username))
    
    if not is_path_allowed(username, requested_path):
        return jsonify({'success': False, 'error': 'صلاحية غير كافية'})
    
    if not os.path.exists(requested_path):
        return jsonify({'success': False, 'error': 'المسار غير موجود'})
    
    try:
        files = os.listdir(requested_path)
        file_list = []
        for f in files:
            full_path = os.path.join(requested_path, f)
            try:
                file_list.append({
                    'name': f,
                    'is_dir': os.path.isdir(full_path),
                    'size': os.path.getsize(full_path) if os.path.isfile(full_path) else 0,
                    'modified': datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat()
                })
            except:
                pass
        
        user_root = get_user_path(username)
        can_go_up = requested_path != user_root
        if username == MASTER_USERNAME:
            can_go_up = requested_path != BASE_PATH
        
        return jsonify({
            'success': True,
            'files': file_list,
            'path': requested_path,
            'can_go_up': can_go_up
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/files/upload', methods=['POST'])
@login_required
def upload_file():
    username = session.get('username')
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'لا يوجد ملف'})
    
    file = request.files['file']
    path = request.form.get('path', get_user_path(username))
    
    if not is_path_allowed(username, path):
        return jsonify({'success': False, 'error': 'صلاحية غير كافية'})
    
    try:
        filepath = os.path.join(path, file.filename)
        file.save(filepath)
        log_activity(username, "UPLOAD", file.filename)
        return jsonify({'success': True, 'message': 'تم الرفع بنجاح'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/files/folder', methods=['POST'])
@login_required
def create_folder():
    username = session.get('username')
    data = request.json
    path = data.get('path')
    name = data.get('name')
    
    if not is_path_allowed(username, path):
        return jsonify({'success': False, 'error': 'صلاحية غير كافية'})
    
    try:
        os.makedirs(os.path.join(path, name), exist_ok=True)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/files/create', methods=['POST'])
@login_required
def create_file():
    username = session.get('username')
    data = request.json
    path = data.get('path')
    name = data.get('name')
    
    if not is_path_allowed(username, path):
        return jsonify({'success': False, 'error': 'صلاحية غير كافية'})
    
    try:
        filepath = os.path.join(path, name)
        with open(filepath, 'w') as f:
            f.write('')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/files/delete', methods=['POST'])
@login_required
def delete_file():
    username = session.get('username')
    data = request.json
    full_path = os.path.join(data['path'], data['name'])
    
    if not is_path_allowed(username, full_path):
        return jsonify({'success': False, 'error': 'صلاحية غير كافية'})
    
    try:
        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
        else:
            os.remove(full_path)
        log_activity(username, "DELETE", data['name'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/files/content', methods=['GET'])
@login_required
def get_file_content():
    username = session.get('username')
    path = request.args.get('path')
    
    if not is_path_allowed(username, path):
        return jsonify({'success': False, 'error': 'صلاحية غير كافية'})
    
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return jsonify({'success': True, 'content': content})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/files/save', methods=['POST'])
@login_required
def save_file():
    username = session.get('username')
    data = request.json
    path = data['path']
    
    if not is_path_allowed(username, path):
        return jsonify({'success': False, 'error': 'صلاحية غير كافية'})
    
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(data['content'])
        log_activity(username, "EDIT", path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/file/run', methods=['POST'])
@login_required
def run_file():
    username = session.get('username')
    data = request.json
    filename = data.get('filename')
    path = data.get('path')
    
    if not is_path_allowed(username, path):
        return jsonify({'success': False, 'error': 'صلاحية غير كافية'})
    
    try:
        filepath = os.path.join(path, filename)
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'الملف غير موجود'})
        
        # تثبيت المكتبات تلقائياً
        installed = auto_install_dependencies(filepath)
        
        ext = filename.split('.')[-1].lower()
        if ext == 'py':
            command = f'python3 "{filepath}"'
        elif ext == 'js':
            command = f'node "{filepath}"'
        elif ext in ['sh', 'bash']:
            command = f'bash "{filepath}"'
        elif ext == 'php':
            command = f'php "{filepath}"'
        else:
            command = f'python3 "{filepath}"'
        
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid,
            universal_newlines=True,
            bufsize=1
        )
        
        process_id = f"{username}_{filename}_{int(time.time())}"
        file_processes[process_id] = {
            'process': process,
            'filename': filename,
            'username': username,
            'command': command,
            'started': time.time(),
            'output': []
        }
        
        log_activity(username, "FILE_RUN", filename)
        return jsonify({
            'success': True,
            'process_id': process_id,
            'message': f'تم تشغيل {filename}',
            'installed': installed
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/file/stop', methods=['POST'])
@login_required
def stop_file():
    username = session.get('username')
    data = request.json
    process_id = data.get('process_id')
    
    if process_id not in file_processes:
        return jsonify({'success': False, 'error': 'العملية غير موجودة'})
    
    proc_info = file_processes[process_id]
    if proc_info['username'] != username and username != MASTER_USERNAME:
        return jsonify({'success': False, 'error': 'صلاحية غير كافية'})
    
    try:
        os.killpg(os.getpgid(proc_info['process'].pid), signal.SIGTERM)
        time.sleep(1)
        if proc_info['process'].poll() is None:
            os.killpg(os.getpgid(proc_info['process'].pid), signal.SIGKILL)
        
        del file_processes[process_id]
        log_activity(username, "FILE_STOP", proc_info['filename'])
        return jsonify({'success': True, 'message': 'تم الإيقاف'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/exec', methods=['POST'])
@login_required
def execute_command():
    username = session.get('username')
    data = request.json
    command = data.get('command', '')
    cwd = data.get('cwd', get_user_path(username))
    
    if not is_path_allowed(username, cwd):
        cwd = get_user_path(username)
    
    dangerous = ['rm -rf /', 'mkfs', 'dd if=/dev/zero', ':(){ :|:& };:']
    for d in dangerous:
        if d in command:
            return jsonify({'success': False, 'error': 'أمر خطير ممنوع'})
    
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            bufsize=1,
            universal_newlines=True
        )
        
        try:
            stdout, stderr = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            return jsonify({'success': False, 'error': 'انتهت مهلة الأمر (30 ثانية)'})
        
        log_activity(username, "EXEC", command[:100])
        
        output = stdout if stdout else stderr if stderr else "لا يوجد مخرجات"
        
        return jsonify({
            'success': True,
            'stdout': output,
            'returncode': process.returncode
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/process/start', methods=['POST'])
@login_required
def start_process():
    username = session.get('username')
    data = request.json
    name = data['name']
    command = data['command']
    cwd = data.get('cwd', get_user_path(username))
    
    if name in running_processes:
        return jsonify({'success': False, 'message': 'اسم العملية موجود مسبقاً'})
    
    def run_proc():
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            running_processes[name] = {'process': process, 'owner': username, 'command': command}
            process.wait()
        except Exception as e:
            print(f"Process error: {e}")
        finally:
            if name in running_processes:
                del running_processes[name]
    
    threading.Thread(target=run_proc, daemon=True).start()
    
    processes = load_processes()
    processes[name] = {
        'command': command,
        'status': 'running',
        'owner': username,
        'started': time.time()
    }
    save_processes(processes)
    
    log_activity(username, "PROCESS_START", name)
    return jsonify({'success': True, 'message': f'✅ تم تشغيل {name}'})

@app.route('/api/process/stop', methods=['POST'])
@login_required
def stop_process():
    username = session.get('username')
    data = request.json
    name = data['name']
    
    if name in running_processes:
        proc_info = running_processes[name]
        if proc_info['owner'] != username and username != MASTER_USERNAME:
            return jsonify({'success': False, 'error': 'صلاحية غير كافية'})
        
        try:
            os.killpg(os.getpgid(proc_info['process'].pid), signal.SIGTERM)
            time.sleep(1)
            if proc_info['process'].poll() is None:
                os.killpg(os.getpgid(proc_info['process'].pid), signal.SIGKILL)
        except:
            pass
        
        if name in running_processes:
            del running_processes[name]
    
    processes = load_processes()
    if name in processes:
        processes[name]['status'] = 'stopped'
        save_processes(processes)
    
    log_activity(username, "PROCESS_STOP", name)
    return jsonify({'success': True})

@app.route('/api/process/stop-all', methods=['POST'])
@master_required
def stop_all_processes():
    for name in list(running_processes.keys()):
        try:
            proc_info = running_processes[name]
            os.killpg(os.getpgid(proc_info['process'].pid), signal.SIGKILL)
        except:
            pass
    running_processes.clear()
    
    processes = load_processes()
    for name in processes:
        processes[name]['status'] = 'stopped'
    save_processes(processes)
    
    return jsonify({'success': True})

@app.route('/api/process/list')
@login_required
def list_processes():
    processes = load_processes()
    username = session.get('username')
    
    for name in processes:
        if name in running_processes:
            processes[name]['status'] = 'running'
        else:
            processes[name]['status'] = 'stopped'
    
    if username != MASTER_USERNAME:
        processes = {k: v for k, v in processes.items() if v.get('owner') == username}
    
    return jsonify(processes)

@app.route('/api/network/stats')
@login_required
def network_stats():
    try:
        net_io = psutil.net_io_counters()
        return jsonify({
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv,
            'packets_sent': net_io.packets_sent,
            'packets_recv': net_io.packets_recv
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/network/scan', methods=['POST'])
@login_required
def scan_ports():
    data = request.json
    host = data.get('host', 'localhost')
    ports = data.get('ports', [80, 443])
    
    results = []
    for port in ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            results.append({'port': port, 'open': result == 0})
        except:
            results.append({'port': port, 'open': False})
    
    return jsonify({'results': results})

@app.route('/api/users/list')
@master_required
def list_users_api():
    users = load_users()
    sessions = load_user_sessions()
    result = []
    
    for username, user_data in users.items():
        if isinstance(user_data, dict):
            result.append({
                'username': username,
                'max_sessions': user_data.get('max_sessions', 999),
                'active_sessions': sessions.get(username, 0),
                'expiry': user_data.get('expiry')
            })
    
    return jsonify({'success': True, 'users': result})

@app.route('/api/users/add', methods=['POST'])
@master_required
def add_user_api():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password')
    max_sessions = data.get('max_sessions', 999)
    expiry = data.get('expiry')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'الاسم وكلمة المرور مطلوبان'})
    
    if username == MASTER_USERNAME:
        return jsonify({'success': False, 'message': 'لا يمكن إضافة المستخدم الرئيسي'})
    
    users = load_users()
    if username in users:
        return jsonify({'success': False, 'message': 'المستخدم موجود مسبقاً'})
    
    users[username] = {
        'password': hashlib.sha256(password.encode()).hexdigest(),
        'max_sessions': int(max_sessions),
        'created': datetime.now().isoformat(),
        'expiry': expiry
    }
    save_users(users)
    ensure_user_folder(username)
    
    log_activity(MASTER_USERNAME, "USER_ADD", username)
    return jsonify({'success': True, 'message': f'✅ تم إضافة المستخدم: {username}'})

@app.route('/api/users/delete', methods=['POST'])
@master_required
def delete_user_api():
    data = request.json
    username = data.get('username')
    
    if username == MASTER_USERNAME:
        return jsonify({'success': False, 'message': 'لا يمكن حذف المستخدم الرئيسي'})
    
    users = load_users()
    if username not in users:
        return jsonify({'success': False, 'message': 'المستخدم غير موجود'})
    
    del users[username]
    save_users(users)
    
    user_folder = os.path.join(USERS_FOLDER, username)
    if os.path.exists(user_folder):
        shutil.rmtree(user_folder)
    
    log_activity(MASTER_USERNAME, "USER_DELETE", username)
    return jsonify({'success': True, 'message': f'✅ تم حذف المستخدم: {username}'})

@app.route('/api/schedules/list')
@master_required
def list_schedules():
    schedules = load_schedules()
    return jsonify({'success': True, 'schedules': list(schedules.values())})

@app.route('/api/schedules/add', methods=['POST'])
@master_required
def add_schedule():
    data = request.json
    schedule_id = str(uuid.uuid4())[:8]
    
    schedules = load_schedules()
    schedules[schedule_id] = {
        'id': schedule_id,
        'name': data.get('name'),
        'command': data.get('command'),
        'schedule': data.get('schedule'),
        'created': datetime.now().isoformat()
    }
    save_schedules(schedules)
    
    log_activity(MASTER_USERNAME, "SCHEDULE_ADD", data.get('name'))
    return jsonify({'success': True, 'message': 'تمت إضافة المهمة'})

@app.route('/api/backups/list')
@master_required
def list_backups():
    backups = []
    if os.path.exists(BACKUPS_FOLDER):
        for f in os.listdir(BACKUPS_FOLDER):
            if f.endswith('.tar.gz') or f.endswith('.zip'):
                filepath = os.path.join(BACKUPS_FOLDER, f)
                size = os.path.getsize(filepath)
                backups.append({
                    'name': f,
                    'size': f"{size / 1024**2:.2f} MB",
                    'date': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
                })
    return jsonify({'backups': backups})

@app.route('/api/backups/create', methods=['POST'])
@master_required
def create_backup():
    data = request.json
    name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_path = os.path.join(BACKUPS_FOLDER, f"{name}.tar.gz")
    
    try:
        with tarfile.open(backup_path, 'w:gz') as tar:
            tar.add(BASE_PATH, arcname='backup')
        
        log_activity(MASTER_USERNAME, "BACKUP_CREATE", name)
        return jsonify({'success': True, 'message': f'✅ تم إنشاء النسخة: {name}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/packages/list')
@master_required
def list_packages():
    packages = load_packages()
    return jsonify(packages)

@app.route('/api/packages/install/pip', methods=['POST'])
@master_required
def install_pip():
    pkg = request.json.get('package')
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', pkg], capture_output=True, timeout=300)
        
        packages = load_packages()
        if pkg not in packages['pip']:
            packages['pip'].append(pkg)
            save_packages(packages)
        
        log_activity(MASTER_USERNAME, "PIP_INSTALL", pkg)
        return jsonify({'success': True, 'message': f'✅ تم تثبيت: {pkg}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/docker/list')
@master_required
def list_docker():
    containers = []
    try:
        result = subprocess.run(['docker', 'ps', '-a', '--format', '{{.Names}}|{{.Status}}'],
                              capture_output=True, text=True)
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split('|')
                if len(parts) >= 2:
                    containers.append({'name': parts[0], 'status': parts[1]})
    except:
        pass
    
    return jsonify({'containers': containers})

@app.route('/api/docker/run', methods=['POST'])
@master_required
def run_docker():
    data = request.json
    image = data.get('image')
    name = data.get('name', '')
    
    try:
        cmd = ['docker', 'run', '-d']
        if name:
            cmd.extend(['--name', name])
        cmd.append(image)
        
        subprocess.run(cmd, capture_output=True, timeout=60)
        
        log_activity(MASTER_USERNAME, "DOCKER_RUN", image)
        return jsonify({'success': True, 'message': f'✅ تم تشغيل الحاوية'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/logs')
@master_required
def get_logs():
    try:
        if os.path.exists(LOGS_FILE):
            with open(LOGS_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                logs = f.read()
            return jsonify({'logs': logs[-50000:]})
        return jsonify({'logs': 'لا توجد سجلات'})
    except:
        return jsonify({'logs': 'خطأ في قراءة السجلات'})

@app.route('/api/logs/clear', methods=['POST'])
@master_required
def clear_logs():
    try:
        with open(LOGS_FILE, 'w', encoding='utf-8') as f:
            f.write(f"[{datetime.now()}] SYSTEM: تم مسح السجلات\\n")
        return jsonify({'success': True})
    except:
        return jsonify({'success': False})

# ============================================================
# تشغيل التطبيق
# ============================================================
if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     🔥 ˣᶜᵀ 𝒙 𝑻𝒆𝒂𝑴 - UNLIMITED VPS CONTROL PANEL 🔥          ║
║                                                              ║
║     Resources: UNLIMITED ∞                                   ║
║     Port: 3066                                               ║
║     Master: VeNoM / VeNoM                                    ║
║                                                              ║
║     ✓ 3 أشرطة جانبية                                          ║
║     ✓ تثبيت تلقائي للمكتبات                                    ║
║     ✓ ملف شخصي متكامل                                         ║
║     ✓ تيرمنال محسن                                            ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    port = int(os.environ.get('SERVER_PORT', 3066))
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True,
        use_reloader=False
    )