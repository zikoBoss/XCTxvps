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
import uuid
import ast
import signal
import warnings
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
import subprocess
import json
import shutil
import zipfile
import tarfile
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from collections import deque

warnings.filterwarnings('ignore')

PROFILE_IMAGE_URL = "https://files.manuscdn.com/user_upload_by_module/session_file/310519663299109277/qXMPQJGpGmBBKCfH.png"

def set_unlimited_resources():
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
DOCKER_FILE = os.path.join(BASE_PATH, 'docker.json')
MASTER_CONFIG_FILE = os.path.join(BASE_PATH, 'master_config.json')

def init_json_file(file_path, default_data):
    if not os.path.exists(file_path):
        try:
            with open(file_path, 'w') as f:
                json.dump(default_data, f, indent=2)
        except:
            pass

def load_json_file(file_path):
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_json_file(file_path, data):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except:
        return False

def load_master_config():
    default_config = {
        'master_username': 'VeNoM',
        'master_password_hash': hashlib.sha256('VeNoM'.encode()).hexdigest(),
        'port': 3066
    }
    if not os.path.exists(MASTER_CONFIG_FILE):
        save_json_file(MASTER_CONFIG_FILE, default_config)
        return default_config
    config = load_json_file(MASTER_CONFIG_FILE)
    if not config:
        return default_config
    return config

MASTER_CONFIG = load_master_config()
MASTER_USERNAME = MASTER_CONFIG.get('master_username', 'VeNoM')
MASTER_PASSWORD_HASH = MASTER_CONFIG.get('master_password_hash', hashlib.sha256('VeNoM'.encode()).hexdigest())

for folder in [USERS_FOLDER, TEMP_FOLDER, BACKUPS_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

init_json_file(USERS_FILE, {})
init_json_file(PROCESSES_FILE, {})
init_json_file(SCHEDULES_FILE, {})
init_json_file(USER_SESSIONS_FILE, {})
init_json_file(PACKAGES_FILE, {'pip': [], 'apt': [], 'custom': []})
init_json_file(DOCKER_FILE, {'containers': [], 'images': []})
init_json_file(MASTER_CONFIG_FILE, {
    'master_username': 'VeNoM',
    'master_password_hash': hashlib.sha256('VeNoM'.encode()).hexdigest(),
    'port': 3066
})

def log_activity(username, action, details=""):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOGS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] [{username}] {action} | {details}\n")
    except:
        pass

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

def is_path_allowed(username, requested_path):
    if username == MASTER_USERNAME:
        return True
    user_path = get_user_path(username)
    try:
        real_requested = os.path.realpath(requested_path)
        real_user_path = os.path.realpath(user_path)
        return real_requested.startswith(real_user_path)
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
            'memory': {'total': mem.total, 'used': mem.used, 'percent': mem.percent},
            'disk': {'total': disk.total, 'used': disk.used, 'percent': disk.percent},
            'network': {'bytes_sent': net_io.bytes_sent, 'bytes_recv': net_io.bytes_recv},
            'uptime': time.time() - psutil.boot_time(),
            'processes': len(psutil.pids())
        }
    except:
        return {'cpu': 0, 'memory': {'percent': 0}, 'disk': {'percent': 0}, 'uptime': 0, 'processes': 0}

def extract_and_find_main(zip_path, extract_to):
    try:
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(extract_to)
        main_files = ['main.py', 'app.py', 'bot.py', 'run.py', 'start.py', 'index.py']
        for root, dirs, files in os.walk(extract_to):
            for f in files:
                if f.lower() in main_files:
                    return os.path.join(root, f)
        for root, dirs, files in os.walk(extract_to):
            for f in files:
                if f.endswith(('.py', '.js', '.php', '.sh')):
                    return os.path.join(root, f)
    except:
        pass
    return None

def validate_python_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read().strip()
        if not content:
            return False, "File is empty"
        if len(content.split()) == 1 and not content.startswith(('import', 'from', 'def', 'class', '#', 'print')):
            return False, f"File contains only one word: '{content}'"
        try:
            ast.parse(content)
            return True, "Valid Python code"
        except SyntaxError as e:
            return False, f"Python syntax error: {str(e)}"
    except:
        return True, ""

def auto_install_dependencies(filepath):
    installed = []
    failed = []
    try:
        current_dir = os.path.dirname(filepath)
        for _ in range(3):
            req_path = os.path.join(current_dir, 'requirements.txt')
            if os.path.exists(req_path):
                try:
                    result = subprocess.run(
                        [sys.executable, '-m', 'pip', 'install', '-r', req_path],
                        capture_output=True, text=True, timeout=300
                    )
                    if result.returncode == 0:
                        installed.append('requirements.txt')
                    else:
                        failed.append('requirements.txt')
                except:
                    failed.append('requirements.txt')
                break
            current_dir = os.path.dirname(current_dir)
        
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
                packages = re.findall(r'^(?:import|from)\s+([a-zA-Z0-9_]+)', content, re.MULTILINE)
        
        elif filepath.endswith('.js'):
            packages = re.findall(r'require\([\'"]([^\'"]+)[\'"]\)', content)
            packages.extend(re.findall(r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]', content))
        
        package_map = {
            'telegram': 'python-telegram-bot',
            'telebot': 'pyTelegramBotAPI',
            'discord': 'discord.py',
            'PIL': 'Pillow',
            'cv2': 'opencv-python',
            'sklearn': 'scikit-learn',
            'flask_sqlalchemy': 'Flask-SQLAlchemy',
            'flask_cors': 'Flask-Cors',
            'bs4': 'beautifulsoup4',
            'yaml': 'PyYAML',
            'dotenv': 'python-dotenv',
            'mysql': 'mysql-connector-python',
            'psycopg2': 'psycopg2-binary',
            'pymongo': 'pymongo',
            'redis': 'redis',
            'requests': 'requests',
            'aiohttp': 'aiohttp',
            'selenium': 'selenium',
            'pandas': 'pandas',
            'numpy': 'numpy',
            'matplotlib': 'matplotlib',
            'tensorflow': 'tensorflow',
            'torch': 'torch',
            'fastapi': 'fastapi',
            'uvicorn': 'uvicorn',
            'gunicorn': 'gunicorn',
            'django': 'Django',
            'boto3': 'boto3',
            'paramiko': 'paramiko',
            'docker': 'docker',
            'pyyaml': 'PyYAML',
            'click': 'click',
            'rich': 'rich',
            'tqdm': 'tqdm',
            'python-telegram-bot': 'python-telegram-bot',
            'telethon': 'telethon',
            'pyrogram': 'pyrogram',
            'discord.py': 'discord.py',
            'youtube_dl': 'youtube-dl',
            'yt_dlp': 'yt-dlp',
            'spotipy': 'spotipy',
            'tweepy': 'tweepy',
            'praw': 'praw',
            'wikipedia': 'wikipedia',
            'pyautogui': 'pyautogui',
            'keyboard': 'keyboard',
            'opencv-python': 'opencv-python',
            'pillow': 'Pillow',
            'pygame': 'pygame',
            'kivy': 'kivy',
            'pyqt5': 'PyQt5',
            'tkinter': 'tk',
        }
        
        std_libs = ['os', 'sys', 'time', 'json', 're', 'math', 'random', 'datetime', 
                    'threading', 'subprocess', 'collections', 'io', 'typing', 'abc',
                    'flask', 'requests', 'psutil', 'hashlib', 'base64', 'uuid',
                    'socket', 'platform', 'signal', 'warnings', 'gc', 'resource',
                    'shutil', 'zipfile', 'tarfile', 'secrets', 'functools', 'itertools',
                    'string', 'textwrap', 'pathlib', 'glob', 'tempfile', 'contextlib']
        
        for pkg in set(packages):
            if pkg and not pkg.startswith('.') and pkg not in std_libs:
                actual_pkg = package_map.get(pkg, pkg)
                try:
                    result = subprocess.run(
                        [sys.executable, '-m', 'pip', 'install', '--user', actual_pkg],
                        capture_output=True, text=True, timeout=120
                    )
                    if result.returncode == 0:
                        installed.append(actual_pkg)
                        print(f"[AUTO-INSTALL] ✅ {actual_pkg}")
                    else:
                        failed.append(actual_pkg)
                        print(f"[AUTO-INSTALL] ❌ {actual_pkg}")
                except subprocess.TimeoutExpired:
                    failed.append(actual_pkg)
                    print(f"[AUTO-INSTALL] ⏱️ Timeout: {actual_pkg}")
                except Exception as e:
                    failed.append(actual_pkg)
                    print(f"[AUTO-INSTALL] ❌ Error: {actual_pkg} - {e}")
        
        return {'installed': installed, 'failed': failed}
        
    except Exception as e:
        print(f"[AUTO-INSTALL ERROR] {e}")
        return {'installed': installed, 'failed': failed + [str(e)]}

def get_run_command(filepath):
    ext = filepath.split('.')[-1].lower()
    commands = {
        'py': f'python3 -u "{filepath}"',
        'js': f'node "{filepath}"',
        'php': f'php "{filepath}"',
        'sh': f'bash "{filepath}"',
        'bash': f'bash "{filepath}"',
        'rb': f'ruby "{filepath}"',
        'pl': f'perl "{filepath}"',
        'lua': f'lua "{filepath}"',
        'go': f'go run "{filepath}"',
        'java': f'java "{filepath}"',
        'class': f'java "{os.path.splitext(filepath)[0]}"',
        'jar': f'java -jar "{filepath}"',
        'c': f'gcc "{filepath}" -o "{os.path.splitext(filepath)[0]}" && "{os.path.splitext(filepath)[0]}"',
        'cpp': f'g++ "{filepath}" -o "{os.path.splitext(filepath)[0]}" && "{os.path.splitext(filepath)[0]}"',
        'rs': f'rustc "{filepath}" && "{os.path.splitext(filepath)[0]}"',
        'swift': f'swift "{filepath}"',
        'kt': f'kotlinc -script "{filepath}"',
        'dart': f'dart "{filepath}"',
        'r': f'Rscript "{filepath}"',
        'jl': f'julia "{filepath}"',
    }
    return commands.get(ext, f'python3 -u "{filepath}"')

running_processes = {}
file_processes = {}

def read_process_output(proc_id, process, max_lines=1000):
    output_buffer = deque(maxlen=max_lines)
    try:
        for line in iter(process.stdout.readline, ''):
            if proc_id not in file_processes:
                break
            output_buffer.append(line.strip())
            file_processes[proc_id]['output'] = list(output_buffer)
    except:
        pass

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'Session expired'}), 401
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

