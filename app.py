import os, time, json, random, socket, threading, asyncio
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# Import authentication functions
from JwtGen import (
    GeNeRaTeAccEss, EncRypTMajoRLoGin, MajorLogin, DecRypTMajoRLoGin,
    GetLoginData, DecRypTLoGinDaTa, xAuThSTarTuP
)

# ---------- Global data ----------
connected_clients = {}          # uid -> client object
connected_clients_lock = threading.Lock()
active_spam_targets = {}        # target uid -> timestamp/True
active_spam_lock = threading.Lock()

# ---------- User Auth System ----------
USER_DATA_FILE = "users.json"
ADMIN_USER = "zenon"
ADMIN_PASS = "apon"

def load_users():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(users, f, indent=4)

# ---------- Packet functions ----------
def EnC_Uid(H):
    e, H = [], int(H)
    while H:
        e.append((H & 0x7F) | (0x80 if H > 0x7F else 0))
        H >>= 7
    return bytes(e).hex()

def CrEaTe_ProTo(fields):
    def EnC_Vr(N):
        if N < 0:
            return b''
        H = []
        while True:
            b = N & 0x7F
            N >>= 7
            if N:
                b |= 0x80
            H.append(b)
            if not N:
                break
        return bytes(H)
    def CrEaTe_VarianT(field_number, value):
        field_header = (field_number << 3) | 0
        return EnC_Vr(field_header) + EnC_Vr(value)
    def CrEaTe_LenGTh(field_number, value):
        field_header = (field_number << 3) | 2
        encoded_value = value.encode() if isinstance(value, str) else value
        return EnC_Vr(field_header) + EnC_Vr(len(encoded_value)) + encoded_value
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(value, dict):
            nested = CrEaTe_ProTo(value)
            packet.extend(CrEaTe_LenGTh(field, nested))
        elif isinstance(value, int):
            packet.extend(CrEaTe_VarianT(field, value))
        elif isinstance(value, (str, bytes)):
            packet.extend(CrEaTe_LenGTh(field, value))
    return packet

