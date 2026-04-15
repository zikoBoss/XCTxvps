import os
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
import signal
import warnings
warnings.filterwarnings('ignore')

def set_unlimited_resources():
    """تعيين موارد غير محدودة للنظام"""
    try:
        resource.setrlimit(resource.RLIMIT_AS, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        resource.setrlimit(resource.RLIMIT_DATA, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        resource.setrlimit(resource.RLIMIT_STACK, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        resource.setrlimit(resource.RLIMIT_RSS, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        resource.setrlimit(resource.RLIMIT_CPU, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        resource.setrlimit(resource.RLIMIT_NOFILE, (999999, 999999))
        resource.setrlimit(resource.RLIMIT_MEMLOCK, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        resource.setrlimit(resource.RLIMIT_NPROC, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        resource.setrlimit(resource.RLIMIT_CORE, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
        print("[🔥 UNLIMITED] All resource limits removed - INFINITY MODE ACTIVE")
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
            mem = psutil.virtual_memory()
            print(f"[🧹 MEMORY] Free: {mem.available / (1024**3):.2f} GB | Used: {mem.percent}% | UNLIMITED MODE")
        except Exception as e:
            pass

threading.Thread(target=unlimited_memory_monitor, daemon=True).start()

app = Flask(__name__)
app.secret_key = secrets.token_hex(64)
app.permanent_session_lifetime = timedelta(days=30)
app.config['MAX_CONTENT_LENGTH'] = None 
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

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

for folder in [USERS_FOLDER, TEMP_FOLDER, BACKUPS_FOLDER, 
               os.path.join(BASE_PATH, 'docker'), os.path.join(BASE_PATH, 'scripts')]:
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

def init_json_file(file_path, default_data):
    """تهيئة ملف JSON"""
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
    """تسجيل النشاط"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOGS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] [{username}] {action} | {details}\n")
    except:
        pass

def load_json_file(file_path):
    """تحميل ملف JSON"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_json_file(file_path, data):
    """حفظ ملف JSON"""
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

def load_network_stats():
    return load_json_file(NETWORK_STATS_FILE)

def save_network_stats(stats):
    save_json_file(NETWORK_STATS_FILE, stats)

def get_user_path(username):
    """الحصول على مسار المستخدم"""
    if username == MASTER_USERNAME:
        return BASE_PATH
    return os.path.join(USERS_FOLDER, username)

def get_terminal_cwd(username):
    return terminal_cwd.get(username, get_user_path(username))

def set_terminal_cwd(username, path):
    if is_path_allowed(username, path):
        terminal_cwd[username] = path
        return True
    return False

def ensure_user_folder(username):
    """التأكد من وجود مجلد المستخدم"""
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
  • docker run <image>

💡 Enjoy unlimited resources!
""")

def is_path_allowed(username, requested_path):
    """التحقق من صلاحية المسار"""
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
    """التحقق من إمكانية تسجيل الدخول"""
    sessions = load_user_sessions()
    user_config = load_users().get(username, {})
    max_sessions = user_config.get('max_sessions', 999) if isinstance(user_config, dict) else 999
    return sessions.get(username, 0) < max_sessions

def register_session(username):
    """تسجيل جلسة جديدة"""
    sessions = load_user_sessions()
    sessions[username] = sessions.get(username, 0) + 1
    save_user_sessions(sessions)

def unregister_session(username):
    """إلغاء تسجيل جلسة"""
    sessions = load_user_sessions()
    if username in sessions and sessions[username] > 0:
        sessions[username] -= 1
    save_user_sessions(sessions)

def get_system_stats():
    """الحصول على إحصائيات النظام"""
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
            padding: 15px;
            min-height: 100vh;
        }
        .container { max-width: 1600px; margin: 0 auto; }
        
        /* Header */
        .header-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding: 15px;
            background: rgba(0,0,0,0.6);
            border-radius: 15px;
            border: 1px solid #00ffcc44;
            flex-wrap: wrap;
            gap: 10px;
        }
        h1 { 
            font-size: 1.8em; 
            text-shadow: 0 0 20px #00ffcc, 0 0 40px #00ffcc88;
            background: linear-gradient(90deg, #00ffcc, #ff66cc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .unlimited-badge {
            background: linear-gradient(45deg, #ff6600, #ff9900);
            color: black;
            padding: 5px 15px;
            border-radius: 30px;
            font-size: 0.75em;
            font-weight: bold;
            animation: pulse 1.5s infinite;
            display: inline-block;
            margin-right: 10px;
        }
        @keyframes pulse {
            0%, 100% { transform: scale(1); opacity: 0.9; }
            50% { transform: scale(1.05); opacity: 1; }
        }
        .subtitle { 
            text-align: center; 
            margin-bottom: 15px; 
            color: #ff66cc; 
            font-size: 1em;
            text-shadow: 0 0 10px #ff66cc88;
        }
        
        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 12px;
            margin-bottom: 20px;
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
        .stat-label { font-size: 0.8em; color: #888; margin-bottom: 5px; }
        .stat-value { font-size: 1.6em; font-weight: bold; color: #00ffcc; }
        .stat-sub { font-size: 0.7em; color: #aaa; }
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #333;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 8px;
        }
        .progress-fill { 
            height: 100%; 
            background: linear-gradient(90deg, #00ffcc, #00ff88);
            width: 0%;
            transition: width 0.5s;
        }
        
        /* Tabs */
        .tabs {
            display: flex;
            gap: 8px;
            margin-bottom: 15px;
            flex-wrap: wrap;
            padding: 10px;
            background: rgba(0,0,0,0.4);
            border-radius: 10px;
        }
        .tab-btn {
            background: rgba(0,0,0,0.6);
            border: 1px solid #00ffcc44;
            color: #00ffcc;
            padding: 10px 18px;
            cursor: pointer;
            border-radius: 8px;
            transition: all 0.3s;
            font-size: 0.9em;
        }
        .tab-btn:hover {
            background: #00ffcc22;
            border-color: #00ffcc;
        }
        .tab-btn.active {
            background: linear-gradient(45deg, #00ffcc, #00ff88);
            color: #0a0e27;
            border-color: #00ffcc;
            font-weight: bold;
        }
        .tab-content {
            background: rgba(0,0,0,0.6);
            border: 1px solid #00ffcc44;
            border-radius: 15px;
            padding: 20px;
            display: none;
            min-height: 400px;
        }
        .tab-content.active { display: block; }
        
        /* Buttons */
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
            box-shadow: 0 4px 15px #00ffcc55;
        }
        .master-btn { 
            background: linear-gradient(45deg, #ff66cc, #ff3399);
            color: white;
            border: none;
        }
        .master-btn:hover {
            background: linear-gradient(45deg, #ff3399, #ff66cc);
        }
        .danger-btn {
            background: linear-gradient(45deg, #ff3333, #ff6666);
            color: white;
            border: none;
        }
        .danger-btn:hover {
            background: linear-gradient(45deg, #ff6666, #ff3333);
        }
        .success-btn {
            background: linear-gradient(45deg, #28a745, #5cb85c);
            color: white;
            border: none;
        }
        .logout-btn { 
            background: linear-gradient(45deg, #dc3545, #ff6b6b);
            color: white;
            border: none;
        }
        
        /* Inputs */
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
        
        /* Terminal */
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
        .terminal-line { margin: 2px 0; }
        .terminal-prompt { color: #00ffcc; }
        .terminal-error { color: #ff6666; }
        .terminal-success { color: #66ff66; }
        
        /* File Manager */
        .file-list { list-style: none; }
        .file-item {
            padding: 10px;
            border-bottom: 1px solid #00ffcc22;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            transition: all 0.2s;
        }
        .file-item:hover {
            background: rgba(0,255,204,0.05);
        }
        .file-icon { margin-left: 8px; }
        .file-actions {
            display: flex;
            gap: 5px;
            flex-wrap: wrap;
        }
        .file-actions button {
            padding: 5px 10px;
            font-size: 0.8em;
        }
        .run-btn {
            background: linear-gradient(45deg, #28a745, #5cb85c) !important;
            color: white !important;
            border: none !important;
        }
        .run-btn:hover {
            background: linear-gradient(45deg, #218838, #28a745) !important;
        }
        .stop-btn {
            background: linear-gradient(45deg, #dc3545, #ff6b6b) !important;
            color: white !important;
            border: none !important;
        }
        .running-indicator {
            color: #28a745;
            font-size: 0.75em;
            animation: blink 1s infinite;
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        /* Process List */
        .process-list { list-style: none; }
        .process-item {
            padding: 12px;
            border-bottom: 1px solid #00ffcc22;
            background: rgba(0,0,0,0.3);
            margin-bottom: 8px;
            border-radius: 8px;
        }
        .process-status-running { color: #28a745; }
        .process-status-stopped { color: #dc3545; }
        
        /* Network Stats */
        .network-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        
        /* Charts */
        .chart-container {
            background: rgba(0,0,0,0.5);
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
        }
        
        /* Contact Buttons */
        .contact-buttons {
            display: flex;
            gap: 10px;
            justify-content: center;
            margin: 15px 0;
            flex-wrap: wrap;
        }
        .contact-btn {
            padding: 10px 20px;
            border-radius: 25px;
            text-decoration: none;
            font-weight: bold;
            transition: all 0.3s;
        }
        .contact-btn:hover { transform: scale(1.05); }
        .btn1 { background: linear-gradient(45deg, #0088cc, #00a8e8); color: white; }
        .btn2 { background: linear-gradient(45deg, #28a745, #5cb85c); color: white; }
        .btn3 { background: linear-gradient(45deg, #dc3545, #ff6b6b); color: white; }
        
        /* Grid Layouts */
        .grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }
        
        /* Modal */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: linear-gradient(145deg, #0a0e27, #1a1f3a);
            border: 2px solid #00ffcc;
            border-radius: 15px;
            padding: 25px;
            max-width: 800px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
        }
        
        /* Code Editor */
        .code-editor {
            background: #0a0e27;
            color: #00ffcc;
            font-family: 'Courier New', monospace;
            width: 100%;
            min-height: 300px;
            padding: 15px;
            border: 1px solid #00ffcc55;
            border-radius: 8px;
            resize: vertical;
        }
        
        /* Animations */
        .glitch {
            animation: glitch 0.3s infinite;
        }
        @keyframes glitch {
            0% { text-shadow: 0.05em 0 0 rgba(255,0,0,0.75), -0.05em 0 0 rgba(0,255,0,0.75); }
            50% { text-shadow: -0.05em 0 0 rgba(255,0,0,0.75), 0.05em 0 0 rgba(0,0,255,0.75); }
            100% { text-shadow: 0.05em 0 0 rgba(0,255,0,0.75), -0.05em 0 0 rgba(255,0,0,0.75); }
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #0a0e27;
        }
        ::-webkit-scrollbar-thumb {
            background: #00ffcc;
            border-radius: 4px;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .header-bar { flex-direction: column; text-align: center; }
            h1 { font-size: 1.3em; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
        }
        
        .unlimited-text { color: #ff6600; font-weight: bold; }
        .badge {
            background: linear-gradient(45deg, #ff66cc, #ff3399);
            color: white;
            padding: 3px 10px;
            border-radius: 15px;
            font-size: 0.7em;
        }
        .info-box {
            background: rgba(0,255,204,0.1);
            border-left: 3px solid #00ffcc;
            padding: 15px;
            margin: 10px 0;
            border-radius: 0 8px 8px 0;
        }
    </style>
</head>
<body>
<div class="container">
    <div class="header-bar">
        <h1 class="glitch">ˣᶜᵀ 𝒙 𝑻𝒆𝒂𝑴 <span class="unlimited-badge">∞ UNLIMITED</span></h1>
        <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
            <span>👤 {{ session.username }}</span>
            {% if session.username == 'VeNoM' %}
                <button class="master-btn" onclick="showTab('users')">👑 Users</button>
                <button class="master-btn" onclick="showTab('schedules')">⏰ Cron</button>
                <button class="master-btn" onclick="showTab('logs')">📝 Logs</button>
                <button class="master-btn" onclick="showTab('backups')">💾 Backups</button>
                <button class="master-btn" onclick="showTab('packages')">📦 Packages</button>
                <button class="master-btn" onclick="showTab('docker')">🐳 Docker</button>
            {% endif %}
            <button onclick="showTab('files')">📁 Files</button>
            <button onclick="showTab('terminal')">🖥️ Terminal</button>
            <button onclick="showTab('processes')">⚙️ Processes</button>
            <button onclick="showTab('network')">🌐 Network</button>
            <button onclick="showTab('editor')">📝 Editor</button>
            <button onclick="showTab('info')">ℹ️ System</button>
            <a href="/logout"><button class="logout-btn">🚪 Logout</button></a>
        </div>
    </div>
    
    <div class="subtitle">🚀 UNLIMITED VPS | NO LIMITS | FULL CONTROL <span class="unlimited-text">∞</span></div>

    <div class="contact-buttons">
        <a href="https://t.me/noseyrobot" target="_blank" class="contact-btn btn1">📱 xAyOuB</a>
        <a href="https://t.me/GV_V_M" target="_blank" class="contact-btn btn2">👑 VeNoM</a>
        <a href="https://t.me/ZikoB0SS" target="_blank" class="contact-btn btn3">⚡ ZiKo BosS</a>
    </div>

    <div class="stats-grid" id="stats">
        <div class="stat-card">
            <div class="stat-label">💻 CPU Usage</div>
            <div class="stat-value" id="cpu">0%</div>
            <div class="progress-bar"><div class="progress-fill" id="cpuFill"></div></div>
        </div>
        <div class="stat-card">
            <div class="stat-label">🧠 RAM Usage</div>
            <div class="stat-value" id="ram">0%</div>
            <div class="stat-bar"><span id="ramText">0 / 0 GB</span></div>
            <div class="progress-bar"><div class="progress-fill" id="ramFill"></div></div>
        </div>
        <div class="stat-card">
            <div class="stat-label">💾 Disk Usage</div>
            <div class="stat-value" id="disk">0%</div>
            <div class="progress-bar"><div class="progress-fill" id="diskFill"></div></div>
        </div>
        <div class="stat-card">
            <div class="stat-label">⏱️ Uptime</div>
            <div class="stat-value" id="uptime">0h</div>
            <div class="stat-sub" id="uptimeFull">0d 0h 0m</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">🔄 Processes</div>
            <div class="stat-value" id="processes">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">🌐 Network</div>
            <div class="stat-value" id="netSpeed">0 KB/s</div>
            <div class="stat-sub">↓ <span id="netIn">0</span> | ↑ <span id="netOut">0</span></div>
        </div>
    </div>

    <!-- Files Tab -->
    <div id="files" class="tab-content active">
        <div style="margin-bottom:15px; display:flex; flex-wrap:wrap; gap:8px; align-items:center;">
            <input type="file" id="uploadFile" multiple style="max-width:200px;">
            <button onclick="uploadFiles()" class="success-btn">📤 Upload</button>
            <button onclick="refreshFiles()">🔄 Refresh</button>
            <button onclick="createFolder()">📁 New Folder</button>
            <button onclick="createFile()">📄 New File</button>
            <button onclick="compressFiles()">🗜️ Compress</button>
            <button onclick="downloadSelected()">⬇️ Download</button>
            <span style="font-size:0.8em; margin-right:auto;">📍 <span id="currentPathDisplay"></span></span>
        </div>
        <div id="fileBrowser"></div>
    </div>

    <!-- Terminal Tab -->
    <div id="terminal" class="tab-content">
        <div class="terminal" id="terminalOutput">
$ ========================================
$ 🔥 ˣᶜᵀ 𝒙 𝑻𝒆𝒂𝑴 UNLIMITED VPS 🔥
$ Resources: UNLIMITED ∞
$ Status: READY
$ Type 'help' for available commands
$ ========================================
        </div>
        <div style="display:flex; margin-top:10px; gap:8px;">
            <span style="color:#00ffcc; padding:10px;">$</span>
            <input type="text" id="cmdInput" placeholder="Enter command..." style="flex:1;" onkeypress="if(event.keyCode==13) execCommand()">
            <button onclick="execCommand()" class="success-btn">⚡ Execute</button>
            <button onclick="clearTerminal()">🗑️ Clear</button>
            <button onclick="stopCommand()" class="danger-btn">⏹️ Stop</button>
        </div>
    </div>

    <!-- Processes Tab -->
    <div id="processes" class="tab-content">
        <div style="margin-bottom:15px; display:flex; flex-wrap:wrap; gap:8px;">
            <input type="text" id="procName" placeholder="Process name" style="width:150px;">
            <input type="text" id="procCommand" placeholder="Command (e.g., python3 bot.py)" style="width:300px;">
            <button onclick="startProcess()" class="success-btn">▶️ Start</button>
            <button onclick="refreshProcesses()">🔄 Refresh</button>
            <button onclick="killAllProcesses()" class="danger-btn">⏹️ Stop All</button>
        </div>
        <div id="processList"></div>
    </div>

    <!-- Network Tab -->
    <div id="network" class="tab-content">
        <div class="grid-2">
            <div>
                <h3>🌐 Network Statistics</h3>
                <div id="networkStats"></div>
            </div>
            <div>
                <h3>📊 Network History</h3>
                <div class="chart-container" id="networkChart">
                    <canvas id="netChart" width="400" height="200"></canvas>
                </div>
            </div>
        </div>
        <div style="margin-top:20px;">
            <h3>🔍 Port Scanner</h3>
            <input type="text" id="scanHost" placeholder="Host (e.g., localhost)" value="localhost">
            <input type="text" id="scanPorts" placeholder="Ports (e.g., 80,443,8080)" value="80,443,8080,3000,5000,8000">
            <button onclick="scanPorts()">🔍 Scan</button>
            <div id="scanResults"></div>
        </div>
    </div>

    <!-- Code Editor Tab -->
    <div id="editor" class="tab-content">
        <div style="margin-bottom:15px; display:flex; flex-wrap:wrap; gap:8px;">
            <input type="text" id="editFilePath" placeholder="File path..." style="flex:1;">
            <button onclick="loadFileForEdit()">📂 Load</button>
            <button onclick="saveFileFromEditor()" class="success-btn">💾 Save</button>
            <button onclick="formatCode()">✨ Format</button>
            <select id="editorLang">
                <option value="python">Python</option>
                <option value="javascript">JavaScript</option>
                <option value="html">HTML</option>
                <option value="css">CSS</option>
                <option value="json">JSON</option>
                <option value="bash">Bash</option>
            </select>
        </div>
        <textarea id="codeEditor" class="code-editor" placeholder="// Select a file or start coding..."></textarea>
    </div>

    <!-- System Info Tab -->
    <div id="info" class="tab-content">
        <div class="grid-2">
            <div>
                <h3>🖥️ System Information</h3>
                <pre id="sysInfo" style="background:#0a0e27; padding:15px; border-radius:10px; overflow-x:auto; font-size:0.85em;"></pre>
            </div>
            <div>
                <h3>📈 Resource Usage</h3>
                <div id="resourceUsage"></div>
                <h3 style="margin-top:20px;">🔧 Quick Actions</h3>
                <button onclick="runQuickAction('update')">🔄 Update System</button>
                <button onclick="runQuickAction('clean')">🧹 Clean Cache</button>
                <button onclick="runQuickAction('restart')">🔄 Restart Services</button>
            </div>
        </div>
    </div>

    {% if session.username == 'VeNoM' %}
    <!-- Users Tab -->
    <div id="users" class="tab-content">
        <div class="grid-2">
            <div>
                <h3>➕ Add New User</h3>
                <input type="text" id="newUsername" placeholder="Username" style="width:100%;">
                <input type="password" id="newPassword" placeholder="Password" style="width:100%;">
                <input type="number" id="maxSessions" placeholder="Max sessions" value="999" style="width:100%;">
                <input type="date" id="expiryDate" placeholder="Expiry date" style="width:100%;">
                <button onclick="addUser()" class="success-btn">➕ Add User</button>
            </div>
            <div>
                <h3>👥 User Management</h3>
                <div id="userList"></div>
            </div>
        </div>
        <div style="margin-top:20px;">
            <h3>📂 All Users Folders</h3>
            <div id="allUsersFolders"></div>
        </div>
    </div>

    <!-- Schedules Tab -->
    <div id="schedules" class="tab-content">
        <div class="grid-2">
            <div>
                <h3>⏰ Add Cron Job</h3>
                <input type="text" id="cronName" placeholder="Job name" style="width:100%;">
                <input type="text" id="cronCommand" placeholder="Command" style="width:100%;">
                <input type="text" id="cronSchedule" placeholder="Schedule (e.g., */5 * * * *)" value="*/5 * * * *" style="width:100%;">
                <select id="cronUser" style="width:100%;">
                    <option value="all">All Users</option>
                </select>
                <button onclick="addSchedule()" class="success-btn">➕ Add Schedule</button>
            </div>
            <div>
                <h3>📋 Active Schedules</h3>
                <div id="scheduleList"></div>
            </div>
        </div>
    </div>

    <!-- Backups Tab -->
    <div id="backups" class="tab-content">
        <div style="margin-bottom:15px; display:flex; flex-wrap:wrap; gap:8px;">
            <input type="text" id="backupName" placeholder="Backup name">
            <select id="backupType">
                <option value="full">Full System</option>
                <option value="users">Users Only</option>
                <option value="config">Config Only</option>
            </select>
            <button onclick="createBackup()" class="success-btn">💾 Create Backup</button>
            <button onclick="refreshBackups()">🔄 Refresh</button>
        </div>
        <div id="backupList"></div>
    </div>

    <!-- Packages Tab -->
    <div id="packages" class="tab-content">
        <div class="grid-2">
            <div>
                <h3>📦 Install Package</h3>
                <input type="text" id="pipPackage" placeholder="pip package name">
                <button onclick="installPip()" class="success-btn">📥 Install pip</button>
                <input type="text" id="aptPackage" placeholder="apt package name" style="margin-top:10px;">
                <button onclick="installApt()" class="success-btn">📥 Install apt</button>
            </div>
            <div>
                <h3>📋 Installed Packages</h3>
                <div id="packageList"></div>
            </div>
        </div>
    </div>

    <!-- Docker Tab -->
    <div id="docker" class="tab-content">
        <div style="margin-bottom:15px; display:flex; flex-wrap:wrap; gap:8px;">
            <input type="text" id="dockerImage" placeholder="Docker image (e.g., nginx:latest)">
            <input type="text" id="dockerName" placeholder="Container name">
            <input type="text" id="dockerPorts" placeholder="Ports (e.g., 80:8080)">
            <button onclick="runDocker()" class="success-btn">🐳 Run Container</button>
            <button onclick="refreshDocker()">🔄 Refresh</button>
        </div>
        <div class="grid-2">
            <div>
                <h3>📦 Containers</h3>
                <div id="dockerContainers"></div>
            </div>
            <div>
                <h3>🖼️ Images</h3>
                <div id="dockerImages"></div>
            </div>
        </div>
    </div>

    <!-- Logs Tab -->
    <div id="logs" class="tab-content">
        <div style="margin-bottom:15px; display:flex; flex-wrap:wrap; gap:8px;">
            <button onclick="refreshLogs()">🔄 Refresh</button>
            <button onclick="clearLogs()" class="danger-btn">🗑️ Clear</button>
            <button onclick="downloadLogs()">⬇️ Download</button>
            <input type="text" id="logFilter" placeholder="Filter logs..." onkeyup="filterLogs()">
        </div>
        <div id="logViewer" style="background:#0a0e27; padding:15px; border-radius:10px; max-height:500px; overflow-y:auto; font-family:monospace; font-size:0.8em;"></div>
    </div>
    {% endif %}
</div>

<script>
    let currentPath = '{{ user_path }}';
    let selectedFiles = [];
    let networkHistory = [];
    let runningFileProcesses = {};
    
    let currentTerminalSession = null;
    let terminalOutputInterval = null;
    let terminalPrompt = '$ ';

    function getFileIcon(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const icons = {
            'py': '🐍', 'js': '📜', 'html': '🌐', 'htm': '🌐', 'css': '🎨', 'php': '🐘',
            'sh': '📟', 'bash': '📟', 'json': '📋', 'txt': '📄', 'md': '📝', 'sql': '🗄️',
            'java': '☕', 'cpp': '⚙️', 'c': '⚙️', 'go': '🐹', 'rs': '🦀', 'rb': '💎'
        };
        return icons[ext] || '📄';
    }

    function isRunnableFile(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const runnableExts = ['py', 'js', 'sh', 'bash', 'php', 'java', 'cpp', 'c', 'go', 'rs', 'rb'];
        return runnableExts.includes(ext);
    }

    function getRunCommand(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const commands = {
            'py': 'python3', 'js': 'node', 'sh': 'bash', 'bash': 'bash', 'php': 'php',
            'java': 'javac && java', 'cpp': 'g++ -o output && ./output', 'c': 'gcc -o output && ./output',
            'go': 'go run', 'rs': 'rustc && ./output', 'rb': 'ruby'
        };
        return commands[ext] || '';
    }

    async function runFile(filename) {
        const cmd = getRunCommand(filename);
        if(!cmd) return alert('Cannot run this file type');
        const res = await fetch('/api/file/run', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({filename: filename, path: currentPath, command: cmd})
        });
        const data = await res.json();
        if(data.success) {
            runningFileProcesses[filename] = data.process_id;
            alert('✅ Started: ' + filename);
            refreshFiles();
        } else {
            alert('❌ Error: ' + data.error);
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
            alert('⏹️ Stopped: ' + filename);
            refreshFiles();
        }
    }

    async function restartFile(filename) {
        await stopFile(filename);
        setTimeout(() => runFile(filename), 500);
    }

    function showTab(tabId) {
        document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
        document.getElementById(tabId).classList.add('active');
        if(tabId === 'files') refreshFiles();
        if(tabId === 'processes') refreshProcesses();
        if(tabId === 'info') refreshSysInfo();
        if(tabId === 'network') refreshNetwork();
        if(tabId === 'users') { refreshUsers(); refreshAllFolders(); }
        if(tabId === 'schedules') refreshSchedules();
        if(tabId === 'logs') refreshLogs();
        if(tabId === 'backups') refreshBackups();
        if(tabId === 'packages') refreshPackages();
        if(tabId === 'docker') refreshDocker();
    }

    async function updateStats() {
        try {
            const res = await fetch('/api/system');
            const data = await res.json();
            document.getElementById('cpu').innerText = data.cpu.toFixed(1) + '%';
            document.getElementById('cpuFill').style.width = Math.min(data.cpu, 100) + '%';
            document.getElementById('ram').innerText = data.memory.percent.toFixed(1) + '%';
            document.getElementById('ramFill').style.width = Math.min(data.memory.percent, 100) + '%';
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
            document.getElementById('netIn').innerText = netIn + ' MB';
            document.getElementById('netOut').innerText = netOut + ' MB';
        } catch(e) {}
    }

    async function refreshFiles() {
        const res = await fetch(`/api/files?path=${encodeURIComponent(currentPath)}`);
        const data = await res.json();
        if(!data.success) {
            document.getElementById('fileBrowser').innerHTML = `<div style="color:#ff6666;">Error: ${data.error}</div>`;
            return;
        }
        document.getElementById('currentPathDisplay').innerText = data.path;
        let html = `<ul class="file-list">`;
        if(data.can_go_up) {
            html += `<li class="file-item"><span>📁 ..</span><button onclick="goUp()">⬆️ Up</button></li>`;
        }
        data.files.forEach(file => {
            const icon = file.is_dir ? '📁' : getFileIcon(file.name);
            const size = !file.is_dir ? `(${(file.size/1024).toFixed(1)} KB)` : '';
            const isRunnable = isRunnableFile(file.name);
            const isRunning = runningFileProcesses[file.name] ? true : false;
            html += `<li class="file-item" id="file-${file.name.replace(/[^a-zA-Z0-9]/g, '_')}">
                <span><input type="checkbox" value="${file.name}" style="margin-left:8px;"> ${icon} ${file.name} <small style="color:#888;">${size}</small> ${isRunning ? '<span class="running-indicator">● RUNNING</span>' : ''}</span>
                <div class="file-actions">
                    ${file.is_dir ? `<button onclick="enterFolder('${file.name}')">📂 Open</button>` : ''}
                    ${!file.is_dir ? `<button onclick="editFile('${file.name}')">✏️ Edit</button><button onclick="viewFile('${file.name}')">👁️ View</button>` : ''}
                    ${isRunnable ? (isRunning ? 
                        `<button onclick="stopFile('${file.name}')" class="stop-btn">⏹️ Stop</button><button onclick="restartFile('${file.name}')" class="run-btn">🔄 Restart</button>` : 
                        `<button onclick="runFile('${file.name}')" class="run-btn">▶️ Run</button>`
                    ) : ''}
                    <button onclick="renameFile('${file.name}')">✏️ Rename</button>
                    <button onclick="deleteFile('${file.name}')" class="danger-btn">🗑️</button>
                </div>
            </li>`;
        });
        html += `</ul>`;
        document.getElementById('fileBrowser').innerHTML = html;
    }

    function goUp() {
        let parent = currentPath.substring(0, currentPath.lastIndexOf('/'));
        if(!parent || parent === '/home/container/users_data') parent = '{{ user_path }}';
        currentPath = parent;
        refreshFiles();
    }

    function enterFolder(name) {
        currentPath = currentPath + '/' + name;
        refreshFiles();
    }

    async function uploadFiles() {
        const files = document.getElementById('uploadFile').files;
        if(!files.length) return alert('Select files first');
        for(let file of files) {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('path', currentPath);
            await fetch('/api/files/upload', {method: 'POST', body: formData});
        }
        refreshFiles();
        alert('✅ Files uploaded successfully!');
    }

    async function createFolder() {
        const name = prompt('Folder name:');
        if(!name) return;
        await fetch('/api/files/folder', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({path: currentPath, name: name})
        });
        refreshFiles();
    }

    async function createFile() {
        const name = prompt('File name:');
        if(!name) return;
        await fetch('/api/files/create', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({path: currentPath, name: name})
        });
        refreshFiles();
    }

    async function deleteFile(name) {
        if(!confirm('Delete ' + name + '?')) return;
        await fetch('/api/files/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({path: currentPath, name: name})
        });
        refreshFiles();
    }

    async function renameFile(name) {
        const newName = prompt('New name:', name);
        if(!newName || newName === name) return;
        await fetch('/api/files/rename', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({path: currentPath, oldName: name, newName: newName})
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

    async function viewFile(name) {
        window.open(`/api/files/download?path=${currentPath}/${name}`, '_blank');
    }

    // Terminal functions
    async function updateTerminalPrompt() {
        try {
            const res = await fetch('/api/terminal/cwd');
            const data = await res.json();
            if (data.success) {
                terminalPrompt = data.cwd + ' $ ';
            }
        } catch(e) {
            console.error(e);
        }
    }

    async function execCommand() {
        const cmdInput = document.getElementById('cmdInput');
        const command = cmdInput.value.trim();
        if (!command) return;
        const terminal = document.getElementById('terminalOutput');
        terminal.innerText += '\n' + terminalPrompt + command;
        cmdInput.value = '';
        const execBtn = document.querySelector('button[onclick="execCommand()"]');
        execBtn.disabled = true;
        try {
            const res = await fetch('/api/terminal/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: command})
            });
            const data = await res.json();
            if (!data.success) {
                terminal.innerText += '\n[Error] ' + data.error;
                execBtn.disabled = false;
                return;
            }
            if (data.is_cd) {
                terminal.innerText += '\n' + data.output;
                await updateTerminalPrompt();
                execBtn.disabled = false;
                terminal.scrollTop = terminal.scrollHeight;
                return;
            }
            const sessionId = data.session_id;
            currentTerminalSession = sessionId;
            if (terminalOutputInterval) clearInterval(terminalOutputInterval);
            terminalOutputInterval = setInterval(async () => {
                if (!currentTerminalSession) {
                    clearInterval(terminalOutputInterval);
                    return;
                }
                const outRes = await fetch('/api/terminal/output/' + currentTerminalSession);
                const outData = await outRes.json();
                if (outData.success) {
                    const existingLines = terminal.innerText.split('\n');
                    const promptLine = existingLines.lastIndexOf(terminalPrompt + command);
                    if (outData.output) {
                        terminal.innerText = existingLines.slice(0, promptLine + 1).join('\n') + '\n' + outData.output;
                    }
                    if (outData.finished) {
                        clearInterval(terminalOutputInterval);
                        terminalOutputInterval = null;
                        currentTerminalSession = null;
                        execBtn.disabled = false;
                        terminal.innerText += '\n' + terminalPrompt;
                        await updateTerminalPrompt();
                    }
                    terminal.scrollTop = terminal.scrollHeight;
                }
            }, 300);
        } catch (error) {
            terminal.innerText += '\n[System Error] ' + error;
            execBtn.disabled = false;
        }
    }

    function stopCommand() {
        if (currentTerminalSession) {
            fetch('/api/terminal/stop/' + currentTerminalSession, {method: 'POST'});
            clearInterval(terminalOutputInterval);
            terminalOutputInterval = null;
            currentTerminalSession = null;
            document.querySelector('button[onclick="execCommand()"]').disabled = false;
            document.getElementById('terminalOutput').innerText += '\n[Stopped by user]';
        }
    }

    function clearTerminal() {
        document.getElementById('terminalOutput').innerText = '🔥 ˣᶜᵀ 𝒙 𝑻𝒆𝒂𝑴 UNLIMITED VPS 🔥\nResources: UNLIMITED ∞\nStatus: READY\nType \'help\' for available commands\n========================================\n' + terminalPrompt;
    }

    // Process management
    async function startProcess() {
        const name = document.getElementById('procName').value;
        let command = document.getElementById('procCommand').value;
        if(!name || !command) { alert('Enter name and command'); return; }
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
        let html = '<ul class="process-list">';
        for(const [name, info] of Object.entries(procs)) {
            const statusClass = info.status === 'running' ? 'process-status-running' : 'process-status-stopped';
            html += `<li class="process-item">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <strong>${name}</strong>
                        <div style="font-size:0.8em; color:#888;">${info.command}</div>
                        <div style="font-size:0.75em;">Owner: ${info.owner} | Started: ${new Date(info.started * 1000).toLocaleString()}</div>
                    </div>
                    <div>
                        <span class="${statusClass}">${info.status.toUpperCase()}</span>
                        <button onclick="stopProcess('${name}')" class="danger-btn">⏹️ Stop</button>
                        <button onclick="restartProcess('${name}')">🔄 Restart</button>
                    </div>
                </div>
            </li>`;
        }
        if(Object.keys(procs).length === 0) html += '<li style="text-align:center; padding:20px; color:#888;">No running processes</li>';
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

    async function restartProcess(name) {
        await fetch('/api/process/restart', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name})
        });
        refreshProcesses();
    }

    async function killAllProcesses() {
        if(!confirm('Stop ALL processes?')) return;
        await fetch('/api/process/stop-all', {method: 'POST'});
        refreshProcesses();
    }

    async function refreshNetwork() {
        const res = await fetch('/api/network/stats');
        const data = await res.json();
        let html = '<div class="network-stats">';
        html += `<div class="stat-card"><div class="stat-label">📥 Bytes Received</div><div class="stat-value">${(data.bytes_recv/1024**2).toFixed(2)} MB</div></div>`;
        html += `<div class="stat-card"><div class="stat-label">📤 Bytes Sent</div><div class="stat-value">${(data.bytes_sent/1024**2).toFixed(2)} MB</div></div>`;
        html += `<div class="stat-card"><div class="stat-label">📦 Packets In</div><div class="stat-value">${data.packets_recv}</div></div>`;
        html += `<div class="stat-card"><div class="stat-label">📦 Packets Out</div><div class="stat-value">${data.packets_sent}</div></div>`;
        html += '</div>';
        document.getElementById('networkStats').innerHTML = html;
    }

    async function scanPorts() {
        const host = document.getElementById('scanHost').value;
        const ports = document.getElementById('scanPorts').value;
        document.getElementById('scanResults').innerHTML = '<div style="color:#00ffcc;">Scanning...</div>';
        const res = await fetch('/api/network/scan', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({host, ports: ports.split(',').map(p => parseInt(p.trim()))})
        });
        const data = await res.json();
        let html = '<h4>Results:</h4><ul>';
        data.results.forEach(r => {
            const color = r.open ? '#28a745' : '#dc3545';
            html += `<li style="color:${color};">Port ${r.port}: ${r.open ? 'OPEN' : 'CLOSED'} ${r.service ? '('+r.service+')' : ''}</li>`;
        });
        html += '</ul>';
        document.getElementById('scanResults').innerHTML = html;
    }

    async function loadFileForEdit() {
        const path = document.getElementById('editFilePath').value;
        const res = await fetch(`/api/files/content?path=${path}`);
        const data = await res.json();
        if(data.success) {
            document.getElementById('codeEditor').value = data.content;
        } else {
            alert('Error loading file');
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
        alert(data.success ? '✅ Saved!' : '❌ Error: ' + data.error);
    }

    function formatCode() {
        const editor = document.getElementById('codeEditor');
        editor.value = editor.value.split('\n').map(l => l.trim()).join('\n');
    }

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

    async function refreshUsers() {
        const res = await fetch('/api/users/list');
        const data = await res.json();
        if(!data.success) return;
        let html = '<ul class="user-list">';
        data.users.forEach(user => {
            const expiry = user.expiry ? ` | Expires: ${user.expiry}` : '';
            html += `<li class="file-item">
                <span>👤 ${user.username} ${expiry}</span>
                <span>Sessions: ${user.active_sessions}/${user.max_sessions}</span>
                ${user.username !== 'VeNoM' ? `<button onclick="deleteUser('${user.username}')" class="danger-btn">🗑️ Delete</button>` : '<span class="badge">Master</span>'}
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
        if(!username || !password) { alert('Enter username and password'); return; }
        const res = await fetch('/api/users/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username, password, max_sessions: maxSessions, expiry})
        });
        const data = await res.json();
        alert(data.message);
        if(data.success) {
            document.getElementById('newUsername').value = '';
            document.getElementById('newPassword').value = '';
            refreshUsers();
        }
    }

    async function deleteUser(username) {
        if(!confirm(`Delete ${username}? All files will be deleted.`)) return;
        const res = await fetch('/api/users/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username})
        });
        const data = await res.json();
        alert(data.message);
        refreshUsers();
    }

    async function refreshSchedules() {
        const res = await fetch('/api/schedules/list');
        const data = await res.json();
        if(!data.success) return;
        let html = '<ul class="process-list">';
        data.schedules.forEach(sch => {
            html += `<li class="process-item">
                <strong>${sch.name}</strong><br>
                <small>Command: ${sch.command}</small><br>
                <small>Schedule: ${sch.schedule}</small><br>
                <small>User: ${sch.user}</small>
                <button onclick="deleteSchedule('${sch.id}')" class="danger-btn" style="float:right;">🗑️</button>
            </li>`;
        });
        html += '</ul>';
        document.getElementById('scheduleList').innerHTML = html;
    }

    async function addSchedule() {
        const name = document.getElementById('cronName').value;
        const command = document.getElementById('cronCommand').value;
        const schedule = document.getElementById('cronSchedule').value;
        const user = document.getElementById('cronUser').value;
        if(!name || !command) { alert('Enter name and command'); return; }
        const res = await fetch('/api/schedules/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, command, schedule, user})
        });
        const data = await res.json();
        alert(data.message);
        refreshSchedules();
    }

    async function deleteSchedule(id) {
        await fetch('/api/schedules/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({id})
        });
        refreshSchedules();
    }

    async function refreshBackups() {
        const res = await fetch('/api/backups/list');
        const data = await res.json();
        let html = '<ul class="file-list">';
        data.backups.forEach(b => {
            html += `<li class="file-item">
                <span>💾 ${b.name} (${b.size}) - ${b.date}</span>
                <div>
                    <button onclick="restoreBackup('${b.name}')">♻️ Restore</button>
                    <button onclick="deleteBackup('${b.name}')" class="danger-btn">🗑️</button>
                </div>
            </li>`;
        });
        html += '</ul>';
        document.getElementById('backupList').innerHTML = html;
    }

    async function createBackup() {
        const name = document.getElementById('backupName').value;
        const type = document.getElementById('backupType').value;
        const res = await fetch('/api/backups/create', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, type})
        });
        const data = await res.json();
        alert(data.message);
        refreshBackups();
    }

    async function refreshPackages() {
        const res = await fetch('/api/packages/list');
        const data = await res.json();
        let html = '<h4>📦 pip Packages</h4><ul class="file-list">';
        data.pip.forEach(p => {
            html += `<li class="file-item"><span>${p}</span><button onclick="uninstallPip('${p}')" class="danger-btn">🗑️</button></li>`;
        });
        html += '</ul><h4>📦 apt Packages</h4><ul class="file-list">';
        data.apt.forEach(p => {
            html += `<li class="file-item"><span>${p}</span></li>`;
        });
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

    async function installApt() {
        const pkg = document.getElementById('aptPackage').value;
        if(!pkg) return;
        const res = await fetch('/api/packages/install/apt', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({package: pkg})
        });
        const data = await res.json();
        alert(data.message);
    }

    async function refreshDocker() {
        const res = await fetch('/api/docker/list');
        const data = await res.json();
        let containersHtml = '<ul class="process-list">';
        data.containers.forEach(c => {
            containersHtml += `<li class="process-item">
                <strong>${c.name}</strong> (${c.image})<br>
                <small>Status: ${c.status}</small>
                <button onclick="stopDocker('${c.id}')" class="danger-btn">⏹️ Stop</button>
            </li>`;
        });
        containersHtml += '</ul>';
        document.getElementById('dockerContainers').innerHTML = containersHtml;
        let imagesHtml = '<ul class="file-list">';
        data.images.forEach(i => {
            imagesHtml += `<li class="file-item"><span>${i.repo}:${i.tag}</span><span>${i.size}</span></li>`;
        });
        imagesHtml += '</ul>';
        document.getElementById('dockerImages').innerHTML = imagesHtml;
    }

    async function runDocker() {
        const image = document.getElementById('dockerImage').value;
        const name = document.getElementById('dockerName').value;
        const ports = document.getElementById('dockerPorts').value;
        if(!image) return;
        const res = await fetch('/api/docker/run', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({image, name, ports})
        });
        const data = await res.json();
        alert(data.message);
        refreshDocker();
    }

    async function refreshLogs() {
        const res = await fetch('/api/logs');
        const data = await res.json();
        document.getElementById('logViewer').innerText = data.logs || 'No logs available';
    }

    async function clearLogs() {
        if(!confirm('Clear all logs?')) return;
        await fetch('/api/logs/clear', {method: 'POST'});
        refreshLogs();
    }

    function filterLogs() {
        const filter = document.getElementById('logFilter').value.toLowerCase();
        const logViewer = document.getElementById('logViewer');
        const lines = logViewer.innerText.split('\n');
        const filtered = lines.filter(l => l.toLowerCase().includes(filter));
        logViewer.innerText = filtered.join('\n');
    }

    async function updateRunningFiles() {
        const res = await fetch('/api/file/status');
        const data = await res.json();
        if(data.success) {
            runningFileProcesses = {};
            data.running.forEach(r => {
                runningFileProcesses[r.filename] = r.process_id;
            });
            if(document.getElementById('files').classList.contains('active')) {
                refreshFiles();
            }
        }
    }

    // Missing helper functions
    function compressFiles() { alert('Compress feature coming soon'); }
    function downloadSelected() { alert('Download selected feature coming soon'); }
    function refreshAllFolders() { /* implement if needed */ }
    function restoreBackup(name) { alert('Restore backup: ' + name); }
    function deleteBackup(name) { 
        if(confirm('Delete backup ' + name + '?')) {
            // API call to delete backup
        }
    }
    function uninstallPip(pkg) { alert('Uninstall pip: ' + pkg); }
    function stopDocker(id) { 
        // API call to stop container
    }

    // Initialize
    setInterval(updateStats, 3000);
    setInterval(() => {
        if(document.getElementById('processes').classList.contains('active')) refreshProcesses();
        if(document.getElementById('network').classList.contains('active')) refreshNetwork();
    }, 5000);
    setInterval(updateRunningFiles, 3000);

    updateStats();
    updateRunningFiles();

    window.addEventListener('load', async () => {
        await updateTerminalPrompt();
        const terminal = document.getElementById('terminalOutput');
        terminal.innerText = '🔥 ˣᶜᵀ 𝒙 𝑻𝒆𝒂𝑴 UNLIMITED VPS 🔥\nResources: UNLIMITED ∞\nStatus: READY\nType \'help\' for available commands\n========================================\n' + terminalPrompt;
    });
</script>
</body>
</html>
'''

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ˣᶜᵀ 𝒙 𝑻𝒆𝒂𝑴 - UNLIMITED VPS Login</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🔥</text></svg>">
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 50%, #0d1329 100%);
            font-family: 'Cairo', 'Segoe UI', 'Tahoma', sans-serif;
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
            margin-bottom: 10px;
            background: linear-gradient(90deg, #00ffcc, #ff66cc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .unlimited-badge {
            background: linear-gradient(45deg, #ff6600, #ff9900);
            color: black;
            padding: 3px 12px;
            border-radius: 20px;
            font-size: 0.65em;
            font-weight: bold;
            display: inline-block;
            margin-right: 5px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.1); }
        }
        .sub { color: #ff66cc; margin-bottom: 35px; font-size: 0.9em; }
        input {
            width: 100%;
            padding: 14px;
            margin: 10px 0;
            background: rgba(10,14,39,0.9);
            border: 1px solid #00ffcc55;
            color: #00ffcc;
            border-radius: 8px;
            font-size: 1em;
            transition: all 0.3s;
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
            transition: all 0.3s;
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
        .features {
            margin: 25px 0;
            text-align: right;
            font-size: 0.85em;
            color: #888;
        }
        .features li {
            margin: 8px 0;
            list-style: none;
        }
        .features li:before {
            content: "✓ ";
            color: #00ffcc;
        }
        .contact-buttons {
            display: flex;
            gap: 10px;
            justify-content: center;
            margin-top: 25px;
            flex-wrap: wrap;
        }
        .contact-btn {
            padding: 8px 16px;
            border-radius: 20px;
            text-decoration: none;
            font-size: 0.75em;
            font-weight: bold;
            transition: all 0.3s;
        }
        .contact-btn:hover { transform: scale(1.05); }
        .btn1 { background: linear-gradient(45deg, #0088cc, #00a8e8); color: white; }
        .btn2 { background: linear-gradient(45deg, #28a745, #5cb85c); color: white; }
        .btn3 { background: linear-gradient(45deg, #dc3545, #ff6b6b); color: white; }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>ˣᶜᵀ 𝒙 𝑻𝒆𝒂𝑴 <span class="unlimited-badge">∞ UNLIMITED</span></h1>
        <div class="sub">🔥 VPS Control Panel - No Limits 🔥</div>
        
        <ul class="features">
            <li>Unlimited Resources</li>
            <li>File Manager</li>
            <li>Process Manager</li>
            <li>Terminal Access</li>
            <li>Docker Support</li>
            <li>Network Tools</li>
        </ul>
        
        <form method="POST" action="/login">
            <input type="text" name="username" placeholder="👤 Username" required autocomplete="off">
            <input type="password" name="password" placeholder="🔒 Password" required>
            <button type="submit">🔓 Login to UNLIMITED VPS</button>
        </form>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        
        <div class="contact-buttons">
            <a href="https://t.me/noseyrobot" target="_blank" class="contact-btn btn1">📱 xAyOuB</a>
            <a href="https://t.me/GV_V_M" target="_blank" class="contact-btn btn2">👑 VeNoM</a>
            <a href="https://t.me/ZikoB0SS" target="_blank" class="contact-btn btn3">⚡ ZiKo</a>
        </div>
    </div>
</body>
</html>
'''

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
        session['login_time'] = datetime.now().isoformat()
        register_session(username)
        log_activity(username, "LOGIN", "Master logged in - UNLIMITED MODE")
        return redirect(url_for('index'))
    
    users = load_users()
    if username in users:
        user_data = users[username]
        if isinstance(user_data, dict):
            if user_data.get('expiry'):
                expiry = datetime.fromisoformat(user_data['expiry'])
                if datetime.now() > expiry:
                    return render_template_string(LOGIN_TEMPLATE, error='Account expired')
            
            if user_data.get('password') == password_hash and can_user_login(username):
                session.permanent = True
                session['logged_in'] = True
                session['username'] = username
                session['login_time'] = datetime.now().isoformat()
                register_session(username)
                ensure_user_folder(username)
                log_activity(username, "LOGIN", "User logged in")
                return redirect(url_for('index'))
    
    return render_template_string(LOGIN_TEMPLATE, error='❌ Invalid username or password')

@app.route('/logout')
def logout():
    if 'username' in session:
        unregister_session(session['username'])
        log_activity(session['username'], "LOGOUT", "Logged out")
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/api/system')
@login_required
def system_info():
    return jsonify(get_system_stats())

@app.route('/api/sysinfo')
@login_required
def sysinfo():
    try:
        info = f"""
🔥 UNLIMITED VPS - System Information 🔥
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

🌐 Network:
  Bytes Sent: {psutil.net_io_counters().bytes_sent / 1024**2:.2f} MB
  Bytes Recv: {psutil.net_io_counters().bytes_recv / 1024**2:.2f} MB

⏱️ Uptime: {timedelta(seconds=int(time.time() - psutil.boot_time()))}

🔥 RESOURCES: UNLIMITED MODE ACTIVE
========================================
"""
        return jsonify({'info': info})
    except Exception as e:
        return jsonify({'info': f'UNLIMITED VPS - Error: {e}'})

@app.route('/api/system/action', methods=['POST'])
@login_required
def system_action():
    action = request.json.get('action')
    username = session.get('username')
    
    if action == 'clean':
        try:
            gc.collect()
            return jsonify({'success': True, 'message': '🧹 Cache cleaned'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    elif action == 'update':
        try:
            result = subprocess.run(['apt-get', 'update'], capture_output=True, text=True, timeout=120)
            log_activity(username, "SYSTEM_UPDATE", "Updated packages")
            return jsonify({'success': True, 'output': result.stdout})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    return jsonify({'success': False, 'error': 'Unknown action'})

@app.route('/api/files', methods=['GET'])
@login_required
def list_files():
    username = session.get('username')
    requested_path = request.args.get('path', get_user_path(username))
    
    if not is_path_allowed(username, requested_path):
        return jsonify({'success': False, 'error': 'Access denied'})
    
    if not os.path.exists(requested_path):
        return jsonify({'success': False, 'error': 'Path not found'})
    
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

def find_main_file(directory):
    """البحث عن الملف الرئيسي في المجلد"""
    main_files = ['main.py', 'app.py', 'index.py', 'run.py', 'start.py',
                  'main.js', 'index.js', 'app.js', 'server.js',
                  'main.sh', 'start.sh', 'run.sh',
                  'main.php', 'index.php', 'app.php']
    
    try:
        for filename in os.listdir(directory):
            if filename.lower() in main_files:
                return filename
    except:
        pass
    return None

def extract_zip_file(filepath, extract_path):
    """فك ضغط ملف ZIP"""
    try:
        if zipfile.is_zipfile(filepath):
            with zipfile.ZipFile(filepath, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            main_file = find_main_file(extract_path)
            return True, main_file
    except Exception as e:
        print(f"[ERROR] ZIP extraction failed: {e}")
    return False, None

@app.route('/api/files/upload', methods=['POST'])
@login_required
def upload_file():
    username = session.get('username')
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file'})
    
    file = request.files['file']
    path = request.form.get('path', get_user_path(username))
    
    if not is_path_allowed(username, path):
        return jsonify({'success': False, 'error': 'Access denied'})
    
    try:
        filepath = os.path.join(path, file.filename)
        file.save(filepath)
        
        main_file = None
        extracted = False
        
        if file.filename.lower().endswith('.zip'):
            extract_dir = os.path.join(path, file.filename.replace('.zip', ''))
            os.makedirs(extract_dir, exist_ok=True)
            extracted, main_file = extract_zip_file(filepath, extract_dir)
            if extracted:
                print(f"[✅ ZIP EXTRACTED] {file.filename} -> {extract_dir}")
                log_activity(username, "ZIP_EXTRACT", f"{file.filename} -> {main_file or 'no main file found'}")
        
        log_activity(username, "UPLOAD", file.filename)
        return jsonify({
            'success': True, 
            'message': 'Uploaded successfully',
            'extracted': extracted,
            'main_file': main_file,
            'extract_dir': extract_dir if extracted else None
        })
    except Exception as e:
        print(f"[ERROR] Upload failed: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/files/folder', methods=['POST'])
@login_required
def create_folder():
    username = session.get('username')
    data = request.json
    path = data.get('path')
    name = data.get('name')
    
    if not is_path_allowed(username, path):
        return jsonify({'success': False, 'error': 'Access denied'})
    
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
        return jsonify({'success': False, 'error': 'Access denied'})
    
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
        return jsonify({'success': False, 'error': 'Access denied'})
    
    try:
        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
        else:
            os.remove(full_path)
        log_activity(username, "DELETE", data['name'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/files/rename', methods=['POST'])
@login_required
def rename_file():
    username = session.get('username')
    data = request.json
    old_path = os.path.join(data['path'], data['oldName'])
    new_path = os.path.join(data['path'], data['newName'])
    
    if not is_path_allowed(username, old_path):
        return jsonify({'success': False, 'error': 'Access denied'})
    
    try:
        os.rename(old_path, new_path)
        log_activity(username, "RENAME", f"{data['oldName']} -> {data['newName']}")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/files/content', methods=['GET'])
@login_required
def get_file_content():
    username = session.get('username')
    path = request.args.get('path')
    
    if not is_path_allowed(username, path):
        return jsonify({'success': False, 'error': 'Access denied'})
    
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
        return jsonify({'success': False, 'error': 'Access denied'})
    
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(data['content'])
        log_activity(username, "EDIT", path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/files/download')
@login_required
def download_file():
    username = session.get('username')
    path = request.args.get('path')
    
    if not is_path_allowed(username, path):
        return jsonify({'success': False, 'error': 'Access denied'})
    
    try:
        return send_file(path, as_attachment=True)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

file_processes = {}
terminal_sessions = {}
terminal_cwd = {}
@app.route('/api/file/run', methods=['POST'])
@login_required
def run_file():
    username = session.get('username')
    data = request.json
    filename = data.get('filename')
    path = data.get('path')
    cmd_prefix = data.get('command', 'python3')
    
    if not is_path_allowed(username, path):
        return jsonify({'success': False, 'error': 'Access denied'})
    
    try:
        filepath = os.path.join(path, filename)
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'File not found'})
        
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
            command = f'{cmd_prefix} "{filepath}"'
        
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
        
        def capture_output(proc_id):
            try:
                for line in file_processes[proc_id]['process'].stdout:
                    if proc_id in file_processes:
                        file_processes[proc_id]['output'].append(line.strip())
                        print(f"[{filename}] {line.strip()}")
            except Exception as e:
                print(f"[ERROR] Output capture failed: {e}")
        
        threading.Thread(target=capture_output, args=(process_id,), daemon=True).start()
        
        print(f"[STARTED] {username} ran {filename}")
        log_activity(username, "FILE_RUN", filename)
        return jsonify({'success': True, 'process_id': process_id, 'message': f'Started {filename}'})
    except Exception as e:
        print(f"[ERROR] File run failed: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/file/stop', methods=['POST'])
@login_required
def stop_file():
    username = session.get('username')
    data = request.json
    process_id = data.get('process_id')
    
    if process_id not in file_processes:
        return jsonify({'success': False, 'error': 'Process not found'})
    
    proc_info = file_processes[process_id]
    if proc_info['username'] != username and username != MASTER_USERNAME:
        return jsonify({'success': False, 'error': 'Permission denied'})
    
    try:
        os.killpg(os.getpgid(proc_info['process'].pid), signal.SIGTERM)
        time.sleep(1)
        if proc_info['process'].poll() is None:
            os.killpg(os.getpgid(proc_info['process'].pid), signal.SIGKILL)
        
        del file_processes[process_id]
        log_activity(username, "FILE_STOP", proc_info['filename'])
        return jsonify({'success': True, 'message': 'Stopped successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/file/status', methods=['GET'])
@login_required
def file_status():
    username = session.get('username')
    running = []
    
    for pid, info in list(file_processes.items()):
        if info['username'] == username or username == MASTER_USERNAME:
            is_running = info['process'].poll() is None
            if is_running:
                running.append({
                    'process_id': pid,
                    'filename': info['filename'],
                    'started': info['started'],
                    'output': info.get('output', [])
                })
            else:
                del file_processes[pid]
    
    return jsonify({'success': True, 'running': running})

@app.route('/api/file/output/<process_id>', methods=['GET'])
@login_required
def get_file_output(process_id):
    """الحصول على مخرجات الملف المشغل"""
    username = session.get('username')
    
    if process_id not in file_processes:
        return jsonify({'success': False, 'error': 'Process not found'})
    
    proc_info = file_processes[process_id]
    if proc_info['username'] != username and username != MASTER_USERNAME:
        return jsonify({'success': False, 'error': 'Permission denied'})
    
    return jsonify({
        'success': True,
        'output': proc_info.get('output', []),
        'is_running': proc_info['process'].poll() is None
    })

@app.route('/api/terminal/start', methods=['POST'])
@login_required
def terminal_start():
    username = session.get('username')
    data = request.json
    command = data.get('command', '').strip()
    
    if not command:
        return jsonify({'success': False, 'error': 'No command provided'})
    
    dangerous = ['rm -rf /', 'mkfs', 'dd if=/dev/zero', ':(){ :|:& };:']
    for d in dangerous:
        if d in command:
            return jsonify({'success': False, 'error': 'Dangerous command blocked'})
    
    if command.startswith('cd '):
        new_path = command[3:].strip()
        if not new_path:
            new_path = get_user_path(username)
        else:
            current_cwd = get_terminal_cwd(username)
            if not new_path.startswith('/'):
                new_path = os.path.join(current_cwd, new_path)
            new_path = os.path.realpath(new_path)
        
        if is_path_allowed(username, new_path) and os.path.isdir(new_path):
            set_terminal_cwd(username, new_path)
            output = f"Changed directory to: {new_path}"
            log_activity(username, "TERMINAL_CD", new_path)
            return jsonify({'success': True, 'session_id': None, 'output': output, 'cwd': new_path, 'is_cd': True})
        else:
            return jsonify({'success': False, 'error': 'Directory not allowed or does not exist'})
    
    cwd = get_terminal_cwd(username)
    session_id = f"{username}_{secrets.token_hex(4)}_{int(time.time())}"
    
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            preexec_fn=os.setsid,
            universal_newlines=True,
            bufsize=1
        )
        
        terminal_sessions[session_id] = {
            'process': process,
            'username': username,
            'command': command,
            'cwd': cwd,
            'output': [],
            'started': time.time(),
            'finished': False
        }
        
        def read_output(sid):
            proc_info = terminal_sessions.get(sid)
            if not proc_info:
                return
            try:
                for line in iter(proc_info['process'].stdout.readline, ''):
                    if sid not in terminal_sessions:
                        break
                    terminal_sessions[sid]['output'].append(line.rstrip('\n'))
                proc_info['process'].stdout.close()
                proc_info['process'].wait()
                proc_info['finished'] = True
            except Exception as e:
                print(f"[TERMINAL] Output read error: {e}")
            finally:
                if sid in terminal_sessions:
                    terminal_sessions[sid]['finished'] = True
        
        threading.Thread(target=read_output, args=(session_id,), daemon=True).start()
        
        log_activity(username, "TERMINAL_START", f"{command[:100]} in {cwd}")
        return jsonify({
            'success': True,
            'session_id': session_id,
            'cwd': cwd,
            'message': f'Command started: {command}'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/terminal/output/<session_id>', methods=['GET'])
@login_required
def terminal_output(session_id):
    username = session.get('username')
    
    if session_id not in terminal_sessions:
        return jsonify({'success': False, 'error': 'Session not found'})
    
    sess = terminal_sessions[session_id]
    if sess['username'] != username and username != MASTER_USERNAME:
        return jsonify({'success': False, 'error': 'Permission denied'})
    
    output_lines = sess['output'].copy()
    finished = sess['finished']
    
    return jsonify({
        'success': True,
        'output': '\n'.join(output_lines),
        'finished': finished,
        'returncode': sess['process'].returncode if finished else None
    })

@app.route('/api/terminal/stop/<session_id>', methods=['POST'])
@login_required
def terminal_stop(session_id):
    username = session.get('username')
    
    if session_id not in terminal_sessions:
        return jsonify({'success': False, 'error': 'Session not found'})
    
    sess = terminal_sessions[session_id]
    if sess['username'] != username and username != MASTER_USERNAME:
        return jsonify({'success': False, 'error': 'Permission denied'})
    
    try:
        os.killpg(os.getpgid(sess['process'].pid), signal.SIGTERM)
        time.sleep(0.5)
        if sess['process'].poll() is None:
            os.killpg(os.getpgid(sess['process'].pid), signal.SIGKILL)
        sess['finished'] = True
        del terminal_sessions[session_id]
        log_activity(username, "TERMINAL_STOP", f"Session {session_id}")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/terminal/cwd', methods=['GET'])
@login_required
def terminal_get_cwd():
    username = session.get('username')
    cwd = get_terminal_cwd(username)
    return jsonify({'success': True, 'cwd': cwd})

@app.route('/api/process/start', methods=['POST'])
@login_required
def start_process():
    username = session.get('username')
    data = request.json
    name = data['name']
    command = data['command']
    cwd = data.get('cwd', get_user_path(username))
    
    if name in running_processes:
        return jsonify({'success': False, 'message': 'Process name already exists'})
    
    def run_process():
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
    
    threading.Thread(target=run_process, daemon=True).start()
    
    processes = load_processes()
    processes[name] = {
        'command': command,
        'status': 'running',
        'owner': username,
        'started': time.time()
    }
    save_processes(processes)
    
    log_activity(username, "PROCESS_START", name)
    return jsonify({'success': True, 'message': f'✅ Started {name} with UNLIMITED resources'})

@app.route('/api/process/stop', methods=['POST'])
@login_required
def stop_process():
    username = session.get('username')
    data = request.json
    name = data['name']
    
    if name in running_processes:
        proc_info = running_processes[name]
        if proc_info['owner'] != username and username != MASTER_USERNAME:
            return jsonify({'success': False, 'error': 'Permission denied'})
        
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

@app.route('/api/process/restart', methods=['POST'])
@login_required
def restart_process():
    data = request.json
    name = data['name']
    
    processes = load_processes()
    if name in processes:
        command = processes[name]['command']
        stop_process()
        time.sleep(1)
        return start_process()
    
    return jsonify({'success': False, 'error': 'Process not found'})

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
            'packets_recv': net_io.packets_recv,
            'errin': net_io.errin,
            'errout': net_io.errout
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
            
            service = ''
            try:
                service = socket.getservbyport(port)
            except:
                pass
            
            results.append({
                'port': port,
                'open': result == 0,
                'service': service
            })
        except:
            results.append({'port': port, 'open': False, 'service': ''})
    
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
                'expiry': user_data.get('expiry'),
                'created': user_data.get('created')
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
        return jsonify({'success': False, 'message': 'Username and password required'})
    
    if username == MASTER_USERNAME:
        return jsonify({'success': False, 'message': 'Cannot add master'})
    
    users = load_users()
    if username in users:
        return jsonify({'success': False, 'message': 'User already exists'})
    
    users[username] = {
        'password': hashlib.sha256(password.encode()).hexdigest(),
        'max_sessions': int(max_sessions),
        'created': datetime.now().isoformat(),
        'expiry': expiry
    }
    save_users(users)
    ensure_user_folder(username)
    
    log_activity(MASTER_USERNAME, "USER_ADD", username)
    return jsonify({'success': True, 'message': f'✅ Added user: {username}'})

@app.route('/api/users/delete', methods=['POST'])
@master_required
def delete_user_api():
    data = request.json
    username = data.get('username')
    
    if username == MASTER_USERNAME:
        return jsonify({'success': False, 'message': 'Cannot delete master'})
    
    users = load_users()
    if username not in users:
        return jsonify({'success': False, 'message': 'User not found'})
    
    del users[username]
    save_users(users)
    
    user_folder = os.path.join(USERS_FOLDER, username)
    if os.path.exists(user_folder):
        shutil.rmtree(user_folder)
    
    log_activity(MASTER_USERNAME, "USER_DELETE", username)
    return jsonify({'success': True, 'message': f'✅ Deleted user: {username}'})

@app.route('/api/master/folders')
@master_required
def master_folders():
    folders = []
    if os.path.exists(USERS_FOLDER):
        folders = [f for f in os.listdir(USERS_FOLDER) if os.path.isdir(os.path.join(USERS_FOLDER, f))]
    return jsonify({'success': True, 'folders': folders})

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
        'user': data.get('user', 'all'),
        'created': datetime.now().isoformat()
    }
    save_schedules(schedules)
    
    log_activity(MASTER_USERNAME, "SCHEDULE_ADD", data.get('name'))
    return jsonify({'success': True, 'message': 'Schedule added'})

@app.route('/api/schedules/delete', methods=['POST'])
@master_required
def delete_schedule():
    data = request.json
    schedules = load_schedules()
    if data['id'] in schedules:
        del schedules[data['id']]
        save_schedules(schedules)
    return jsonify({'success': True})

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
    name = data.get('name', f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    backup_type = data.get('type', 'full')
    
    backup_path = os.path.join(BACKUPS_FOLDER, f"{name}.tar.gz")
    
    try:
        with tarfile.open(backup_path, 'w:gz') as tar:
            if backup_type == 'full':
                tar.add(BASE_PATH, arcname='backup')
            elif backup_type == 'users':
                tar.add(USERS_FOLDER, arcname='users')
            elif backup_type == 'config':
                for f in [USERS_FILE, PROCESSES_FILE, SCHEDULES_FILE]:
                    if os.path.exists(f):
                        tar.add(f, arcname=os.path.basename(f))
        
        log_activity(MASTER_USERNAME, "BACKUP_CREATE", name)
        return jsonify({'success': True, 'message': f'✅ Backup created: {name}'})
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
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', pkg],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        packages = load_packages()
        if pkg not in packages['pip']:
            packages['pip'].append(pkg)
            save_packages(packages)
        
        log_activity(MASTER_USERNAME, "PIP_INSTALL", pkg)
        return jsonify({'success': True, 'message': f'✅ Installed: {pkg}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/packages/install/apt', methods=['POST'])
@master_required
def install_apt():
    pkg = request.json.get('package')
    try:
        result = subprocess.run(
            ['apt-get', 'install', '-y', pkg],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        packages = load_packages()
        if pkg not in packages['apt']:
            packages['apt'].append(pkg)
            save_packages(packages)
        
        log_activity(MASTER_USERNAME, "APT_INSTALL", pkg)
        return jsonify({'success': True, 'message': f'✅ Installed: {pkg}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/docker/list')
@master_required
def list_docker():
    containers = []
    images = []
    
    try:
        result = subprocess.run(['docker', 'ps', '-a', '--format', '{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}'],
                              capture_output=True, text=True)
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split('|')
                if len(parts) >= 4:
                    containers.append({
                        'id': parts[0][:12],
                        'name': parts[1],
                        'image': parts[2],
                        'status': parts[3]
                    })
        
        result = subprocess.run(['docker', 'images', '--format', '{{.Repository}}|{{.Tag}}|{{.Size}}'],
                              capture_output=True, text=True)
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split('|')
                if len(parts) >= 3:
                    images.append({
                        'repo': parts[0],
                        'tag': parts[1],
                        'size': parts[2]
                    })
    except:
        pass
    
    return jsonify({'containers': containers, 'images': images})

@app.route('/api/docker/run', methods=['POST'])
@master_required
def run_docker():
    data = request.json
    image = data.get('image')
    name = data.get('name', '')
    ports = data.get('ports', '')
    
    try:
        cmd = ['docker', 'run', '-d']
        if name:
            cmd.extend(['--name', name])
        if ports:
            for p in ports.split(','):
                cmd.extend(['-p', p.strip()])
        cmd.append(image)
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        log_activity(MASTER_USERNAME, "DOCKER_RUN", image)
        return jsonify({'success': True, 'message': f'✅ Container started', 'output': result.stdout})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/logs')
@master_required
def get_logs():
    try:
        if os.path.exists(LOGS_FILE):
            with open(LOGS_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                logs = f.read()
            return jsonify({'logs': logs[-50000:]})  # Last 50KB
        return jsonify({'logs': 'No logs available'})
    except:
        return jsonify({'logs': 'Error reading logs'})

@app.route('/api/logs/clear', methods=['POST'])
@master_required
def clear_logs():
    try:
        with open(LOGS_FILE, 'w', encoding='utf-8') as f:
            f.write(f"[{datetime.now()}] SYSTEM: Logs cleared\\n")
        return jsonify({'success': True})
    except:
        return jsonify({'success': False})

if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     🔥 ˣᶜᵀ 𝒙 𝑻𝒆𝒂𝑴 - UNLIMITED VPS CONTROL PANEL 🔥          ║
║                                                              ║
║     Resources: UNLIMITED ∞                                   ║
║     Port: 3066 (Lunes Host)                                  ║
║     Master: VeNoM / VeNoM                                    ║
║                                                              ║
║     Features:                                                ║
║     ✓ File Manager                                           ║
║     ✓ Terminal Access                                        ║
║     ✓ Process Manager                                        ║
║     ✓ Network Tools                                          ║
║     ✓ Code Editor                                            ║
║     ✓ User Management                                        ║
║     ✓ Cron Jobs                                              ║
║     ✓ Backup System                                          ║
║     ✓ Package Manager                                        ║
║     ✓ Docker Support                                         ║
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