def master_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('username') != MASTER_USERNAME:
            return jsonify({'success': False, 'error': 'Master only'}), 403
        return f(*args, **kwargs)
    return decorated_function

def get_html_template(is_master):
    master_tabs = """
            <hr>
            <li onclick="showTab('users'); toggleSidebar('mainMenu')">👑 إدارة المستخدمين</li>
            <li onclick="showTab('schedules'); toggleSidebar('mainMenu')">⏰ المهام المجدولة</li>
            <li onclick="showTab('backups'); toggleSidebar('mainMenu')">💾 النسخ الاحتياطي</li>
            <li onclick="showTab('packages'); toggleSidebar('mainMenu')">📦 إدارة الحزم</li>
            <li onclick="showTab('docker'); toggleSidebar('mainMenu')">🐳 Docker</li>
            <li onclick="showTab('logs'); toggleSidebar('mainMenu')">📝 سجل النشاطات</li>
            <li onclick="showTab('masterSettings'); toggleSidebar('mainMenu')">⚙️ إعدادات المالك</li>
    """ if is_master else ""
    
    master_tabs_content = """
            <div id="users" class="tab-content">
                <h3>➕ إضافة مستخدم</h3>
                <input type="text" id="newUsername" placeholder="اسم المستخدم" style="width:100%;">
                <input type="password" id="newPassword" placeholder="كلمة المرور" style="width:100%;">
                <input type="number" id="maxSessions" placeholder="الحد الأقصى للجلسات" value="999" style="width:100%;">
                <input type="date" id="expiryDate" placeholder="تاريخ الانتهاء" style="width:100%;">
                <button onclick="addUser()" class="success-btn">➕ إضافة</button>
                <h3 style="margin-top:20px;">👥 المستخدمين</h3>
                <div id="userList"></div>
            </div>
            <div id="schedules" class="tab-content">
                <h3>⏰ إضافة مهمة مجدولة</h3>
                <input type="text" id="cronName" placeholder="اسم المهمة" style="width:100%;">
                <input type="text" id="cronCommand" placeholder="الأمر" style="width:100%;">
                <input type="text" id="cronSchedule" placeholder="الجدول (*/5 * * * *)" value="*/5 * * * *" style="width:100%;">
                <button onclick="addSchedule()" class="success-btn">➕ إضافة</button>
                <h3 style="margin-top:20px;">📋 المهام النشطة</h3>
                <div id="scheduleList"></div>
            </div>
            <div id="backups" class="tab-content">
                <h3>💾 النسخ الاحتياطي</h3>
                <button onclick="createBackup()" class="success-btn">💾 إنشاء نسخة احتياطية</button>
                <button onclick="refreshBackups()">🔄 تحديث القائمة</button>
                <h3 style="margin-top:20px;">📂 النسخ المتوفرة</h3>
                <div id="backupList"></div>
            </div>
            <div id="packages" class="tab-content">
                <h3>📦 تثبيت حزم pip</h3>
                <input type="text" id="pipPackage" placeholder="اسم الحزمة" style="width:100%;">
                <button onclick="installPip()" class="success-btn">📥 تثبيت</button>
                <h3 style="margin-top:20px;">📋 الحزم المثبتة</h3>
                <div id="packageList"></div>
            </div>
            <div id="docker" class="tab-content">
                <h3>🐳 إدارة Docker</h3>
                <input type="text" id="dockerImage" placeholder="اسم الصورة (nginx:latest)" style="width:100%;">
                <input type="text" id="dockerName" placeholder="اسم الحاوية (اختياري)" style="width:100%;">
                <input type="text" id="dockerPorts" placeholder="المنافذ (80:8080)" style="width:100%;">
                <button onclick="runDocker()" class="success-btn">🐳 تشغيل حاوية</button>
                <button onclick="refreshDocker()">🔄 تحديث</button>
                <h3 style="margin-top:20px;">📦 الحاويات النشطة</h3>
                <div id="dockerContainers"></div>
            </div>
            <div id="logs" class="tab-content">
                <h3>📝 سجل النشاطات</h3>
                <button onclick="refreshLogs()">🔄 تحديث</button>
                <button onclick="clearLogs()" class="danger-btn">🗑️ مسح السجلات</button>
                <input type="text" id="logFilter" placeholder="تصفية السجلات..." style="width:100%; margin-top:10px;" onkeyup="filterLogs()">
                <pre id="logViewer" style="background:#0a0e27; padding:15px; border-radius:10px; max-height:400px; overflow-y:auto; font-size:0.8em; color:#00ffcc; margin-top:10px;"></pre>
            </div>
            <div id="masterSettings" class="tab-content">
                <div style="display:grid; gap:20px;">
                    <div style="background:rgba(0,0,0,0.4); border:1px solid #ff66cc55; border-radius:12px; padding:20px;">
                        <h3 style="color:#ff66cc;">👑 تغيير اسم المستخدم الرئيسي</h3>
                        <input type="text" id="newMasterUsername" placeholder="اسم المستخدم الجديد" style="width:100%;">
                        <button onclick="changeMasterUsername()" class="master-btn">💾 حفظ التغيير</button>
                        <p style="color:#ffcc00; font-size:0.8em; margin-top:10px;">⚠️ سيتم تسجيل الخروج بعد التغيير</p>
                    </div>
                    <div style="background:rgba(0,0,0,0.4); border:1px solid #ff66cc55; border-radius:12px; padding:20px;">
                        <h3 style="color:#ff66cc;">🔐 تغيير كلمة المرور</h3>
                        <input type="password" id="currentPassword" placeholder="كلمة المرور الحالية" style="width:100%;">
                        <input type="password" id="newMasterPassword" placeholder="كلمة المرور الجديدة" style="width:100%;">
                        <input type="password" id="confirmMasterPassword" placeholder="تأكيد كلمة المرور" style="width:100%;">
                        <button onclick="changeMasterPassword()" class="master-btn">🔒 تغيير كلمة المرور</button>
                    </div>
                    <div style="background:rgba(0,0,0,0.4); border:1px solid #ff66cc55; border-radius:12px; padding:20px;">
                        <h3 style="color:#ff66cc;">🌐 تغيير منفذ التشغيل</h3>
                        <input type="number" id="newPort" placeholder="المنفذ الجديد" value="3066" style="width:100%;">
                        <button onclick="changePort()" class="master-btn">🔄 تغيير المنفذ</button>
                        <p style="color:#ffcc00; font-size:0.8em; margin-top:10px;">⚠️ سيتم إعادة تشغيل السيرفر بعد التغيير</p>
                    </div>
                    <div style="background:rgba(0,0,0,0.4); border:1px solid #ff66cc55; border-radius:12px; padding:20px;">
                        <h3 style="color:#ff66cc;">🔄 إعادة تشغيل اللوحة</h3>
                        <button onclick="restartPanel()" class="danger-btn">🔄 إعادة تشغيل اللوحة</button>
                        <p style="color:#ffcc00; font-size:0.8em; margin-top:10px;">⚠️ سيتم إعادة تشغيل السيرفر، جميع العمليات ستتوقف</p>
                    </div>
                </div>
            </div>
    """ if is_master else ""

    return '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VeNoM - UNLIMITED VPS</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 50%, #0d1329 100%); font-family: 'Cairo', sans-serif; color: #00ffcc; min-height: 100vh; }
        .welcome-modal { display: flex; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 9999; justify-content: center; align-items: center; backdrop-filter: blur(10px); }
        .welcome-card { background: linear-gradient(145deg, #0a0e27, #1a1f3a); border: 3px solid #00ffcc; border-radius: 20px; padding: 40px; max-width: 500px; width: 90%; text-align: center; }
        .welcome-icon { font-size: 5em; margin-bottom: 20px; }
        .welcome-title { font-size: 2.5em; background: linear-gradient(90deg, #00ffcc, #ff66cc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 20px; }
        .welcome-info { background: rgba(0,0,0,0.5); border-radius: 15px; padding: 20px; margin: 20px 0; text-align: right; }
        .welcome-info p { margin: 10px 0; font-size: 1.2em; }
        .welcome-info .label { color: #ff66cc; font-weight: bold; }
        .welcome-info .value { color: #00ffcc; font-family: monospace; font-size: 1.3em; }
        .countdown-bar { width: 100%; height: 5px; background: #333; border-radius: 5px; margin-top: 20px; overflow: hidden; }
        .countdown-fill { height: 100%; background: linear-gradient(90deg, #00ffcc, #ff66cc); width: 100%; animation: countdownShrink 10s linear forwards; }
        @keyframes countdownShrink { from { width: 100%; } to { width: 0%; } }
        .sidebar { height: 100%; width: 0; position: fixed; z-index: 1000; top: 0; right: 0; background: linear-gradient(145deg, #0a0e27, #1a1f3a); overflow-x: hidden; transition: 0.3s; padding-top: 60px; border-right: 1px solid #00ffcc; }
        .sidebar.active { width: 350px; }
        .sidebar-header { display: flex; justify-content: space-between; padding: 15px 20px; border-bottom: 1px solid #00ffcc55; position: absolute; top: 0; right: 0; left: 0; }
        .sidebar-header h3 { color: #ff66cc; }
        .sidebar .close-btn { font-size: 30px; background: none; border: none; color: #00ffcc; cursor: pointer; }
        .sidebar ul { list-style: none; padding: 0; }
        .sidebar ul li { padding: 15px 25px; border-bottom: 1px solid #00ffcc22; cursor: pointer; }
        .sidebar ul li:hover { background: #00ffcc22; }
        .profile-image { width: 120px; height: 120px; border-radius: 50%; border: 3px solid #00ffcc; margin: 0 auto 15px; display: block; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 2000; justify-content: center; align-items: center; }
        .modal.active { display: flex; }
        .modal-content { background: #0a0e27; border: 2px solid #00ffcc; border-radius: 15px; padding: 20px; width: 90%; max-width: 900px; max-height: 85vh; }
        .console-output { background: #000; color: #00ff00; font-family: monospace; padding: 15px; height: 350px; overflow-y: auto; border-radius: 10px; margin: 15px 0; }
        .console-input-area { display: flex; gap: 10px; }
        .console-input { flex: 1; background: #0a0e27; border: 1px solid #00ffcc55; color: #00ffcc; padding: 10px; border-radius: 8px; }
        .top-bar { display: flex; padding: 12px 20px; background: rgba(0,0,0,0.8); border-bottom: 1px solid #00ffcc; gap: 10px; flex-wrap: wrap; }
        .menu-btn { background: #00ffcc22; border: 1px solid #00ffcc; color: #00ffcc; padding: 10px 18px; border-radius: 8px; cursor: pointer; }
        .menu-btn:hover { background: #00ffcc; color: #0a0e27; }
        .top-title { flex: 1; text-align: center; font-size: 1.3em; background: linear-gradient(90deg, #00ffcc, #ff66cc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .back-btn { background: #ffcc0022; border: 1px solid #ffcc00; color: #ffcc00; padding: 10px 18px; border-radius: 8px; cursor: pointer; }
        .logout-btn { background: #dc3545; color: white; border: none; padding: 10px 18px; border-radius: 8px; cursor: pointer; }
        .main-content { padding: 20px; max-width: 1600px; margin: 0 auto; }
        .stats-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 15px; margin-bottom: 25px; }
        .stat-card { background: rgba(0,0,0,0.6); border: 1px solid #00ffcc55; border-radius: 12px; padding: 15px; text-align: center; }
        .stat-value { font-size: 1.8em; color: #00ffcc; }
        .progress-bar { height: 8px; background: #333; border-radius: 4px; margin-top: 10px; }
        .progress-fill { height: 100%; background: #00ffcc; width: 0%; }
        .tabs-container { background: rgba(0,0,0,0.6); border-radius: 15px; padding: 20px; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        button { background: #0a0e27; border: 1px solid #00ffcc; color: #00ffcc; padding: 8px 16px; border-radius: 8px; cursor: pointer; margin: 3px; }
        button:hover { background: #00ffcc; color: #0a0e27; }
        .success-btn { background: #28a745; color: white; border: none; }
        .danger-btn { background: #dc3545; color: white; border: none; }
        .console-btn { background: #6f42c1; color: white; border: none; }
        .master-btn { background: linear-gradient(45deg, #ff66cc, #ff3399); color: white; border: none; }
        input, textarea { background: #0a0e27; border: 1px solid #00ffcc55; color: #00ffcc; padding: 10px; border-radius: 8px; }
        .terminal { background: #000; color: #00ff00; font-family: monospace; padding: 15px; height: 350px; overflow-y: auto; border-radius: 10px; }
        .file-list { list-style: none; }
        .file-item { padding: 12px; border-bottom: 1px solid #00ffcc22; display: flex; justify-content: space-between; }
        .running-indicator { color: #28a745; animation: blink 1s infinite; }
        @keyframes blink { 50% { opacity: 0.5; } }
        @media (max-width: 768px) { .stats-grid { grid-template-columns: repeat(2, 1fr); } }
    </style>
</head>
<body>
    <div id="welcomeModal" class="welcome-modal">
        <div class="welcome-card">
            <div class="welcome-icon">🔥</div>
            <h1 class="welcome-title">أهلاً بك في UNLIMITED VPS</h1>
            <div class="welcome-info">
                <p><span class="label">👤 اسم المستخدم:</span> <span class="value">{{ session.username }}</span></p>
                <p><span class="label">🖥️ حالة VPS:</span> <span class="value" style="color: #28a745;">● نشط</span></p>
                <p><span class="label">📅 تاريخ الدخول:</span> <span class="value" id="welcomeTime"></span></p>
                <p><span class="label">🔥 الموارد:</span> <span class="value" style="color: #ff6600;">غير محدودة ∞</span></p>
            </div>
            <p style="color: #ff66cc;">🎉 مرحباً بعودتك!</p>
            <div class="welcome-footer">
                <span id="countdownText">تختفي الرسالة خلال 10 ثواني</span>
                <div class="countdown-bar"><div class="countdown-fill"></div></div>
            </div>
        </div>
    </div>

    <div id="consoleModal" class="modal">
        <div class="modal-content">
            <div style="display:flex; justify-content:space-between;">
                <span>🖥️ كونسول - <span id="consoleFilename"></span></span>
                <button onclick="closeConsole()" style="font-size:24px;">×</button>
            </div>
            <div class="console-output" id="consoleOutput">⏳ في انتظار المخرجات...</div>
            <div class="console-input-area">
                <input type="text" id="consoleInput" class="console-input" placeholder="أرسل أمراً..." onkeypress="if(event.keyCode==13) sendConsoleInput()">
                <button onclick="sendConsoleInput()" class="success-btn">📤</button>
                <button onclick="clearConsoleOutput()">🗑️</button>
            </div>
        </div>
    </div>

    <div class="top-bar">
        <button class="menu-btn" onclick="toggleSidebar('mainMenu')">☰ القائمة</button>
        <button class="menu-btn" onclick="toggleSidebar('profileMenu'); loadProfileData()">👤 الملف الشخصي</button>
        <button class="menu-btn" onclick="toggleSidebar('toolsMenu')">⚙️ أدوات</button>
        <span class="top-title">🔥 VeNoM UNLIMITED VPS</span>
        <button onclick="goBack()" class="back-btn">↩️ رجوع</button>
        <a href="/logout"><button class="logout-btn">🚪 خروج</button></a>
    </div>

    <div id="mainMenu" class="sidebar">
        <div class="sidebar-header"><h3>📋 القائمة</h3><button class="close-btn" onclick="toggleSidebar('mainMenu')">×</button></div>
        <ul>
            <li onclick="showTab('files'); toggleSidebar('mainMenu')">📁 الملفات</li>
            <li onclick="showTab('terminal'); toggleSidebar('mainMenu')">🖥️ التيرمنال</li>
            <li onclick="showTab('processes'); toggleSidebar('mainMenu')">⚙️ العمليات</li>
            <li onclick="showTab('network'); toggleSidebar('mainMenu')">🌐 الشبكة</li>
            <li onclick="showTab('editor'); toggleSidebar('mainMenu')">📝 المحرر</li>
            <li onclick="showTab('info'); toggleSidebar('mainMenu')">ℹ️ النظام</li>
            ''' + master_tabs + '''
        </ul>
    </div>

    <div id="profileMenu" class="sidebar">
        <div class="sidebar-header"><h3>👤 الملف الشخصي</h3><button class="close-btn" onclick="toggleSidebar('profileMenu')">×</button></div>
        <div style="padding:20px; text-align:center;">
            <img src="''' + PROFILE_IMAGE_URL + '''" alt="Profile" class="profile-image" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>👤</text></svg>'">
            <h2 style="color:#ff66cc;">{{ session.username }}</h2>
            <hr>
            <div id="profileDetails">⏳ جاري التحميل...</div>
        </div>
    </div>

    <div id="toolsMenu" class="sidebar">
        <div class="sidebar-header"><h3>⚡ أدوات</h3><button class="close-btn" onclick="toggleSidebar('toolsMenu')">×</button></div>
        <ul>
            <li onclick="runQuickAction('update')">🔄 تحديث</li>
            <li onclick="runQuickAction('clean')">🧹 تنظيف</li>
            <li onclick="killAllProcesses()">⏹️ إيقاف الكل</li>
        </ul>
    </div>

    <div class="main-content">
        <div class="stats-grid">
            <div class="stat-card"><div>💻 المعالج</div><div class="stat-value" id="cpu">0%</div><div class="progress-bar"><div class="progress-fill" id="cpuFill"></div></div></div>
            <div class="stat-card"><div>🧠 الذاكرة</div><div class="stat-value" id="ram">0%</div><div class="progress-bar"><div class="progress-fill" id="ramFill"></div></div></div>
            <div class="stat-card"><div>💾 القرص</div><div class="stat-value" id="disk">0%</div><div class="progress-bar"><div class="progress-fill" id="diskFill"></div></div></div>
            <div class="stat-card"><div>⏱️ المدة</div><div class="stat-value" id="uptime">0h</div></div>
            <div class="stat-card"><div>🔄 العمليات</div><div class="stat-value" id="processes">0</div></div>
            <div class="stat-card"><div>🌐 الشبكة</div><div class="stat-value">↓<span id="netIn">0</span> ↑<span id="netOut">0</span></div></div>
        </div>

        <div class="tabs-container">
            <div id="files" class="tab-content active">
                <div style="margin-bottom:15px;">
                    <input type="file" id="uploadFile" multiple>
                    <button onclick="uploadFiles()" class="success-btn">📤 رفع</button>
                    <button onclick="refreshFiles()">🔄 تحديث</button>
                    <button onclick="createFolder()">📁 مجلد</button>
                    <button onclick="createFile()">📄 ملف</button>
                    <span>📍 <span id="currentPathDisplay"></span></span>
                </div>
                <div id="fileBrowser"></div>
            </div>
            <div id="terminal" class="tab-content">
                <div class="terminal" id="terminalOutput">$ VeNoM UNLIMITED VPS</div>
                <div style="display:flex; margin-top:10px;"><span>$</span><input type="text" id="cmdInput" placeholder="أمر..." style="flex:1;" onkeypress="if(event.keyCode==13) execCommand()"><button onclick="execCommand()" class="success-btn">⚡</button><button onclick="clearTerminal()">🗑️</button></div>
            </div>
            <div id="processes" class="tab-content">
                <div><input type="text" id="procName" placeholder="اسم"><input type="text" id="procCommand" placeholder="أمر"><button onclick="startProcess()" class="success-btn">▶️</button><button onclick="refreshProcesses()">🔄</button><button onclick="killAllProcesses()" class="danger-btn">⏹️</button></div>
                <div id="processList"></div>
            </div>
            <div id="network" class="tab-content">
                <h3>🔍 فحص المنافذ</h3>
                <input type="text" id="scanHost" value="localhost"><input type="text" id="scanPorts" value="80,443,8080"><button onclick="scanPorts()">فحص</button>
                <div id="scanResults"></div>
            </div>
            <div id="editor" class="tab-content">
                <input type="text" id="editFilePath" placeholder="مسار الملف" style="width:100%;"><button onclick="loadFileForEdit()">📂</button><button onclick="saveFileFromEditor()" class="success-btn">💾</button>
                <textarea id="codeEditor" style="width:100%; height:400px; background:#0a0e27; color:#00ffcc; margin-top:10px;"></textarea>
            </div>
            <div id="info" class="tab-content"><pre id="sysInfo" style="background:#0a0e27; padding:20px;"></pre></div>
            ''' + master_tabs_content + '''
        </div>
    </div>

    <script>
        let currentPath = '{{ user_path }}';
        let runningFileProcesses = {};
        let currentConsole = null;
        let consoleInterval = null;
        let originalLogs = '';
        
        (function() {
            const modal = document.getElementById('welcomeModal');
            document.getElementById('welcomeTime').innerText = new Date().toLocaleString('ar-SA');
            let s = 10;
            const t = setInterval(() => { s--; document.getElementById('countdownText').innerText = `تختفي خلال ${s} ثواني`; if(s<=0) { clearInterval(t); modal.style.display = 'none'; } }, 1000);
            modal.onclick = () => { clearInterval(t); modal.style.display = 'none'; };
        })();

        function toggleSidebar(id) { document.getElementById(id).classList.toggle('active'); }
        window.onclick = e => { if(!e.target.matches('.menu-btn') && !e.target.closest('.sidebar')) document.querySelectorAll('.sidebar').forEach(s => s.classList.remove('active')); };
        function goBack() { if(currentPath !== '{{ user_path }}') { let p = currentPath.substring(0, currentPath.lastIndexOf('/')); if(!p || p === '/home/container/users_data') p = '{{ user_path }}'; currentPath = p; refreshFiles(); } }
        function showTab(id) { document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active')); document.getElementById(id).classList.add('active'); if(id==='files') refreshFiles(); if(id==='processes') refreshProcesses(); if(id==='info') refreshSysInfo(); if(id==='users') refreshUsers(); if(id==='schedules') refreshSchedules(); if(id==='backups') refreshBackups(); if(id==='packages') refreshPackages(); if(id==='docker') refreshDocker(); if(id==='logs') refreshLogs(); }
        
        async function syncRunningFiles() {
            try {
                const r = await fetch('/api/file/running');
                const d = await r.json();
                if(d.success) {
                    runningFileProcesses = {};
                    d.running.forEach(item => {
                        runningFileProcesses[item.filename] = item.process_id;
                    });
                    if(document.getElementById('files').classList.contains('active')) {
                        refreshFiles();
                    }
                }
            } catch(e) {}
        }
        
        function openConsole(fn, pid) { currentConsole = {fn, pid}; document.getElementById('consoleFilename').innerText = fn; document.getElementById('consoleModal').classList.add('active'); if(consoleInterval) clearInterval(consoleInterval); consoleInterval = setInterval(refreshConsoleOutput, 1000); refreshConsoleOutput(); }
        function closeConsole() { document.getElementById('consoleModal').classList.remove('active'); clearInterval(consoleInterval); }
        async function refreshConsoleOutput() { if(!currentConsole) return; const r = await fetch('/api/file/output/' + currentConsole.pid); const d = await r.json(); if(d.success) document.getElementById('consoleOutput').innerHTML = d.output.length ? d.output.join('\\n') : '⏳ لا توجد مخرجات...'; }
        async function sendConsoleInput() { if(!currentConsole) return; const inp = document.getElementById('consoleInput').value; if(!inp) return; await fetch('/api/file/input', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({process_id:currentConsole.pid, input:inp})}); document.getElementById('consoleInput').value = ''; setTimeout(refreshConsoleOutput, 500); }
        function clearConsoleOutput() { document.getElementById('consoleOutput').innerHTML = '🗑️'; }
        
        async function loadProfileData() { const r = await fetch('/api/profile'); const d = await r.json(); document.getElementById('profileDetails').innerHTML = `<p>📅 ${d.created}</p><p>⏰ ${d.expiry}</p><p>💾 ${d.disk_usage_gb.toFixed(2)} GB</p>`; }
        
        async function updateStats() {
            const r = await fetch('/api/system'); const d = await r.json();
            document.getElementById('cpu').innerText = d.cpu.toFixed(1) + '%'; document.getElementById('cpuFill').style.width = d.cpu + '%';
            document.getElementById('ram').innerText = d.memory.percent.toFixed(1) + '%'; document.getElementById('ramFill').style.width = d.memory.percent + '%';
            document.getElementById('disk').innerText = d.disk.percent.toFixed(1) + '%'; document.getElementById('diskFill').style.width = d.disk.percent + '%';
            document.getElementById('uptime').innerText = Math.floor(d.uptime/86400) + 'd ' + Math.floor((d.uptime%86400)/3600) + 'h';
            document.getElementById('processes').innerText = d.processes;
            document.getElementById('netIn').innerText = (d.network.bytes_recv/1024**2).toFixed(2);
            document.getElementById('netOut').innerText = (d.network.bytes_sent/1024**2).toFixed(2);
        }
        
        async function refreshFiles() {
            const r = await fetch('/api/files?path=' + encodeURIComponent(currentPath)); const d = await r.json();
            if(!d.success) return;
            document.getElementById('currentPathDisplay').innerText = d.path;
            let h = '<ul class="file-list">';
            if(d.can_go_up) h += '<li class="file-item"><span>📁 ..</span><button onclick="goBack()">⬆️</button></li>';
            d.files.forEach(f => {
                const run = runningFileProcesses[f.name];
                h += `<li class="file-item"><span>${f.is_dir?'📁':'📄'} ${f.name}</span><div>`;
                if(f.is_dir) h += `<button onclick="enterFolder('${f.name}')">📂</button>`;
                else { h += `<button onclick="editFile('${f.name}')">✏️</button>`; if(run) { h += `<button onclick="stopFile('${f.name}')" class="danger-btn">⏹️</button><button onclick="openConsole('${f.name}', '${runningFileProcesses[f.name]}')" class="console-btn">🖥️</button>`; } else { h += `<button onclick="runFile('${f.name}')" class="success-btn">▶️</button>`; } }
                h += `<button onclick="deleteFile('${f.name}')" class="danger-btn">🗑️</button></div></li>`;
            });
            h += '</ul>'; document.getElementById('fileBrowser').innerHTML = h;
        }
        function enterFolder(n) { currentPath += '/' + n; refreshFiles(); }
        async function runFile(n) { const r = await fetch('/api/file/run', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({filename:n, path:currentPath})}); const d = await r.json(); if(d.success) { runningFileProcesses[n] = d.process_id; refreshFiles(); let msg = '✅ ' + n; if(d.installed_result?.installed?.length) msg += '\\n📦 ' + d.installed_result.installed.join(', '); if(d.installed_result?.failed?.length) msg += '\\n❌ ' + d.installed_result.failed.join(', '); alert(msg); } else alert('❌ ' + d.error); }
        async function stopFile(n) { await fetch('/api/file/stop', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({process_id:runningFileProcesses[n]})}); delete runningFileProcesses[n]; refreshFiles(); }
        async function uploadFiles() { const fs = document.getElementById('uploadFile').files; for(let f of fs) { const fd = new FormData(); fd.append('file', f); fd.append('path', currentPath); await fetch('/api/files/upload', {method:'POST', body:fd}); } refreshFiles(); alert('✅ تم الرفع'); }
        async function createFolder() { const n = prompt('اسم المجلد'); if(n) { await fetch('/api/files/folder', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path:currentPath, name:n})}); refreshFiles(); } }
        async function createFile() { const n = prompt('اسم الملف'); if(n) { await fetch('/api/files/create', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path:currentPath, name:n})}); refreshFiles(); } }
        async function deleteFile(n) { if(confirm('حذف '+n+'؟')) { await fetch('/api/files/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path:currentPath, name:n})}); refreshFiles(); } }
        async function editFile(n) { const r = await fetch('/api/files/content?path=' + currentPath + '/' + n); const d = await r.json(); if(d.success) { document.getElementById('editFilePath').value = currentPath + '/' + n; document.getElementById('codeEditor').value = d.content; showTab('editor'); } }
        async function loadFileForEdit() { const r = await fetch('/api/files/content?path=' + document.getElementById('editFilePath').value); const d = await r.json(); if(d.success) document.getElementById('codeEditor').value = d.content; }
        async function saveFileFromEditor() { await fetch('/api/files/save', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path:document.getElementById('editFilePath').value, content:document.getElementById('codeEditor').value})}); alert('✅ تم الحفظ'); }
        
        async function execCommand() { const c = document.getElementById('cmdInput').value; if(!c) return; const t = document.getElementById('terminalOutput'); t.innerText += '\\n$ ' + c; const r = await fetch('/api/exec', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({command:c, cwd:currentPath})}); const d = await r.json(); t.innerText += '\\n' + (d.stdout || d.error || ''); document.getElementById('cmdInput').value = ''; t.scrollTop = t.scrollHeight; }
        function clearTerminal() { document.getElementById('terminalOutput').innerText = '$ '; }
        
        async function startProcess() { const n = document.getElementById('procName').value, c = document.getElementById('procCommand').value; if(!n||!c) return; await fetch('/api/process/start', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:n, command:c})}); refreshProcesses(); }
        async function refreshProcesses() { const r = await fetch('/api/process/list'); const d = await r.json(); let h = '<ul class="file-list">'; for(const [n, i] of Object.entries(d)) h += `<li class="file-item"><span>${n}</span><span style="color:${i.status==='running'?'#28a745':'#dc3545'}">${i.status}</span><button onclick="stopProcess('${n}')" class="danger-btn">⏹️</button></li>`; document.getElementById('processList').innerHTML = h; }
        async function stopProcess(n) { await fetch('/api/process/stop', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:n})}); refreshProcesses(); }
        async function killAllProcesses() { if(confirm('إيقاف الكل؟')) { await fetch('/api/process/stop-all', {method:'POST'}); refreshProcesses(); } }
        
        async function scanPorts() { const h = document.getElementById('scanHost').value, p = document.getElementById('scanPorts').value.split(',').map(x=>parseInt(x)); const r = await fetch('/api/network/scan', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({host:h, ports:p})}); const d = await r.json(); let ht = '<ul>'; d.results.forEach(r => ht += `<li style="color:${r.open?'#28a745':'#dc3545'}">${r.port}: ${r.open?'مفتوح':'مغلق'}</li>`); document.getElementById('scanResults').innerHTML = ht; }
        
        async function refreshSysInfo() { const r = await fetch('/api/sysinfo'); document.getElementById('sysInfo').innerText = (await r.json()).info; }
        async function runQuickAction(a) { await fetch('/api/system/action', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action:a})}); }
        
        async function refreshUsers() { const r = await fetch('/api/users/list'); const d = await r.json(); let h = ''; d.users.forEach(u => h += `<p>👤 ${u.username} ${u.username!='{{ session.username }}'?'<button onclick="deleteUser(\\''+u.username+'\\')">🗑️</button>':''}</p>`); document.getElementById('userList').innerHTML = h; }
        async function addUser() { const u = document.getElementById('newUsername').value, p = document.getElementById('newPassword').value, m = document.getElementById('maxSessions').value, e = document.getElementById('expiryDate').value; if(!u||!p) return; await fetch('/api/users/add', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:u, password:p, max_sessions:m, expiry:e})}); refreshUsers(); }
        async function deleteUser(u) { await fetch('/api/users/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:u})}); refreshUsers(); }
        
        async function refreshSchedules() { const r = await fetch('/api/schedules/list'); const d = await r.json(); document.getElementById('scheduleList').innerHTML = d.schedules.map(s => `<p>${s.name} - ${s.command}</p>`).join(''); }
        async function addSchedule() { const n = document.getElementById('cronName').value, c = document.getElementById('cronCommand').value, s = document.getElementById('cronSchedule').value; await fetch('/api/schedules/add', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:n, command:c, schedule:s})}); refreshSchedules(); }
        
        async function refreshBackups() { const r = await fetch('/api/backups/list'); const d = await r.json(); document.getElementById('backupList').innerHTML = d.backups.map(b => `<p>💾 ${b.name} (${b.size})</p>`).join(''); }
        async function createBackup() { await fetch('/api/backups/create', {method:'POST'}); refreshBackups(); }
        
        async function refreshPackages() { const r = await fetch('/api/packages/list'); const d = await r.json(); document.getElementById('packageList').innerHTML = d.pip.map(p => `<p>${p}</p>`).join(''); }
        async function installPip() { const p = document.getElementById('pipPackage').value; if(!p) return; await fetch('/api/packages/install/pip', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({package:p})}); refreshPackages(); }
        
        async function refreshDocker() { const r = await fetch('/api/docker/list'); const d = await r.json(); document.getElementById('dockerContainers').innerHTML = d.containers.map(c => `<p>${c.name} (${c.status})</p>`).join(''); }
        async function runDocker() { const i = document.getElementById('dockerImage').value, n = document.getElementById('dockerName').value, p = document.getElementById('dockerPorts').value; if(!i) return; await fetch('/api/docker/run', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({image:i, name:n, ports:p})}); refreshDocker(); }
        
        async function refreshLogs() { const r = await fetch('/api/logs'); const d = await r.json(); originalLogs = d.logs || ''; document.getElementById('logViewer').innerText = originalLogs; }
        async function clearLogs() { if(confirm('مسح السجلات؟')) await fetch('/api/logs/clear', {method:'POST'}); refreshLogs(); }
        function filterLogs() { const f = document.getElementById('logFilter').value.toLowerCase(); const lines = originalLogs.split('\\n'); document.getElementById('logViewer').innerText = lines.filter(l => l.toLowerCase().includes(f)).join('\\n'); }
        
        async function changeMasterUsername() { const u = document.getElementById('newMasterUsername').value; if(!u) return; await fetch('/api/master/change-username', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({new_username:u})}); alert('تم'); }
        async function changeMasterPassword() { const c = document.getElementById('currentPassword').value, n = document.getElementById('newMasterPassword').value, cf = document.getElementById('confirmMasterPassword').value; if(!c||!n||n!==cf) return alert('تأكد من البيانات'); await fetch('/api/master/change-password', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({current_password:c, new_password:n})}); alert('تم'); }
        async function changePort() { const p = document.getElementById('newPort').value; if(!p||!confirm(`تغيير المنفذ إلى ${p}؟`)) return; await fetch('/api/master/change-port', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({port:parseInt(p)})}); }
        async function restartPanel() { if(confirm('إعادة تشغيل؟')) { await fetch('/api/master/restart', {method:'POST'}); setTimeout(() => location.reload(), 3000); } }
        
        setInterval(updateStats, 3000);
        setInterval(() => { if(document.getElementById('processes').classList.contains('active')) refreshProcesses(); }, 5000);
        setInterval(syncRunningFiles, 5000);
        updateStats(); 
        syncRunningFiles().then(() => refreshFiles());
    </script>
</body>
</html>
'''

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8"><title>تسجيل الدخول - VeNoM</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { margin:0; padding:0; }
        body { background:linear-gradient(135deg,#0a0e27,#1a1f3a); font-family:'Cairo',sans-serif; min-height:100vh; display:flex; justify-content:center; align-items:center; }
        .login-container { background:rgba(0,0,0,0.8); border:2px solid #00ffcc; border-radius:20px; padding:40px; width:400px; text-align:center; }
        .login-image { width:100px; height:100px; border-radius:50%; border:3px solid #00ffcc; margin-bottom:20px; }
        h1 { background:linear-gradient(90deg,#00ffcc,#ff66cc); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
        input { width:100%; padding:14px; margin:10px 0; background:#0a0e27; border:1px solid #00ffcc55; color:#00ffcc; border-radius:8px; }
        button { width:100%; padding:14px; background:#00ffcc; color:#0a0e27; border:none; border-radius:8px; font-weight:bold; cursor:pointer; margin-top:25px; }
        .error { color:#ff3333; margin-top:15px; }
    </style>
</head>
<body>
    <div class="login-container">
        <img src="''' + PROFILE_IMAGE_URL + '''" alt="Logo" class="login-image" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🔥</text></svg>'">
        <h1>🔥 VeNoM VPS</h1>
        <form method="POST">
            <input type="text" name="username" placeholder="👤 اسم المستخدم" required>
            <input type="password" name="password" placeholder="🔒 كلمة المرور" required>
            <button type="submit">🔓 تسجيل الدخول</button>
        </form>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
    </div>
</body>
</html>
'''

@app.route('/')
@login_required
def index():
    is_master = (session.get('username') == MASTER_USERNAME)
    return render_template_string(get_html_template(is_master), session=session, user_path=get_user_path(session['username']))

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
        return redirect('/')
    users = load_users()
    if username in users and users[username].get('password') == password_hash and can_user_login(username):
        session.permanent = True
        session['logged_in'] = True
        session['username'] = username
        register_session(username)
        os.makedirs(get_user_path(username), exist_ok=True)
        return redirect('/')
    return render_template_string(LOGIN_TEMPLATE, error='❌ خطأ في البيانات')

@app.route('/logout')
def logout():
    if 'username' in session:
        unregister_session(session['username'])
    session.clear()
    return redirect('/login')

@app.route('/api/profile')
@login_required
def get_profile():
    u = session['username']
    path = get_user_path(u)
    size = 0
    if os.path.exists(path):
        for r, d, f in os.walk(path):
            for fl in f:
                fp = os.path.join(r, fl)
                if os.path.exists(fp):
                    size += os.path.getsize(fp)
    users = load_users()
    user_data = users.get(u, {})
    return jsonify({
        'created': user_data.get('created', datetime.now().isoformat()) if isinstance(user_data, dict) else datetime.now().isoformat(),
        'expiry': user_data.get('expiry', '∞') if isinstance(user_data, dict) else '∞',
        'disk_usage_gb': size/(1024**3)
    })

@app.route('/api/system')
@login_required
def system_info():
    return jsonify(get_system_stats())

@app.route('/api/sysinfo')
@login_required
def sysinfo():
    return jsonify({'info': f"Platform: {platform.platform()}\nCPU: {psutil.cpu_percent()}%\nMemory: {psutil.virtual_memory().percent}%"})

@app.route('/api/system/action', methods=['POST'])
@login_required
def system_action():
    a = request.json.get('action')
    if a == 'clean': gc.collect()
    if a == 'update': subprocess.run(['apt-get', 'update'], capture_output=True, timeout=120)
    return jsonify({'success': True})

@app.route('/api/files')
@login_required
def list_files():
    path = request.args.get('path', get_user_path(session['username']))
    if not is_path_allowed(session['username'], path): return jsonify({'success': False})
    try:
        files = os.listdir(path)
        fl = [{'name': f, 'is_dir': os.path.isdir(os.path.join(path, f)), 'size': os.path.getsize(os.path.join(path, f)) if os.path.isfile(os.path.join(path, f)) else 0} for f in files]
        return jsonify({'success': True, 'files': fl, 'path': path, 'can_go_up': path != get_user_path(session['username'])})
    except: return jsonify({'success': False})

@app.route('/api/files/upload', methods=['POST'])
@login_required
def upload_file():
    f = request.files['file']
    path = request.form.get('path')
    f.save(os.path.join(path, f.filename))
    return jsonify({'success': True})

@app.route('/api/files/folder', methods=['POST'])
@login_required
def create_folder():
    d = request.json
    os.makedirs(os.path.join(d['path'], d['name']), exist_ok=True)
    return jsonify({'success': True})

@app.route('/api/files/create', methods=['POST'])
@login_required
def create_file():
    d = request.json
    open(os.path.join(d['path'], d['name']), 'w').close()
    return jsonify({'success': True})

@app.route('/api/files/delete', methods=['POST'])
@login_required
def delete_file():
    d = request.json
    p = os.path.join(d['path'], d['name'])
    if os.path.isdir(p): shutil.rmtree(p)
    else: os.remove(p)
    return jsonify({'success': True})

@app.route('/api/files/content')
@login_required
def get_file_content():
    with open(request.args.get('path'), 'r', errors='ignore') as f:
        return jsonify({'success': True, 'content': f.read()})

@app.route('/api/files/save', methods=['POST'])
@login_required
def save_file():
    d = request.json
    with open(d['path'], 'w') as f:
        f.write(d['content'])
    return jsonify({'success': True})

@app.route('/api/file/run', methods=['POST'])
@login_required
def run_file():
    d = request.json
    filepath = os.path.join(d['path'], d['filename'])
    if d['filename'].lower().endswith('.zip'):
        extract_dir = os.path.join(d['path'], d['filename'].replace('.zip', ''))
        os.makedirs(extract_dir, exist_ok=True)
        main = extract_and_find_main(filepath, extract_dir)
        if main: filepath = main
        else: return jsonify({'success': False, 'error': 'لم يتم العثور على ملف رئيسي'})
    installed = auto_install_dependencies(filepath)
    cmd = get_run_command(filepath)
    p = subprocess.Popen(cmd, shell=True, cwd=os.path.dirname(filepath), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, preexec_fn=os.setsid, text=True, bufsize=1)
    pid = f"{session['username']}_{d['filename']}_{int(time.time())}"
    file_processes[pid] = {'process': p, 'filename': d['filename'], 'username': session['username'], 'output': []}
    threading.Thread(target=read_process_output, args=(pid, p), daemon=True).start()
    return jsonify({'success': True, 'process_id': pid, 'installed_result': installed})

@app.route('/api/file/stop', methods=['POST'])
@login_required
def stop_file():
    pid = request.json.get('process_id')
    if pid in file_processes:
        try: os.killpg(os.getpgid(file_processes[pid]['process'].pid), signal.SIGKILL)
        except: pass
        del file_processes[pid]
    return jsonify({'success': True})

@app.route('/api/file/output/<pid>')
@login_required
def get_file_output(pid):
    if pid in file_processes:
        return jsonify({'success': True, 'output': file_processes[pid].get('output', []), 'is_running': file_processes[pid]['process'].poll() is None})
    return jsonify({'success': False})

@app.route('/api/file/input', methods=['POST'])
@login_required
def send_file_input():
    d = request.json
    if d['process_id'] in file_processes:
        file_processes[d['process_id']]['process'].stdin.write(d['input'] + '\n')
        file_processes[d['process_id']]['process'].stdin.flush()
    return jsonify({'success': True})

@app.route('/api/file/running')
@login_required
def get_running_files():
    username = session['username']
    running = []
    for pid, info in file_processes.items():
        if info['username'] == username or username == MASTER_USERNAME:
            is_running = info['process'].poll() is None
            if is_running:
                running.append({'process_id': pid, 'filename': info['filename']})
            else:
                del file_processes[pid]
    return jsonify({'success': True, 'running': running})

@app.route('/api/exec', methods=['POST'])
@login_required
def execute_command():
    d = request.json
    try:
        p = subprocess.run(d['command'], shell=True, cwd=d.get('cwd', BASE_PATH), capture_output=True, text=True, timeout=30)
        return jsonify({'success': True, 'stdout': p.stdout or p.stderr or 'Done'})
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Timeout'})

@app.route('/api/process/start', methods=['POST'])
@login_required
def start_process():
    d = request.json
    def run():
        p = subprocess.Popen(d['command'], shell=True, cwd=d.get('cwd', BASE_PATH), preexec_fn=os.setsid)
        running_processes[d['name']] = {'process': p, 'owner': session['username'], 'command': d['command']}
        p.wait()
    threading.Thread(target=run, daemon=True).start()
    return jsonify({'success': True})

@app.route('/api/process/stop', methods=['POST'])
@login_required
def stop_process():
    n = request.json['name']
    if n in running_processes:
        os.killpg(os.getpgid(running_processes[n]['process'].pid), signal.SIGKILL)
        del running_processes[n]
    return jsonify({'success': True})

@app.route('/api/process/stop-all', methods=['POST'])
@login_required
def stop_all_processes():
    for p in list(running_processes.values()):
        try: os.killpg(os.getpgid(p['process'].pid), signal.SIGKILL)
        except: pass
    running_processes.clear()
    return jsonify({'success': True})

@app.route('/api/process/list')
@login_required
def list_processes():
    procs = {}
    for n, i in running_processes.items():
        procs[n] = {'status': 'running' if i['process'].poll() is None else 'stopped', 'command': i['command']}
    return jsonify(procs)

@app.route('/api/network/scan', methods=['POST'])
@login_required
def scan_ports():
    d = request.json
    results = []
    for p in d['ports']:
        s = socket.socket()
        s.settimeout(1)
        r = s.connect_ex((d['host'], p))
        results.append({'port': p, 'open': r == 0})
        s.close()
    return jsonify({'results': results})

@app.route('/api/users/list')
@master_required
def list_users():
    users = load_users()
    sessions = load_user_sessions()
    return jsonify({'users': [{'username': u, 'max_sessions': users[u].get('max_sessions', 999) if isinstance(users[u], dict) else 999, 'active_sessions': sessions.get(u, 0)} for u in users]})

@app.route('/api/users/add', methods=['POST'])
@master_required
def add_user():
    d = request.json
    users = load_users()
    users[d['username']] = {
        'password': hashlib.sha256(d['password'].encode()).hexdigest(),
        'max_sessions': int(d.get('max_sessions', 999)),
        'created': datetime.now().isoformat(),
        'expiry': d.get('expiry')
    }
    save_users(users)
    os.makedirs(os.path.join(USERS_FOLDER, d['username']), exist_ok=True)
    return jsonify({'success': True})

@app.route('/api/users/delete', methods=['POST'])
@master_required
def delete_user():
    d = request.json
    users = load_users()
    if d['username'] in users:
        del users[d['username']]
        save_users(users)
        shutil.rmtree(os.path.join(USERS_FOLDER, d['username']), ignore_errors=True)
    return jsonify({'success': True})

@app.route('/api/schedules/list')
@master_required
def list_schedules():
    return jsonify({'schedules': list(load_schedules().values())})

@app.route('/api/schedules/add', methods=['POST'])
@master_required
def add_schedule():
    d = request.json
    sch = load_schedules()
    sid = str(uuid.uuid4())[:8]
    sch[sid] = {'id': sid, 'name': d['name'], 'command': d['command'], 'schedule': d.get('schedule', '* * * * *')}
    save_schedules(sch)
    return jsonify({'success': True})

@app.route('/api/backups/list')
@master_required
def list_backups():
    backs = []
    if os.path.exists(BACKUPS_FOLDER):
        for f in os.listdir(BACKUPS_FOLDER):
            if f.endswith('.tar.gz'):
                backs.append({'name': f, 'size': f"{os.path.getsize(os.path.join(BACKUPS_FOLDER, f))/1024**2:.2f} MB"})
    return jsonify({'backups': backs})

@app.route('/api/backups/create', methods=['POST'])
@master_required
def create_backup():
    name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tar.gz"
    with tarfile.open(os.path.join(BACKUPS_FOLDER, name), 'w:gz') as tar:
        tar.add(BASE_PATH, arcname='backup')
    return jsonify({'success': True})

@app.route('/api/packages/list')
@master_required
def list_packages():
    return jsonify(load_packages())

@app.route('/api/packages/install/pip', methods=['POST'])
@master_required
def install_pip():
    pkg = request.json['package']
    subprocess.run([sys.executable, '-m', 'pip', 'install', pkg], capture_output=True)
    packages = load_packages()
    if pkg not in packages['pip']:
        packages['pip'].append(pkg)
        save_packages(packages)
    return jsonify({'success': True})

@app.route('/api/docker/list')
@master_required
def list_docker():
    containers = []
    try:
        result = subprocess.run(['docker', 'ps', '-a', '--format', '{{.Names}}|{{.Status}}'], capture_output=True, text=True)
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split('|')
                if len(parts) >= 2:
                    containers.append({'name': parts[0], 'status': parts[1]})
    except: pass
    return jsonify({'containers': containers})

@app.route('/api/docker/run', methods=['POST'])
@master_required
def run_docker():
    d = request.json
    cmd = ['docker', 'run', '-d']
    if d.get('name'): cmd.extend(['--name', d['name']])
    if d.get('ports'):
        for p in d['ports'].split(','):
            cmd.extend(['-p', p.strip()])
    cmd.append(d['image'])
    subprocess.run(cmd, capture_output=True)
    return jsonify({'success': True})

@app.route('/api/logs')
@master_required
def get_logs():
    if os.path.exists(LOGS_FILE):
        with open(LOGS_FILE, 'r') as f:
            return jsonify({'logs': f.read()[-50000:]})
    return jsonify({'logs': ''})

@app.route('/api/logs/clear', methods=['POST'])
@master_required
def clear_logs():
    with open(LOGS_FILE, 'w') as f:
        f.write(f"[{datetime.now()}] CLEARED\n")
    return jsonify({'success': True})

@app.route('/api/master/change-username', methods=['POST'])
@master_required
def change_master_username():
    global MASTER_USERNAME
    MASTER_USERNAME = request.json['new_username']
    MASTER_CONFIG['master_username'] = MASTER_USERNAME
    save_json_file(MASTER_CONFIG_FILE, MASTER_CONFIG)
    return jsonify({'success': True})

@app.route('/api/master/change-password', methods=['POST'])
@master_required
def change_master_password():
    global MASTER_PASSWORD_HASH
    d = request.json
    if hashlib.sha256(d['current_password'].encode()).hexdigest() == MASTER_PASSWORD_HASH:
        MASTER_PASSWORD_HASH = hashlib.sha256(d['new_password'].encode()).hexdigest()
        MASTER_CONFIG['master_password_hash'] = MASTER_PASSWORD_HASH
        save_json_file(MASTER_CONFIG_FILE, MASTER_CONFIG)
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/master/change-port', methods=['POST'])
@master_required
def change_port():
    MASTER_CONFIG['port'] = request.json['port']
    save_json_file(MASTER_CONFIG_FILE, MASTER_CONFIG)
    threading.Thread(target=lambda: (time.sleep(1), os.execv(sys.executable, [sys.executable] + sys.argv))).start()
    return jsonify({'success': True})

@app.route('/api/master/restart', methods=['POST'])
@master_required
def restart_panel():
    threading.Thread(target=lambda: (time.sleep(1), os.execv(sys.executable, [sys.executable] + sys.argv))).start()
    return jsonify({'success': True})

if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     🔥 VeNoM - UNLIMITED VPS CONTROL PANEL 🔥                ║
║                                                              ║
║     Port: 3066                                               ║
║     Master: VeNoM / VeNoM                                    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    port = MASTER_CONFIG.get('port', 3066)
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)