def GeneRaTePk(Pk, N, K, V):
    def EnC_PacKeT(HeX, K, V):
        return AES.new(K, AES.MODE_CBC, V).encrypt(pad(bytes.fromhex(HeX), 16)).hex()
    def DecodE_HeX(H):
        return hex(H)[2:].zfill(2)
    PkEnc = EnC_PacKeT(Pk, K, V)
    _ = DecodE_HeX(len(PkEnc) // 2)
    if len(_) == 2:
        HeadEr = N + "000000"
    elif len(_) == 3:
        HeadEr = N + "00000"
    elif len(_) == 4:
        HeadEr = N + "0000"
    elif len(_) == 5:
        HeadEr = N + "000"
    else:
        HeadEr = N + "000000"
    return bytes.fromhex(HeadEr + _ + PkEnc)

def openroom(K, V):
    fields = {
        1: 2,
        2: {
            1: 1, 2: 15, 3: 5, 4: "[FFFF00]ᴢᴇɴᴏɴ➺ꫝᴘᴏɴ", 5: "1", 6: 12, 7: 1, 8: 1, 9: 1,
            11: 1, 12: 2, 14: 36981056,
            15: {1: "IDC3", 2: 126, 3: "ME"},
            16: "\u0001\u0003\u0004\u0007\t\n\u000b\u0012\u000f\u000e\u0016\u0019\u001a \u001d",
            18: 2368584, 27: 1, 34: "\u0000\u0001", 40: "en", 48: 1,
            49: {1: 21}, 50: {1: 36981056, 2: 2368584, 5: 2}
        }
    }
    return GeneRaTePk(CrEaTe_ProTo(fields).hex(), '0E15', K, V)

def spmroom(K, V, uid):
    fields = {1: 22, 2: {1: int(uid)}}
    return GeneRaTePk(CrEaTe_ProTo(fields).hex(), '0E15', K, V)

# ---------- Spam worker with reconnection ----------
def send_spam_from_all_accounts(target_id):
    with connected_clients_lock:
        clients = list(connected_clients.values())
    for client in clients:
        # Check if still active before sending
        with active_spam_lock:
            if target_id not in active_spam_targets:
                return

        if not client.online_sock or client._need_reconnect:
            client.reconnect()
            if not client.online_sock:
                continue
        try:
            client.online_sock.send(openroom(client.key, client.iv))
            time.sleep(1.5)
            for i in range(10):
                # Inner loop check for fast stop
                with active_spam_lock:
                    if target_id not in active_spam_targets:
                        return
                client.online_sock.send(spmroom(client.key, client.iv, target_id))
                time.sleep(0.2)
        except:
            client._need_reconnect = True

def spam_worker(target_id, duration_minutes):
    start_time = datetime.now()
    while True:
        with active_spam_lock:
            if target_id not in active_spam_targets:
                break
            if duration_minutes:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= duration_minutes * 60:
                    del active_spam_targets[target_id]
                    break
        try:
            send_spam_from_all_accounts(target_id)
            time.sleep(10) # reduced sleep for better responsiveness
        except:
            time.sleep(1)

# ---------- Account client with auto-reconnect ----------
class FF_CLient:
    def __init__(self, uid, password):
        self.uid = uid
        self.password = password
        self.key = None
        self.iv = None
        self.auth_token = None
        self.online_sock = None
        self.running = False
        self._need_reconnect = False
        self._connect()

    def _run_async(self, coro):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _full_auth(self):
        try:
            open_id, access_token = self._run_async(GeNeRaTeAccEss(self.uid, self.password))
            if not open_id or not access_token: return False
            payload = self._run_async(EncRypTMajoRLoGin(open_id, access_token))
            login_res = self._run_async(MajorLogin(payload))
            if not login_res: return False
            dec = self._run_async(DecRypTMajoRLoGin(login_res))
            self.key, self.iv, token, timestamp, account_uid = dec.key, dec.iv, dec.token, dec.timestamp, dec.account_uid
            login_data = self._run_async(GetLoginData(dec.url, payload, token))
            if not login_data: return False
            ports = self._run_async(DecRypTLoGinDaTa(login_data))
            online_ip, online_port = ports.Online_IP_Port.split(":")
            self.online_ip, self.online_port = online_ip, int(online_port)
            self.auth_token = self._run_async(xAuThSTarTuP(int(account_uid), token, int(timestamp), self.key, self.iv))
            return True
        except: return False

    def _connect_online(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.online_ip, self.online_port))
            sock.send(bytes.fromhex(self.auth_token))
            resp = sock.recv(4096)
            return sock if resp else None
        except: return None

    def _reader(self, sock):
        while self.running:
            try:
                data = sock.recv(4096)
                if not data: break
            except: break
        self.running, self._need_reconnect = False, True

    def _connect(self):
        if not self._full_auth(): return
        sock = self._connect_online()
        if not sock: return
        self.online_sock, self.running, self._need_reconnect = sock, True, False
        threading.Thread(target=self._reader, args=(sock,), daemon=True).start()
        with connected_clients_lock:
            connected_clients[self.uid] = self

    def reconnect(self):
        if self.online_sock:
            try: self.online_sock.close()
            except: pass
        self._connect()

# ---------- Load accounts ----------
def load_accounts():
    accounts = []
    try:
        if os.path.exists("Eren.txt"):
            with open("Eren.txt", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and ":" in line:
                        uid, pwd = line.split(":", 1)
                        accounts.append((uid, pwd))
    except: pass
    return accounts

def start_all_accounts():
    for uid, pwd in load_accounts():
        threading.Thread(target=lambda: FF_CLient(uid, pwd), daemon=True).start()
        time.sleep(2)

# ---------- Flask Web App ----------
app = Flask(__name__)
app.secret_key = "ᴢᴇɴᴏɴ➺ꫝᴘᴏɴ_secret_key_fixed"

LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - ᴢᴇɴᴏɴ➺ꫝᴘᴏɴ PANEL</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@600&display=swap" rel="stylesheet">
    <style>body { background: #06040a; color: white; font-family: 'Rajdhani', sans-serif; }</style>
</head>
<body class="flex items-center justify-center min-h-screen p-4">
    <div class="w-full max-w-md bg-[#0f0b20] p-8 rounded-2xl border border-purple-500/30 shadow-2xl">
        <h2 class="text-2xl font-bold text-center mb-6 text-purple-400">ᴢᴇɴᴏɴ➺ꫝᴘᴏɴ AUTH SYSTEM</h2>
        {% if error %}<p class="text-red-500 text-sm mb-4 text-center">{{ error }}</p>{% endif %}
        {% if msg %}<p class="text-green-500 text-sm mb-4 text-center">{{ msg }}</p>{% endif %}
        <form method="POST">
            <input type="text" name="username" placeholder="Username" class="w-full bg-black/50 border border-white/10 p-3 rounded-lg mb-4 outline-none focus:border-purple-500" required>
            <input type="password" name="password" placeholder="Password" class="w-full bg-black/50 border border-white/10 p-3 rounded-lg mb-6 outline-none focus:border-purple-500" required>
            <button name="action" value="login" class="w-full bg-purple-600 hover:bg-purple-700 p-3 rounded-lg font-bold transition mb-3">LOGIN</button>
            <button name="action" value="register" class="w-full border border-purple-600 p-3 rounded-lg font-bold hover:bg-purple-600/20 transition">REGISTER</button>
        </form>
    </div>
</body>
</html>
'''

ADMIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin - ᴢᴇɴᴏɴ➺ꫝᴘᴏɴ PANEL</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>body { background: #06040a; color: white; }</style>
</head>
<body class="p-6">
    <div class="max-w-4xl mx-auto">
        <div class="flex justify-between items-center mb-8">
            <h1 class="text-2xl font-bold text-purple-400">ADMIN CONTROL</h1>
            <a href="/" class="bg-gray-700 px-4 py-2 rounded">Back to Panel</a>
        </div>
        <div class="bg-[#0f0b20] rounded-xl overflow-hidden border border-white/10">
            <table class="w-full text-left">
                <thead class="bg-purple-900/50">
                    <tr>
                        <th class="p-4">Username</th>
                        <th class="p-4">Status</th>
                        <th class="p-4">Action</th>
                    </tr>
                </thead>
                <tbody>
                    {% for user, data in users.items() if user != "zenon" %}
                    <tr class="border-t border-white/5">
                        <td class="p-4">{{ user }}</td>
                        <td class="p-4">
                            {% if data.approved %}<span class="text-green-400">Approved</span>{% else %}<span class="text-yellow-400">Pending</span>{% endif %}
                        </td>
                        <td class="p-4 flex gap-2">
                            {% if not data.approved %}
                            <a href="/admin/approve/{{ user }}" class="bg-green-600 px-3 py-1 rounded text-sm">Approve</a>
                            {% endif %}
                            <a href="/admin/delete/{{ user }}" class="bg-red-600 px-3 py-1 rounded text-sm">Delete</a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
'''

# The original HTML template remains the same (Main Control Panel)
MAIN_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ᴢᴇɴᴏɴ➺ꫝᴘᴏɴ ULTRA TERMINAL</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600&family=Rajdhani:wght@600&family=Poppins&display=swap" rel="stylesheet">
    <style>
        * { font-family: 'Rajdhani', sans-serif; }
        body { background: radial-gradient(circle at top, #0f0c20 0%, #06040a 100%); color: white; }
        .cyber-panel { background: rgba(15, 11, 32, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); border-radius: 20px; padding: 20px; }
        .cyber-input { background: rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; color: white; padding: 12px; width: 100%; outline: none; }
        .btn-glow { background: linear-gradient(135deg, #00f0ff, #ff0080); border-radius: 10px; padding: 12px; font-weight: bold; width: 100%; }
        .vector-card { background: #0d091f; border: 1px solid #39ff1433; border-radius: 15px; padding: 15px; margin-bottom: 10px; }
    </style>
</head>
<body class="p-4 max-w-xl mx-auto">
    <header class="text-center my-6">
        <h1 class="text-3xl font-bold bg-gradient-to-r from-cyan-400 to-pink-500 text-transparent bg-clip-text">ᴢᴇɴᴏɴ➺ꫝᴘᴏɴ PANEL</h1>
        <div class="flex justify-center gap-4 mt-2">
            {% if is_admin %}
            <a href="/admin" class="text-xs text-yellow-400 border border-yellow-400/30 px-2 py-1 rounded">ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ</a>
            {% endif %}
            <a href="/logout" class="text-xs text-red-400 border border-red-400/30 px-2 py-1 rounded">Logout ({{ username }})</a>
        </div>
    </header>

    <div class="grid grid-cols-2 gap-4 mb-6 text-center">
        <div class="cyber-panel">
            <div class="text-2xl text-pink-500 font-bold" id="activeSpamCount">0</div>
            <div class="text-xs text-gray-400">ACTIVE SPAM</div>
        </div>
        <div class="cyber-panel">
            <div class="text-2xl text-cyan-400 font-bold" id="accCount">0</div>
            <div class="text-xs text-gray-400">BOTS ONLINE</div>
        </div>
    </div>

    <div class="cyber-panel mb-6">
        <h2 class="mb-4 text-cyan-400"><i class="fa-solid fa-bolt mr-2"></i>START OPERATION</h2>
        <input type="text" id="targetUid" class="cyber-input mb-4" placeholder="Enter Target UID">
        <button id="startBtn" class="btn-glow">START SPAM</button>
        <p id="startMsg" class="mt-2 text-xs text-center"></p>
    </div>

    <div class="cyber-panel">
        <h2 class="mb-4 text-pink-500"><i class="fa-solid fa-list mr-2"></i>ACTIVE PIPELINE</h2>
        <div id="activeTargets"></div>
    </div>

    <script>
        function fetchStatus() {
            fetch('/api/status').then(res => res.json()).then(data => {
                document.getElementById('accCount').innerText = data.connected_accounts;
                document.getElementById('activeSpamCount').innerText = data.active_spam.length;
                const targetsDiv = document.getElementById('activeTargets');
                targetsDiv.innerHTML = data.active_spam.map(uid => `
                    <div class="vector-card flex justify-between items-center">
                        <div>
                            <div class="text-sm">Target: <span class="text-cyan-400">${uid}</span></div>
                            <div class="text-[10px] text-gray-500">Status: Running...</div>
                        </div>
                        <button onclick="stopSpam('${uid}')" class="bg-red-600 text-xs px-3 py-1 rounded-full">STOP</button>
                    </div>
                `).join('') || '<p class="text-gray-500 text-center text-sm">No active tasks</p>';
            });
        }

        document.getElementById('startBtn').onclick = () => {
            const uid = document.getElementById('targetUid').value.trim();
            if(!uid) return;
            fetch('/start_spam?uid='+uid).then(res=>res.json()).then(data=>{
                document.getElementById('startMsg').innerText = data.status || data.error;
                fetchStatus();
            });
        };

        window.stopSpam = (uid) => {
            fetch('/stop_spam?uid='+uid).then(res=>res.json()).then(data=>{
                fetchStatus();
            });
        };

        setInterval(fetchStatus, 3000);
        fetchStatus();
    </script>
</body>
</html>
'''

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        action = request.form.get('action')
        users = load_users()

        if action == 'register':
            if user in users or user == ADMIN_USER:
                return render_template_string(LOGIN_HTML, error="Username already exists")
            users[user] = {"password": pw, "approved": False}
            save_users(users)
            return render_template_string(LOGIN_HTML, msg="Registration successful. Wait for Admin approval.")

        if user == ADMIN_USER and pw == ADMIN_PASS:
            session['username'] = ADMIN_USER
            return redirect(url_for('index'))
        
        if user in users and users[user]['password'] == pw:
            if users[user]['approved']:
                session['username'] = user
                return redirect(url_for('index'))
            else:
                return render_template_string(LOGIN_HTML, error="Your account is pending approval.")
        
        return render_template_string(LOGIN_HTML, error="Invalid credentials")
    
    return render_template_string(LOGIN_HTML)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template_string(MAIN_HTML, username=session['username'], is_admin=(session['username'] == ADMIN_USER))

# Admin Routes
@app.route('/admin')
def admin():
    if session.get('username') != ADMIN_USER:
        return redirect(url_for('index'))
    return render_template_string(ADMIN_HTML, users=load_users())

@app.route('/admin/approve/<username>')
def approve_user(username):
    if session.get('username') == ADMIN_USER:
        users = load_users()
        if username in users:
            users[username]['approved'] = True
            save_users(users)
    return redirect(url_for('admin'))

@app.route('/admin/delete/<username>')
def delete_user(username):
    if session.get('username') == ADMIN_USER:
        users = load_users()
        if username in users:
            del users[username]
            save_users(users)
    return redirect(url_for('admin'))

@app.route('/api/status')
def api_status():
    if 'username' not in session: return jsonify({}), 401
    with active_spam_lock:
        active = list(active_spam_targets.keys())
    return jsonify({
        'connected_accounts': len(connected_clients),
        'active_spam': active
    })

@app.route('/start_spam')
def start_spam_route():
    if 'username' not in session: return jsonify({}), 401
    target = request.args.get('uid')
    if not target or not connected_clients:
        return jsonify({'error': 'No bots or target'}), 400
    with active_spam_lock:
        if target not in active_spam_targets:
            active_spam_targets[target] = datetime.now().timestamp()
            threading.Thread(target=spam_worker, args=(target, None), daemon=True).start()
    return jsonify({'status': 'Spam started on '+target})

@app.route('/stop_spam')
def stop_spam_route():
    if 'username' not in session: return jsonify({}), 401
    target = request.args.get('uid')
    with active_spam_lock:
        if target in active_spam_targets:
            del active_spam_targets[target]
            return jsonify({'status': 'Stopped'})
    return jsonify({'error': 'Not found'}), 404

if __name__ == '__main__':
    threading.Thread(target=start_all_accounts, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)