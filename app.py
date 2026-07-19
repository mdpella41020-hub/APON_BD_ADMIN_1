# ============================================================
# COMBINED APP.PY - BD ADMIN PAID SPAM TOOLS
# app.py (Room Spam +  Request) + main.py (All Badge + Group Invite)
# একটি UID দিলে চারটা একসাথে কাজ করবে:
#   M1. All Badge Spam       Friend(account.txt)
#   M2. Group/Squad Invite   (account.txt + xC4)
#   M3. Room Spam            (room.txt)
#   M4. Friend Request Spam  (friend.txt)
# ============================================================

import os, time, json, random, socket, threading, asyncio, ssl
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from functools import wraps
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# ---- JwtGen (auth flow) ----
from JwtGen import (
    GeNeRaTeAccEss, EncRypTMajoRLoGin, MajorLogin, DecRypTMajoRLoGin,
    GetLoginData, DecRypTLoGinDaTa, xAuThSTarTuP
)

# ---- Friend Request ----
import requests
import urllib3
from byte import Encrypt_ID, encrypt_api
from xH import gJwt

# ---- xC4 (Squad Invite + xBunnEr) ----
try:
    from xC4 import OpEnSq, cHSq, SEnd_InV, ExiT, xBunnEr
    XC4_AVAILABLE = True
except ImportError:
    XC4_AVAILABLE = False
    print("[WARN] xC4 not found — Squad Invite disabled")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ============================================================
# CONFIG
# ============================================================
PROFILE_PIC  = "https://i.ibb.co.com/p6xCCh55/IMG-20260701-185837.jpg"
MUSIC_FILE   = "https://files.catbox.moe/ua29li.mp4"
ADMIN_USER   = "@apon"
ADMIN_PASS   = "1020"

BADGES = {
    "s1": (1048576,  "Craftland"),
    "s2": (32768,    "V-Badge"),
    "s3": (2048,     "Moderator"),
    "s4": (64,       "Small V-Badge"),
    "s5": (262144,   "Pro Badge"),
}

print("=" * 60)
print(f"[CONFIG] Profile Pic : {PROFILE_PIC}")
print(f"[CONFIG] Music File  : {MUSIC_FILE}")
print(f"[CONFIG] xC4 Module  : {'OK' if XC4_AVAILABLE else 'NOT FOUND'}")
print("=" * 60)

# ============================================================
# GLOBAL STATE
# ============================================================
connected_clients      = {}
connected_clients_lock = threading.Lock()

active_spam_targets    = {}
active_spam_lock       = threading.Lock()

friend_accounts        = []
friend_accounts_lock   = threading.Lock()
friend_jwt_tokens      = {}
friend_jwt_lock        = threading.Lock()

users_db               = {}
user_activities        = {}

# ============================================================
# USER MANAGEMENT
# ============================================================
def load_users():
    global users_db
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            users_db = json.load(f)
    except:
        users_db = {}

def save_users():
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(users_db, f, indent=2)

def require_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login_page'))
        username = session['user']
        if username not in users_db or not users_db[username].get('approved', False):
            return redirect(url_for('pending_page'))
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin' not in session:
            return redirect(url_for('admin_login_page'))
        return f(*args, **kwargs)
    return decorated

load_users()

# ============================================================
# ASYNC HELPER
# ============================================================
def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

# ============================================================
# ACCOUNT FILE LOADERS
# ============================================================
def load_badge_accounts():
    accounts = []
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "account.txt")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write("# Format: uid:password\n")
        return accounts
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                u, p = line.split(":", 1)
                accounts.append((u.strip(), p.strip()))
    return accounts

def load_room_accounts():
    accounts = []
    try:
        with open("room.txt", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and ":" in line and not line.startswith("#"):
                    uid, pwd = line.split(":", 1)
                    accounts.append((uid.strip(), pwd.strip()))
    except FileNotFoundError:
        print("[WARN] room.txt not found")
    return accounts

def Load_Friend_Accounts():
    accounts = []
    try:
        with open("friend.txt", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    parts = line.split(":", 1)
                    accounts.append((parts[0].strip(), parts[1].strip()))
    except FileNotFoundError:
        print("[WARN] friend.txt not found")
    return accounts

# ============================================================
# PACKET BUILDING
# ============================================================
def EnC_Uid(H):
    e, H = [], int(H)
    while H:
        e.append((H & 0x7F) | (0x80 if H > 0x7F else 0))
        H >>= 7
    return bytes(e).hex()

def CrEaTe_ProTo(fields):
    def EnC_Vr(N):
        if N < 0: return b''
        H = []
        while True:
            b = N & 0x7F
            N >>= 7
            if N: b |= 0x80
            H.append(b)
            if not N: break
        return bytes(H)
    def CrEaTe_VarianT(fn, v):
        return EnC_Vr((fn << 3) | 0) + EnC_Vr(v)
    def CrEaTe_LenGTh(fn, v):
        ev = v.encode() if isinstance(v, str) else v
        return EnC_Vr((fn << 3) | 2) + EnC_Vr(len(ev)) + ev
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(value, dict):
            nested = CrEaTe_ProTo(value)
            packet.extend(CrEaTe_LenGTh(field, bytes(nested)))
        elif isinstance(value, int):
            packet.extend(CrEaTe_VarianT(field, value))
        elif isinstance(value, (str, bytes)):
            packet.extend(CrEaTe_LenGTh(field, value))
    return bytes(packet)

def GeneRaTePk(Pk, N, K, V):
    def EnC_PacKeT(HeX, K, V):
        return AES.new(K, AES.MODE_CBC, V).encrypt(pad(bytes.fromhex(HeX), 16)).hex()
    def DecodE_HeX(H):
        return hex(H)[2:].zfill(2)
    PkEnc = EnC_PacKeT(Pk, K, V)
    _ = DecodE_HeX(len(PkEnc) // 2)
    if   len(_) == 2: HeadEr = N + "000000"
    elif len(_) == 3: HeadEr = N + "00000"
    elif len(_) == 4: HeadEr = N + "0000"
    elif len(_) == 5: HeadEr = N + "000"
    else:             HeadEr = N + "000000"
    return bytes.fromhex(HeadEr + _ + PkEnc)

def openroom(K, V):
    fields = {
        1: 2,
        2: {
            1: 1, 2: 15, 3: 5, 4: "[FFFF00]BD ADMIN", 5: "1", 6: 12, 7: 1, 8: 1, 9: 1,
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

def build_badge_packet(target_uid, badge_value, key, iv, region="BD"):
    try:
        avatar_id = int(_run_async(xBunnEr())) if XC4_AVAILABLE else random.randint(200000000, 299999999)
    except:
        avatar_id = random.randint(200000000, 299999999)
    fields = {
        1: 33,
        2: {
            1:  int(target_uid),
            2:  region.upper(),
            3:  1, 4: 1,
            5:  bytes([1, 7, 9, 10, 11, 18, 25, 26, 32]),
            6:  "TG:[C][B][FF0000] @BD_ADMIN_CODER",
            7:  330, 8: 1000, 10: region.upper(),
            11: bytes([49,97,99,52,98,56,48,101,99,102,48,52,55,56,97,52,
                       52,50,48,51,98,102,56,102,97,99,54,49,50,48,102,53]),
            12: 1, 13: int(target_uid),
            14: {1: 2203434355, 2: 8,
                 3: b"\x10\x15\x08\x0A\x0B\x13\x0C\x0F\x11\x04\x07\x02\x03\x0D\x0E\x12\x01\x05\x06"},
            16: 1, 17: 1, 18: 312, 19: 46,
            23: bytes([16, 1, 24, 1]),
            24: avatar_id, 26: {},
            27: {1: 11, 2: 12999994075, 3: 9999},
            28: {},
            31: {1: 1, 2: int(badge_value)},
            32: int(badge_value),
            34: {1: int(target_uid), 2: 8,
                 3: b"\x0F\x06\x15\x08\x0A\x0B\x13\x0C\x11\x04\x0E\x14\x07\x02\x01\x05\x10\x03\x0D\x12"}
        },
        10: "en",
        13: {2: 1, 3: 1}
    }
    return GeneRaTePk(CrEaTe_ProTo(fields).hex(), "0519", key, iv)

def build_squad_packets(target_uid, key, iv, region="BD"):
    if not XC4_AVAILABLE:
        return []
    try:
        return [
            _run_async(OpEnSq(key, iv, region)),
            _run_async(cHSq(5, int(target_uid), key, iv, region)),
            _run_async(SEnd_InV(5, int(target_uid), key, iv, region)),
            _run_async(ExiT(None, key, iv)),
        ]
    except Exception as e:
        print(f"[Squad] Packet error: {e}")
        return []

# ============================================================
# STATS HELPER
# ============================================================
def _inc_stat(target_uid, method, count=1):
    with active_spam_lock:
        if target_uid in active_spam_targets:
            s = active_spam_targets[target_uid]["stats"]
            s[method] = s.get(method, 0) + count
            s["total"] = s.get("total", 0) + count

def _add_log(target_uid, msg, level="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = {"ts": ts, "msg": msg, "level": level}
    with active_spam_lock:
        if target_uid in active_spam_targets:
            logs = active_spam_targets[target_uid].setdefault("logs", [])
            logs.append(entry)
            if len(logs) > 150:
                active_spam_targets[target_uid]["logs"] = logs[-150:]

# ============================================================
# AUTH + TCP
# ============================================================
def _authenticate_bot(bot_uid, bot_password):
    try:
        open_id, access_token = _run_async(GeNeRaTeAccEss(bot_uid, bot_password))
        if not open_id or not access_token:
            return None
        payload    = _run_async(EncRypTMajoRLoGin(open_id, access_token))
        login_res  = _run_async(MajorLogin(payload))
        if not login_res:
            return None
        dec         = _run_async(DecRypTMajoRLoGin(login_res))
        key         = dec.key
        iv          = dec.iv
        token       = dec.token
        timestamp   = dec.timestamp
        account_uid = dec.account_uid
        login_data  = _run_async(GetLoginData(dec.url, payload, token))
        if not login_data:
            return None
        ports = _run_async(DecRypTLoGinDaTa(login_data))
        online_ip, online_port = ports.Online_IP_Port.split(":")
        auth_token = _run_async(xAuThSTarTuP(
            int(account_uid), token, int(timestamp), key, iv
        ))
        return (key, iv, online_ip, int(online_port), auth_token)
    except Exception as e:
        print(f"[Auth] {bot_uid} failed: {e}")
        return None

def _connect_tcp(online_ip, online_port, auth_token):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(15)
        sock.connect((online_ip, online_port))
        sock.send(bytes.fromhex(auth_token))
        resp = sock.recv(4096)
        if not resp:
            sock.close()
            return None
        return sock
    except Exception as e:
        print(f"[TCP] Connect error: {e}")
        return None

# ============================================================
# METHOD 1 + 2: BADGE SPAM + SQUAD INVITE
# ============================================================
def badge_squad_worker(target_uid, badges_str, fast_mode):
    region  = "BD"
    delay_b = 0.2 if fast_mode else 0.6
    delay_s = 0.15

    badges_list = badges_str.split(",") if badges_str and badges_str != "all" else list(BADGES.keys())
    if "all" in badges_list:
        badges_list = list(BADGES.keys())

    _add_log(target_uid, f"🚀 [M1+M2] Badge+Squad started (Fast:{fast_mode})", "success")

    while active_spam_targets.get(target_uid, {}).get("running", False):
        accounts = load_badge_accounts()
        if not accounts:
            _add_log(target_uid, "❌ account.txt empty", "error")
            time.sleep(5)
            continue

        for bot_uid, bot_pass in accounts:
            if not active_spam_targets.get(target_uid, {}).get("running", False):
                break
            try:
                result = _authenticate_bot(bot_uid, bot_pass)
                if not result:
                    _add_log(target_uid, f"[-] Auth fail: {bot_uid}", "error")
                    continue

                key, iv, online_ip, online_port, auth_token = result
                sock = _connect_tcp(online_ip, online_port, auth_token)
                if not sock:
                    continue

                try:
                    # M1: All Badge Spam
                    for badge_key in badges_list:
                        if not active_spam_targets.get(target_uid, {}).get("running", False):
                            break
                        badge_val, badge_label = BADGES.get(badge_key, (None, badge_key))
                        if not badge_val:
                            continue
                        pkt = build_badge_packet(target_uid, badge_val, key, iv, region)
                        if pkt:
                            sock.send(pkt)
                            _inc_stat(target_uid, "badge")
                            _add_log(target_uid, f"   🏅 [{bot_uid}] Badge: {badge_label}", "success")
                        time.sleep(delay_b)

                    # M2: Squad/Group Invite
                    sq_pkts = build_squad_packets(target_uid, key, iv, region)
                    sent = 0
                    for pkt in sq_pkts:
                        if pkt:
                            sock.send(pkt)
                            sent += 1
                            time.sleep(delay_s)
                    if sent:
                        _inc_stat(target_uid, "squad", sent)
                        _add_log(target_uid, f"   👥 [{bot_uid}] Squad Invite sent ({sent} pkts)", "success")

                finally:
                    try:
                        sock.close()
                    except:
                        pass

            except Exception as e:
                _add_log(target_uid, f"[-] {bot_uid}: {e}", "error")

            time.sleep(0.5 if fast_mode else 1.0)

        time.sleep(1.0)

    _add_log(target_uid, "⏹️ [M1+M2] Badge+Squad stopped", "info")

# ============================================================
# METHOD 3: ROOM SPAM
# ============================================================
class FF_Client:
    def __init__(self, uid, password):
        self.uid             = uid
        self.password        = password
        self.key             = None
        self.iv              = None
        self.online_sock     = None
        self.running         = False
        self._need_reconnect = False
        threading.Thread(target=self._connect, daemon=True).start()

    def _connect(self):
        result = _authenticate_bot(self.uid, self.password)
        if not result:
            print(f"[-] {self.uid} auth failed")
            return
        key, iv, online_ip, online_port, auth_token = result
        self.key, self.iv = key, iv
        sock = _connect_tcp(online_ip, online_port, auth_token)
        if not sock:
            return
        self.online_sock     = sock
        self.running         = True
        self._need_reconnect = False
        with connected_clients_lock:
            connected_clients[self.uid] = self
            print(f"[+] Room client {self.uid} online. Total: {len(connected_clients)}")
        threading.Thread(target=self._reader, daemon=True).start()

    def reconnect(self):
        if self.online_sock:
            try:
                self.online_sock.close()
            except:
                pass
        self.running = False
        self._connect()

    def _reader(self):
        while self.running:
            try:
                data = self.online_sock.recv(4096)
                if not data:
                    break
            except:
                break
        self.running         = False
        self._need_reconnect = True


def room_spam_send(target_uid):
    with connected_clients_lock:
        clients = list(connected_clients.values())
    for client in clients:
        if not client.online_sock or client._need_reconnect:
            threading.Thread(target=client.reconnect, daemon=True).start()
            continue
        try:
            client.online_sock.send(openroom(client.key, client.iv))
            time.sleep(1.0)
            for _ in range(10):
                client.online_sock.send(spmroom(client.key, client.iv, target_uid))
                time.sleep(0.2)
            _inc_stat(target_uid, "room", 11)
            _add_log(target_uid, f"   🏠 [{client.uid}] Room spam sent", "success")
        except Exception as e:
            _add_log(target_uid, f"   [Room] {client.uid}: {e}", "error")
            client._need_reconnect = True


def room_spam_worker(target_uid):
    _add_log(target_uid, "🏠 [M3] Room Spam started", "success")
    while active_spam_targets.get(target_uid, {}).get("running", False):
        room_spam_send(target_uid)
        time.sleep(3.0)
    _add_log(target_uid, "⏹️ [M3] Room Spam stopped", "info")

# ============================================================
# METHOD 4: FRIEND REQUEST SPAM
# ============================================================
FRIEND_HEADERS = {
    "X-Unity-Version": "2018.4.11f1",
    "X-GA": "v1 1",
    "ReleaseVersion": "OB54",
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Dalvik/2.1.0"
}

def _send_friend_request(target_uid, token):
    try:
        enc_target  = Encrypt_ID(str(target_uid))
        payload     = f"08a7c4839f1e10{enc_target}1801"
        enc_payload = encrypt_api(payload)
        headers     = {**FRIEND_HEADERS, "Authorization": f"Bearer {token}"}
        response    = requests.post(
            "https://clientbp.ggpolarbear.com/RequestAddingFriend",
            headers=headers,
            data=bytes.fromhex(enc_payload),
            verify=False,
            timeout=10
        )
        return response
    except:
        return None


def _update_friend_jwt():
    while True:
        with friend_accounts_lock:
            accounts = friend_accounts.copy()
        for uid, pwd in accounts:
            try:
                token = gJwt(uid, pwd)
                if token:
                    with friend_jwt_lock:
                        friend_jwt_tokens[uid] = token
            except:
                pass
        time.sleep(1)


def friend_request_worker(target_uid):
    _add_log(target_uid, "👤 [M4] Friend Request Spam started", "success")
    success = 0
    failed  = 0
    while active_spam_targets.get(target_uid, {}).get("running", False):
        with friend_accounts_lock:
            accounts = friend_accounts.copy()
        for uid, _ in accounts:
            if not active_spam_targets.get(target_uid, {}).get("running", False):
                break
            with friend_jwt_lock:
                token = friend_jwt_tokens.get(uid)
            if not token:
                failed += 1
                continue
            resp = _send_friend_request(target_uid, token)
            if resp and resp.status_code == 200:
                success += 1
                _inc_stat(target_uid, "friend")
                _add_log(target_uid, f"   👤 [{uid}] Friend req sent ✅", "success")
            else:
                failed += 1
            time.sleep(0.15)
        time.sleep(0.5)
    _add_log(target_uid, f"⏹️ [M4] Friend Spam stopped | ✅{success} ❌{failed}", "info")

# ============================================================
# COMBINED SPAM MASTER
# ============================================================
def start_combined_spam(target_uid, username, badges_str="all", fast_mode=False):
    with active_spam_lock:
        if target_uid in active_spam_targets and active_spam_targets[target_uid].get("running"):
            return False, "Already running for this UID"
        active_spam_targets[target_uid] = {
            "running":    True,
            "username":   username,
            "start_time": time.time(),
            "fast_mode":  fast_mode,
            "badges":     badges_str,
            "stats": {"badge": 0, "squad": 0, "room": 0, "friend": 0, "total": 0},
            "logs": [],
        }

    if username not in user_activities:
        user_activities[username] = {"targets": [], "start_times": {}}
    if target_uid not in user_activities[username]["targets"]:
        user_activities[username]["targets"].append(target_uid)
    user_activities[username]["start_times"][target_uid] = time.time()

    threading.Thread(target=badge_squad_worker, args=(target_uid, badges_str, fast_mode), daemon=True).start()
    threading.Thread(target=room_spam_worker,   args=(target_uid,), daemon=True).start()
    threading.Thread(target=friend_request_worker, args=(target_uid,), daemon=True).start()

    return True, f"All 4 methods started for UID {target_uid}"


def stop_combined_spam(target_uid):
    with active_spam_lock:
        if target_uid in active_spam_targets:
            active_spam_targets[target_uid]["running"] = False
            username = active_spam_targets[target_uid].get("username")
            if username and username in user_activities:
                try:
                    user_activities[username]["targets"].remove(target_uid)
                except ValueError:
                    pass
            return True
    return False

# ============================================================
# ROOM CLIENTS STARTUP
# ============================================================
def start_room_clients():
    for uid, pwd in load_room_accounts():
        time.sleep(3)
        FF_Client(uid, pwd)

# ============================================================
# FLASK ROUTES — USER
# ============================================================
@app.route('/')
def login_page():
    return render_template_string(LOGIN_HTML)

@app.route('/pending')
def pending_page():
    return render_template_string(PENDING_HTML)

@app.route('/dashboard')
@require_login
def dashboard_page():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/login', methods=['POST'])
def api_login():
    data     = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if username in users_db and users_db[username].get('password') == password:
        if not users_db[username].get('approved', False):
            return jsonify({'success': False, 'pending': True, 'message': 'Account pending approval'})
        session['user'] = username
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Invalid username or password'})

@app.route('/api/register', methods=['POST'])
def api_register():
    data     = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if not username or not password:
        return jsonify({'success': False, 'message': 'All fields required'})
    if username in users_db:
        return jsonify({'success': False, 'message': 'Username already exists'})
    users_db[username] = {
        'password': password,
        'approved': False,
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M')
    }
    save_users()
    return jsonify({'success': True, 'message': 'Registered! Waiting for admin approval.'})

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.pop('user', None)
    return jsonify({'success': True})

@app.route('/api/spam/start', methods=['POST'])
@require_login
def api_spam_start():
    data       = request.get_json()
    target_uid = str(data.get('target_uid', '')).strip()
    badges_str = data.get('badges', 'all')
    fast_mode  = data.get('fast_mode', False)
    username   = session['user']

    if not target_uid or not target_uid.isdigit():
        return jsonify({'success': False, 'message': 'Invalid UID'})

    ok, msg = start_combined_spam(target_uid, username, badges_str, fast_mode)
    return jsonify({'success': ok, 'message': msg})

@app.route('/api/spam/stop', methods=['POST'])
@require_login
def api_spam_stop():
    data       = request.get_json()
    target_uid = str(data.get('target_uid', '')).strip()
    username   = session['user']
    # ── ownership check ──
    with active_spam_lock:
        info = active_spam_targets.get(target_uid, {})
        if info and info.get("username") != username:
            return jsonify({'success': False, 'message': 'Not your target'})
    ok = stop_combined_spam(target_uid)
    return jsonify({'success': ok, 'message': 'Stopped' if ok else 'Not running'})

@app.route('/api/status')
@require_login
def api_status():
    username = session['user']
    with active_spam_lock:
        targets = []
        for uid, info in active_spam_targets.items():
            if not info.get("running"):
                continue
            # ── প্রতিটি ইউজার শুধু নিজের target দেখবে ──
            if info.get("username") != username:
                continue
            elapsed = time.time() - info.get("start_time", time.time())
            targets.append({
                "uid":        uid,
                "stats":      info.get("stats", {}),
                "elapsed":    round(elapsed, 1),
                "start_time": info.get("start_time", time.time()),
                "logs":       info.get("logs", [])[-20:],
                "username":   info.get("username"),
            })

    with connected_clients_lock:
        room_connected = list(connected_clients.keys())

    with friend_accounts_lock:
        fa_list = [u for u, _ in friend_accounts]

    badge_accs  = load_badge_accounts()
    room_total  = load_room_accounts()

    return jsonify({
        "active_targets":   targets,
        "room_connected":   len(room_connected),
        "room_total":       len(room_total),
        "room_client_uids": room_connected,
        "friend_connected": len(fa_list),
        "friend_total":     len(Load_Friend_Accounts()),
        "badge_connected":  len(badge_accs),
        "badge_total":      len(badge_accs),
        "xc4_available":    XC4_AVAILABLE,
        "username":         username,
    })

@app.route('/api/player_info/<uid>')
@require_login
def api_player_info(uid):
    """Free Fire player info proxy"""
    try:
        r = requests.get(
            f"https://player-info-by-ckrpro.vercel.app/get?uid={uid}",
            timeout=10
        )
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/wishlist/<uid>')
@require_login
def api_wishlist(uid):
    """Wishlist proxy"""
    region = request.args.get("region", "BD")
    try:
        r = requests.get(
            f"https://player-info-by-ckrpro.vercel.app/wishlist?uid={uid}&region={region}",
            timeout=10
        )
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e), "wishlist": []}), 500

# ============================================================
# FLASK ROUTES — ADMIN
# ============================================================
@app.route('/admin')
def admin_login_page():
    return render_template_string(ADMIN_LOGIN_HTML)

@app.route('/api/admin/login', methods=['POST'])
def api_admin_login():
    data = request.get_json()
    if data.get('username') == ADMIN_USER and data.get('password') == ADMIN_PASS:
        session['admin'] = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Invalid admin credentials'})

@app.route('/admin/dashboard')
@require_admin
def admin_dashboard():
    with active_spam_lock:
        active_spam = [uid for uid, info in active_spam_targets.items() if info.get("running")]
    return render_template_string(ADMIN_DASH_HTML,
        users=users_db,
        activities=user_activities,
        active_spam=active_spam
    )

@app.route('/api/admin/approve', methods=['POST'])
@require_admin
def api_admin_approve():
    username = request.get_json().get('username', '').strip()
    if username in users_db:
        users_db[username]['approved'] = True
        save_users()
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'User not found'})

@app.route('/api/admin/reject', methods=['POST'])
@require_admin
def api_admin_reject():
    username = request.get_json().get('username', '').strip()
    if username in users_db:
        users_db[username]['approved'] = False
        save_users()
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'User not found'})

@app.route('/api/admin/delete', methods=['POST'])
@require_admin
def api_admin_delete():
    username = request.get_json().get('username', '').strip()
    if username in users_db:
        users_db.pop(username)
        save_users()
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'User not found'})

@app.route('/api/admin/change_password', methods=['POST'])
@require_admin
def api_admin_change_password():
    data     = request.get_json()
    username = data.get('username', '').strip()
    new_pass = data.get('new_password', '').strip()
    if username in users_db:
        users_db[username]['password'] = new_pass
        save_users()
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'User not found'})

@app.route('/api/admin/stop_all', methods=['POST'])
@require_admin
def api_admin_stop_all():
    username = request.get_json().get('username', '').strip()
    stopped  = 0
    with active_spam_lock:
        for uid, info in active_spam_targets.items():
            if info.get("username") == username and info.get("running"):
                info["running"] = False
                stopped += 1
    if username in user_activities:
        user_activities[username] = {"targets": [], "start_times": {}}
    return jsonify({'success': True, 'stopped': stopped})

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login_page'))

# ============================================================
# HTML TEMPLATES
# ============================================================

SHARED_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600;800;900&family=Rajdhani:wght@500;600;700&family=Poppins:wght@400;500;600;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
:root{--a:#00d4ff;--b:#0066cc;--g:#00ff88;--r:#ff2255;--o:#ffa500;--p:#c47aff;--bg:#000d1a}
body{background:linear-gradient(135deg,#001a33 0%,#000d1a 60%,#001020 100%);min-height:100vh;color:#fff;font-family:'Rajdhani',sans-serif;overflow-x:hidden}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(circle at 15% 85%,rgba(0,212,255,.07) 0%,transparent 45%),radial-gradient(circle at 85% 15%,rgba(0,102,204,.07) 0%,transparent 45%);pointer-events:none;z-index:0}
.glass{background:rgba(0,16,32,.78);backdrop-filter:blur(22px);border:1px solid rgba(0,212,255,.18);border-radius:18px}
.glow{box-shadow:0 0 28px rgba(0,212,255,.22)}
.btn-ocean{background:linear-gradient(135deg,var(--a),var(--b));color:#000;font-weight:800;border:none;border-radius:12px;cursor:pointer;font-family:'Orbitron',sans-serif;letter-spacing:1.5px;transition:all .3s;padding:11px 22px;font-size:.82rem}
.btn-ocean:hover{transform:translateY(-2px);box-shadow:0 6px 24px rgba(0,212,255,.45)}
.btn-red{background:linear-gradient(135deg,#ff2255,#cc0044);color:#fff;font-weight:700;border:none;border-radius:10px;cursor:pointer;padding:7px 14px;transition:all .3s;font-size:.78rem}
.btn-green{background:linear-gradient(135deg,var(--g),#00cc66);color:#000;font-weight:700;border:none;border-radius:10px;cursor:pointer;padding:7px 14px;transition:all .3s;font-size:.78rem}
.inp{background:rgba(0,8,20,.85);border:1px solid rgba(0,212,255,.22);border-radius:12px;color:#fff;padding:12px 16px;width:100%;outline:none;font-family:'Poppins',sans-serif;font-size:.93rem;transition:.3s}
.inp:focus{border-color:var(--a);box-shadow:0 0 14px rgba(0,212,255,.18)}
.inp::placeholder{color:rgba(0,212,255,.3)}
.toast{position:fixed;bottom:22px;right:22px;z-index:9999;background:rgba(0,16,32,.97);border:1px solid rgba(0,212,255,.4);border-radius:14px;padding:13px 20px;font-family:'Poppins',sans-serif;font-size:.88rem;min-width:230px;opacity:0;transform:translateY(8px);transition:all .35s;pointer-events:none}
.toast.show{opacity:1;transform:translateY(0)}
.avatar-ring{width:82px;height:82px;border-radius:50%;padding:3px;background:linear-gradient(135deg,var(--a),var(--b),#00f0ff);box-shadow:0 0 22px rgba(0,212,255,.4)}
.avatar-ring img{width:100%;height:100%;border-radius:50%;object-fit:cover;border:3px solid #001a33}
.particle{position:absolute;border-radius:50%;animation:floatUp linear infinite}
@keyframes floatUp{0%{transform:translateY(100vh);opacity:0}10%{opacity:.8}90%{opacity:.8}100%{transform:translateY(-8vh);opacity:0}}
.music-btn{position:fixed;top:13px;right:13px;z-index:200;background:rgba(0,16,32,.9);border:1px solid rgba(0,212,255,.3);border-radius:22px;padding:6px 14px;cursor:pointer;display:flex;align-items:center;gap:5px;font-family:'Orbitron',sans-serif;font-size:.7rem;color:var(--a);transition:all .3s;letter-spacing:1px}
.music-btn:hover{border-color:var(--a);box-shadow:0 0 12px rgba(0,212,255,.28)}
/* Equal stat boxes */
.stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:22px}
@media(max-width:700px){.stat-grid{grid-template-columns:repeat(2,1fr)}}
.stat-box{background:rgba(0,8,22,.75);border-radius:14px;padding:18px 12px;text-align:center;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;min-height:110px;position:relative;overflow:hidden}
.stat-box::before{content:'';position:absolute;inset:0;border-radius:14px;border:1px solid transparent;transition:border-color .3s}
.stat-box.c-blue::before{border-color:rgba(0,212,255,.25)}
.stat-box.c-green::before{border-color:rgba(0,255,136,.25)}
.stat-box.c-orange::before{border-color:rgba(255,165,0,.25)}
.stat-box.c-purple::before{border-color:rgba(196,122,255,.25)}
.stat-label{font-size:.72rem;color:rgba(255,255,255,.45);font-family:'Orbitron',sans-serif;letter-spacing:1.2px;text-transform:uppercase}
.stat-count{font-family:'Orbitron',sans-serif;font-size:1.9rem;font-weight:900;line-height:1}
.stat-sub{font-size:.68rem;color:rgba(255,255,255,.3);font-family:'Poppins',sans-serif}
.stat-dot{width:7px;height:7px;border-radius:50%;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
/* Method badge chips */
.mbadge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.72rem;font-weight:700;letter-spacing:.8px}
.mb1{background:rgba(255,165,0,.15);border:1px solid rgba(255,165,0,.45);color:var(--o)}
.mb2{background:rgba(196,122,255,.15);border:1px solid rgba(196,122,255,.45);color:var(--p)}
.mb3{background:rgba(0,255,136,.15);border:1px solid rgba(0,255,136,.45);color:var(--g)}
.mb4{background:rgba(0,212,255,.15);border:1px solid rgba(0,212,255,.45);color:var(--a)}
/* Badge chips */
.badge-chip{padding:5px 11px;border-radius:18px;cursor:pointer;font-size:.8rem;font-weight:700;letter-spacing:.8px;transition:.25s;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.12);color:rgba(255,255,255,.5)}
.badge-chip.on{background:rgba(0,212,255,.18);border-color:var(--a);color:var(--a);box-shadow:0 0 9px rgba(0,212,255,.22)}
/* Log */
.log-line{padding:2px 0;font-family:'Courier New',monospace;font-size:.76rem;border-bottom:1px solid rgba(255,255,255,.03)}
.log-s{color:#00ff88}.log-e{color:#ff4466}.log-i{color:var(--a)}
/* Target card */
.target-card{background:rgba(0,8,22,.88);border:2px solid rgba(0,212,255,.28);border-radius:15px;padding:15px;position:relative;transition:border-color .3s}
.target-card:hover{border-color:rgba(0,212,255,.55)}
.target-banner{width:100%;border-radius:9px;border:1px solid rgba(0,212,255,.18);min-height:76px;object-fit:cover;background:#000914}
/* Method stats row - 4 equal boxes */
.mstats{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:10px}
.mstat-box{background:rgba(0,0,0,.35);border-radius:9px;padding:8px 5px;text-align:center}
.mstat-num{font-family:'Orbitron',sans-serif;font-size:1.1rem;font-weight:900;line-height:1.1}
.mstat-lbl{font-size:.62rem;margin-top:2px}
/* Player profile card */
.view-more-btn{background:linear-gradient(135deg,var(--g),#00cc66);color:#000;font-weight:800;border:none;border-radius:22px;cursor:pointer;padding:7px 18px;font-size:.76rem;font-family:'Orbitron',sans-serif;letter-spacing:1px;display:flex;align-items:center;gap:5px;transition:all .3s}
.view-more-btn:hover{transform:translateY(-1px);box-shadow:0 4px 16px rgba(0,255,136,.4)}
.view-less-btn{background:linear-gradient(135deg,#00c8ff,#0066cc);color:#000;font-weight:800;border:none;border-radius:22px;cursor:pointer;padding:7px 18px;font-size:.76rem;font-family:'Orbitron',sans-serif;letter-spacing:1px;display:flex;align-items:center;gap:5px;transition:all .3s}
.profile-panel{display:none;margin-top:12px;animation:fadeSlide .3s ease}
@keyframes fadeSlide{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:translateY(0)}}
.glass-card-inner{background:rgba(0,6,18,.9);border:1px solid rgba(0,212,255,.14);border-radius:14px;padding:14px;margin-bottom:9px}
.banner-wrap{position:relative;width:100%;height:100px;border-radius:10px;overflow:hidden;background:#000914;margin-bottom:-40px}
.banner-wrap img{width:100%;height:100%;object-fit:cover;opacity:.7}
.p-avatar-wrap{position:relative;z-index:2;width:72px;height:72px;border-radius:14px;border:3px solid rgba(0,212,255,.5);overflow:hidden;background:#001020;margin:0 auto;display:block}
.p-avatar-wrap img{width:100%;height:100%;object-fit:contain}
.p-info-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:9px}
.p-info-box{background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.06);border-radius:10px;padding:9px;text-align:center}
.p-info-label{font-size:.65rem;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:1px;font-family:'Orbitron',sans-serif}
.p-info-val{font-family:'Orbitron',sans-serif;font-size:.95rem;font-weight:900;margin-top:2px}
.info-row{display:flex;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,.05);padding:5px 0;font-size:.78rem}
.info-row:last-child{border-bottom:none}
.info-key{color:rgba(255,255,255,.4)}
.info-val{color:rgba(255,255,255,.85);font-weight:600}
.section-hdr{font-family:'Orbitron',sans-serif;font-size:.72rem;letter-spacing:2px;text-transform:uppercase;display:flex;align-items:center;gap:7px;margin-bottom:9px;font-weight:700}
.companion-box{display:flex;align-items:center;gap:11px;background:rgba(0,0,0,.4);border:1px solid rgba(0,255,136,.12);border-radius:12px;padding:10px}
.comp-img{width:52px;height:52px;border-radius:10px;background:#000;border:1px solid rgba(0,255,136,.15);overflow:hidden}
.comp-img img{width:100%;height:100%;object-fit:contain}
</style>"""

MUSIC_JS = f"""
<audio id="bgm" loop><source src="{MUSIC_FILE}" type="audio/mp4"></audio>
<script>
const bgm=document.getElementById('bgm');bgm.volume=0.35;
let muted=false;
document.addEventListener('click',()=>{{if(!muted)bgm.play().catch(()=>{{}});}},{{once:true}});
function toggleMusic(){{muted=!muted;if(muted){{bgm.pause();document.getElementById('mBtn').style.borderColor='rgba(255,0,85,.4)';document.getElementById('mLabel').textContent='OFF'}}else{{bgm.play();document.getElementById('mBtn').style.borderColor='rgba(0,212,255,.3)';document.getElementById('mLabel').textContent='ON'}}}}
</script>"""

# ─────────────────────────── LOGIN PAGE ───────────────────────────
LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>BD ADMIN — PAID SPAM TOOLS</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
""" + SHARED_CSS + """
<style>
.wrap{position:relative;z-index:1;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px}
.particles{position:fixed;inset:0;pointer-events:none;z-index:0;overflow:hidden}
.link-row{display:flex;gap:10px;margin-bottom:26px}
.link-btn{background:rgba(0,212,255,.07);border:1px solid rgba(0,212,255,.28);color:var(--a);font-size:.76rem;font-weight:700;letter-spacing:1.5px;padding:8px 16px;border-radius:22px;text-decoration:none;display:flex;align-items:center;gap:6px;font-family:'Orbitron',sans-serif;transition:.3s}
.link-btn:hover{background:linear-gradient(135deg,var(--a),var(--b));color:#000}
.tabs{display:flex;border-radius:11px;overflow:hidden;border:1px solid rgba(0,212,255,.18);margin-bottom:20px}
.tab{flex:1;padding:10px;text-align:center;cursor:pointer;font-family:'Orbitron',sans-serif;font-size:.78rem;letter-spacing:1px;transition:.3s;color:rgba(255,255,255,.45)}
.tab.active{background:linear-gradient(135deg,var(--a),var(--b));color:#000}
</style>
</head>
<body>
<div class="particles" id="particles"></div>
""" + MUSIC_JS + """
<div class="music-btn" id="mBtn" onclick="toggleMusic()">
  <i class="fa-solid fa-volume-high" style="font-size:10px"></i>
  <span id="mLabel">ON</span>
</div>
<div class="wrap">
  <h1 style="font-family:'Orbitron',sans-serif;font-size:2.1rem;font-weight:900;letter-spacing:5px;text-shadow:0 0 22px rgba(0,212,255,.6);margin-bottom:5px">BD ADMIN</h1>
  <p style="font-family:'Orbitron',sans-serif;font-size:.8rem;color:rgba(0,212,255,.65);letter-spacing:6px;margin-bottom:22px">PAID SPAM TOOLS</p>

  <div class="link-row">
    <a href="https://t.me/BD_ADMIN_CODER_OFFICIAL" target="_blank" class="link-btn"><i class="fa-brands fa-telegram"></i> CHANNEL</a>
    <a href="https://t.me/BD_ADMIN_20" target="_blank" class="link-btn"><i class="fa-solid fa-phone"></i> OWNER</a>
  </div>

  <div class="glass glow" style="width:100%;max-width:400px;padding:30px">
    <div style="display:flex;justify-content:center;margin-bottom:20px">
      <div class="avatar-ring"><img src='""" + PROFILE_PIC + """' onerror="this.src='https://via.placeholder.com/80/001a33/00d4ff?text=BD'" alt="BD"></div>
    </div>
    <div class="tabs">
      <div class="tab active" id="tabLogin" onclick="switchTab('login')">LOGIN</div>
      <div class="tab" id="tabReg" onclick="switchTab('reg')">REGISTER</div>
    </div>
    <div id="loginForm">
      <div style="margin-bottom:13px"><input class="inp" id="lUser" placeholder="Username" autocomplete="off"></div>
      <div style="margin-bottom:18px"><input class="inp" id="lPass" placeholder="Password" type="password"></div>
      <button class="btn-ocean" style="width:100%;padding:13px" onclick="doLogin()"><i class="fa-solid fa-arrow-right-to-bracket"></i> LOGIN</button>
    </div>
    <div id="regForm" style="display:none">
      <div style="margin-bottom:13px"><input class="inp" id="rUser" placeholder="Username" autocomplete="off"></div>
      <div style="margin-bottom:18px"><input class="inp" id="rPass" placeholder="Password" type="password"></div>
      <button class="btn-ocean" style="width:100%;padding:13px" onclick="doRegister()"><i class="fa-solid fa-user-plus"></i> REGISTER</button>
    </div>
  </div>

  <a href="/admin" style="color:rgba(0,212,255,.35);font-size:.7rem;font-family:'Orbitron',sans-serif;letter-spacing:2px;text-decoration:none;margin-top:16px;transition:.3s" onmouseover="this.style.color='#00d4ff'" onmouseout="this.style.color='rgba(0,212,255,.35)'">
    <i class="fa-solid fa-shield-halved"></i> ADMIN PANEL
  </a>
</div>
<div class="toast" id="toast"></div>
<script>
const pc=document.getElementById('particles');
for(let i=0;i<22;i++){const p=document.createElement('div');p.className='particle';const s=Math.random()*3+1;p.style.cssText=`left:${Math.random()*100}%;width:${s}px;height:${s}px;background:rgba(0,212,255,${Math.random()*.35+.1});animation-duration:${Math.random()*8+5}s;animation-delay:${Math.random()*6}s`;pc.appendChild(p)}
function switchTab(t){
  document.getElementById('loginForm').style.display=t==='login'?'':'none';
  document.getElementById('regForm').style.display=t==='reg'?'':'none';
  document.getElementById('tabLogin').className='tab'+(t==='login'?' active':'');
  document.getElementById('tabReg').className='tab'+(t==='reg'?' active':'');
}
function toast(msg,err=false){const el=document.getElementById('toast');el.textContent=msg;el.style.borderColor=err?'rgba(255,0,85,.5)':'rgba(0,212,255,.5)';el.style.color=err?'#ff6080':'#00d4ff';el.classList.add('show');setTimeout(()=>el.classList.remove('show'),3500)}
async function doLogin(){
  const u=document.getElementById('lUser').value.trim(),p=document.getElementById('lPass').value.trim();
  if(!u||!p)return toast('Enter credentials',true);
  const d=await(await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})})).json();
  if(d.success)window.location='/dashboard';
  else if(d.pending)toast('⏳ Account pending admin approval');
  else toast(d.message||'Login failed',true);
}
async function doRegister(){
  const u=document.getElementById('rUser').value.trim(),p=document.getElementById('rPass').value.trim();
  if(!u||!p)return toast('Fill all fields',true);
  const d=await(await fetch('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})})).json();
  if(d.success){toast('✅ Registered! Waiting for approval...');setTimeout(()=>switchTab('login'),1600)}
  else toast(d.message,true);
}
document.addEventListener('keydown',e=>{if(e.key==='Enter'){if(document.getElementById('loginForm').style.display!=='none')doLogin();else doRegister()}});
</script>
</body></html>"""

# ─────────────────────── PENDING PAGE ───────────────────────
PENDING_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Pending</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
""" + SHARED_CSS + """
</head><body>
<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px">
  <div class="glass glow" style="max-width:400px;width:100%;padding:42px;text-align:center">
    <i class="fa-solid fa-clock" style="font-size:3rem;color:var(--a);margin-bottom:18px;display:block;animation:pulse 2s infinite"></i>
    <h2 style="font-family:'Orbitron',sans-serif;color:var(--a);margin-bottom:12px;letter-spacing:2px">PENDING APPROVAL</h2>
    <p style="color:rgba(255,255,255,.55);margin-bottom:24px;line-height:1.65;font-size:.9rem">Your account is waiting for admin approval.<br>Contact the owner on Telegram.</p>
    <a href="https://t.me/BD_ADMIN_20" target="_blank" style="display:inline-block;background:linear-gradient(135deg,var(--a),var(--b));color:#000;padding:10px 26px;border-radius:12px;font-family:'Orbitron',sans-serif;font-weight:700;text-decoration:none;font-size:.82rem;letter-spacing:1px">
      <i class="fa-brands fa-telegram"></i> CONTACT OWNER
    </a>
    <br><br>
    <a href="/" style="color:rgba(0,212,255,.4);font-size:.78rem;font-family:'Orbitron',sans-serif;text-decoration:none">← Back to Login</a>
  </div>
</div>
</body></html>"""

# ─────────────────────── DASHBOARD ───────────────────────
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>BD ADMIN — Dashboard</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
""" + SHARED_CSS + """
<style>
.container{position:relative;z-index:1;max-width:1180px;margin:0 auto;padding:18px}
.header{text-align:center;padding:26px 0 18px}
.header h1{font-family:'Orbitron',sans-serif;font-size:1.75rem;font-weight:900;letter-spacing:4px;text-shadow:0 0 18px rgba(0,212,255,.5)}
.section-title{font-family:'Orbitron',sans-serif;font-size:.9rem;letter-spacing:2px;margin-bottom:14px;display:flex;align-items:center;gap:8px}
</style>
</head>
<body>
""" + MUSIC_JS + """
<div class="music-btn" id="mBtn" onclick="toggleMusic()">
  <i class="fa-solid fa-volume-high" style="font-size:10px"></i><span id="mLabel">ON</span>
</div>
<div class="container">

  <!-- ── HEADER ── -->
  <div class="header">
    <h1>⚡ BD ADMIN <span style="color:var(--a)">COMBINED SPAM</span></h1>
    <p style="font-family:'Orbitron',sans-serif;font-size:.72rem;color:rgba(0,212,255,.55);letter-spacing:5px;margin-top:4px">ALL 4 METHODS — ONE UID</p>
    <div style="display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap;margin-top:13px">
      <span class="mbadge mb1">M1 Badge</span>
      <span class="mbadge mb2">M2 Squad</span>
      <span class="mbadge mb3">M3 Room</span>
      <span class="mbadge mb4">M4 Friend</span>
      <span id="userLabel" style="color:rgba(0,212,255,.55);font-size:.8rem;font-family:'Orbitron',sans-serif"></span>
      <button onclick="doLogout()" style="background:none;border:1px solid rgba(255,0,85,.3);color:#ff4466;border-radius:8px;padding:4px 13px;cursor:pointer;font-size:.76rem;font-family:'Orbitron',sans-serif">LOGOUT</button>
    </div>
  </div>

  <!-- ── ACCOUNT STATUS (4 equal boxes) ── -->
  <div class="stat-grid">
    <!-- Active Targets -->
    <div class="stat-box c-blue">
      <div style="display:flex;align-items:center;gap:6px">
        <span class="stat-dot" style="background:#00d4ff"></span>
        <span class="stat-label">Active Targets</span>
      </div>
      <div class="stat-count" id="sTargets" style="color:var(--a)">0</div>
      <div class="stat-sub">running sessions</div>
    </div>
    <!-- Room Accounts -->
    <div class="stat-box c-green">
      <div style="display:flex;align-items:center;gap:6px">
        <span class="stat-dot" style="background:#00ff88"></span>
        <span class="stat-label">Room Clients</span>
      </div>
      <div class="stat-count" style="color:var(--g)">
        <span id="sRoomConn">0</span><span style="font-size:1rem;color:rgba(255,255,255,.25)"> / </span><span id="sRoomTotal" style="font-size:1rem;color:rgba(0,255,136,.45)">0</span>
      </div>
      <div class="stat-sub">connected / total</div>
    </div>
    <!-- Badge Accounts -->
    <div class="stat-box c-orange">
      <div style="display:flex;align-items:center;gap:6px">
        <span class="stat-dot" style="background:#ffa500"></span>
        <span class="stat-label">Badge Accs</span>
      </div>
      <div class="stat-count" style="color:var(--o)">
        <span id="sBadgeConn">0</span><span style="font-size:1rem;color:rgba(255,255,255,.25)"> / </span><span id="sBadgeTotal" style="font-size:1rem;color:rgba(255,165,0,.45)">0</span>
      </div>
      <div class="stat-sub">loaded / total</div>
    </div>
    <!-- Friend Accounts -->
    <div class="stat-box c-purple">
      <div style="display:flex;align-items:center;gap:6px">
        <span class="stat-dot" style="background:#c47aff"></span>
        <span class="stat-label">Friend Accs</span>
      </div>
      <div class="stat-count" style="color:var(--p)">
        <span id="sFriendConn">0</span><span style="font-size:1rem;color:rgba(255,255,255,.25)"> / </span><span id="sFriendTotal" style="font-size:1rem;color:rgba(196,122,255,.45)">0</span>
      </div>
      <div class="stat-sub">jwt ready / total</div>
    </div>
  </div>

  <!-- ── LAUNCH PANEL ── -->
  <div class="glass" style="padding:24px;margin-bottom:20px">
    <div class="section-title" style="color:var(--a)"><i class="fa-solid fa-rocket"></i> LAUNCH COMBINED SPAM</div>

    <!-- UID Input -->
    <div style="margin-bottom:16px">
      <label style="font-size:.76rem;color:rgba(255,255,255,.4);font-family:'Orbitron',sans-serif;letter-spacing:1px;display:block;margin-bottom:7px">TARGET FREE FIRE UID</label>
      <div style="display:flex;gap:10px">
        <input class="inp" id="targetUid" placeholder="Enter UID..." style="flex:1;font-size:1.05rem;letter-spacing:2px" oninput="this.value=this.value.replace(/\\D/g,'')">
        <button class="btn-ocean" style="padding:12px 15px" onclick="pasteUid()" title="Paste"><i class="fa-solid fa-paste"></i></button>
      </div>
    </div>

    <!-- Badge Selector -->
    <div style="margin-bottom:16px">
      <label style="font-size:.76rem;color:rgba(255,255,255,.4);font-family:'Orbitron',sans-serif;letter-spacing:1px;display:block;margin-bottom:8px">BADGES <span class="mbadge mb1" style="vertical-align:middle">M1</span></label>
      <div style="display:flex;gap:8px;flex-wrap:wrap" id="badgeChips">
        <div class="badge-chip on" data-v="all">⚡ All Badges</div>
        <div class="badge-chip" data-v="s1">🔴 Craftland</div>
        <div class="badge-chip" data-v="s2">🟣 V-Badge</div>
        <div class="badge-chip" data-v="s3">🟢 Moderator</div>
        <div class="badge-chip" data-v="s4">🔵 Small V</div>
        <div class="badge-chip" data-v="s5">🟡 Pro Badge</div>
      </div>
    </div>

    <!-- Options + Start -->
    <div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap">
      <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:.88rem;user-select:none">
        <input type="checkbox" id="fastMode" style="width:17px;height:17px;accent-color:var(--a)">
        <span>⚡ Fast Mode</span>
      </label>
      <button class="btn-ocean" style="margin-left:auto;padding:13px 28px;font-size:.88rem" onclick="startSpam()">
        <i class="fa-solid fa-play"></i> START ALL 4 METHODS
      </button>
    </div>
    <div id="spamMsg" style="margin-top:11px;font-size:.84rem;opacity:0;transition:.4s;font-family:'Poppins',sans-serif"></div>
  </div>

  <!-- ── ACTIVE SESSIONS ── -->
  <div class="glass" style="padding:22px;margin-bottom:20px">
    <div class="section-title" style="color:#ff4466"><i class="fa-solid fa-crosshairs"></i> ACTIVE SESSIONS</div>
    <div id="activeTargets" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px">
      <p style="color:rgba(255,255,255,.28);font-size:.84rem">No active sessions...</p>
    </div>
  </div>

  <!-- ── LOGS ── -->
  <div class="glass" style="padding:22px;margin-bottom:20px">
    <div class="section-title" style="color:var(--a)"><i class="fa-solid fa-terminal"></i> REAL-TIME LOGS</div>
    <div id="logBox" style="background:#000608;border:1px solid rgba(255,255,255,.07);border-radius:10px;padding:13px;height:190px;overflow-y:auto"></div>
  </div>

</div>
<div class="toast" id="toastEl"></div>
<script>
let selBadges=['all'];

document.getElementById('badgeChips').addEventListener('click',function(e){
  const chip=e.target.closest('.badge-chip');if(!chip)return;
  const v=chip.dataset.v;
  if(v==='all'){
    document.querySelectorAll('.badge-chip').forEach(c=>c.classList.remove('on'));
    chip.classList.add('on');selBadges=['all'];
  }else{
    document.querySelector('.badge-chip[data-v="all"]').classList.remove('on');
    chip.classList.toggle('on');
    selBadges=Array.from(document.querySelectorAll('.badge-chip.on')).map(c=>c.dataset.v);
    if(!selBadges.length){document.querySelector('.badge-chip[data-v="all"]').classList.add('on');selBadges=['all'];}
  }
});

function toast(msg,err=false){
  const el=document.getElementById('toastEl');el.textContent=msg;
  el.style.borderColor=err?'rgba(255,0,85,.5)':'rgba(0,212,255,.5)';
  el.style.color=err?'#ff6080':'#00d4ff';
  el.classList.add('show');setTimeout(()=>el.classList.remove('show'),3500);
}

async function pasteUid(){
  try{const t=await navigator.clipboard.readText();if(/^\\d+$/.test(t.trim())){document.getElementById('targetUid').value=t.trim();toast('UID pasted ✅')}}catch{toast('Clipboard denied',true)}
}

async function startSpam(){
  const uid=document.getElementById('targetUid').value.trim();
  const fast=document.getElementById('fastMode').checked;
  if(!uid)return toast('Enter target UID',true);
  const msg=document.getElementById('spamMsg');
  msg.style.opacity=1;msg.style.color='var(--a)';msg.textContent='Starting all 4 methods...';
  const d=await(await fetch('/api/spam/start',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({target_uid:uid,badges:selBadges.join(','),fast_mode:fast})})).json();
  msg.style.color=d.success?'#00ff88':'#ff4466';msg.textContent=d.message;
  if(d.success){document.getElementById('targetUid').value='';fetchStatus();}
  setTimeout(()=>{msg.style.opacity=0},4200);
}

async function stopSpam(uid){
  const d=await(await fetch('/api/spam/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target_uid:uid})})).json();
  toast(d.success?'⏹ Stopped ✅':'Stop failed',!d.success);fetchStatus();
}

async function doLogout(){
  await fetch('/api/logout',{method:'POST'});window.location='/';
}

const DEF_IMG='https://raw.githubusercontent.com/ashqking/FF-Items/main/ICONS/900000013.png';
const profileCache={};
const expandedStates={};
const startTimes={};

function getItemImg(id){return(!id||id==0)?DEF_IMG:`https://raw.githubusercontent.com/ashqking/FF-Items/main/ICONS/${id}.png`}
function fmtTs(ts){if(!ts)return'N/A';const d=new Date(parseInt(ts)*1000);return d.toLocaleDateString()+' '+d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}
function calcAge(ts){if(!ts)return'N/A';const diff=Date.now()-parseInt(ts)*1000;return Math.floor(diff/86400000)+' DAYS'}
function fmtElapsed(secs){const s=Math.floor(secs);const d=Math.floor(s/86400);const h=Math.floor((s%86400)/3600);const m=Math.floor((s%3600)/60);return`${d}d ${h}h ${m}m`}

function buildTargetCard(t){
  const s=t.stats||{};
  startTimes[t.uid]=t.start_time||0;
  return `<div class="target-card" id="card-${t.uid}">
    <!-- top row: avatar + name + buttons -->
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <div style="width:48px;height:48px;border-radius:12px;border:2px solid rgba(0,212,255,.35);overflow:hidden;background:#000914;flex-shrink:0">
        <img id="av-${t.uid}" src="${DEF_IMG}" onerror="this.src='${DEF_IMG}'" style="width:100%;height:100%;object-fit:contain">
      </div>
      <div style="flex:1;min-width:0">
        <div id="nm-${t.uid}" style="font-family:'Orbitron',sans-serif;color:var(--a);font-size:.88rem;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">UID: ${t.uid}</div>
        <div style="font-size:.72rem;color:rgba(255,255,255,.4);margin-top:2px">
          UID: <span style="color:rgba(255,255,255,.7);font-family:monospace">${t.uid}</span>
          &nbsp;<span id="lvl-${t.uid}" style="color:var(--g);font-weight:700;font-family:'Orbitron',sans-serif"></span>
        </div>
      </div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;flex-shrink:0">
        <div style="display:flex;gap:7px">
          <button id="vbtn-${t.uid}" class="view-more-btn" onclick="toggleViewMore('${t.uid}')">
            <i class="fa-solid fa-chevron-down" style="font-size:9px"></i> View More
          </button>
          <button class="btn-red" style="padding:7px 14px;font-size:.76rem;border-radius:22px" onclick="stopSpam('${t.uid}')">
            <i class="fa-solid fa-hand" style="font-size:9px"></i> STOP
          </button>
        </div>
        <div style="background:rgba(0,0,0,.5);border:1px solid rgba(0,212,255,.15);border-radius:8px;padding:3px 10px;font-family:'Orbitron',sans-serif;font-size:.7rem;color:var(--g)">
          <i class="fa-solid fa-clock" style="font-size:9px"></i> <span id="up-${t.uid}">${fmtElapsed(t.elapsed)}</span>
        </div>
      </div>
    </div>

    <!-- method stats -->
    <div class="mstats">
      <div class="mstat-box">
        <div class="mstat-num" style="color:var(--o)">${s.badge||0}</div>
        <div class="mstat-lbl" style="color:rgba(255,165,0,.6)">BADGE</div>
      </div>
      <div class="mstat-box">
        <div class="mstat-num" style="color:var(--p)">${s.squad||0}</div>
        <div class="mstat-lbl" style="color:rgba(196,122,255,.6)">SQUAD</div>
      </div>
      <div class="mstat-box">
        <div class="mstat-num" style="color:var(--g)">${s.room||0}</div>
        <div class="mstat-lbl" style="color:rgba(0,255,136,.6)">ROOM</div>
      </div>
      <div class="mstat-box">
        <div class="mstat-num" style="color:var(--a)">${s.friend||0}</div>
        <div class="mstat-lbl" style="color:rgba(0,212,255,.6)">FRIEND</div>
      </div>
    </div>

    <!-- expandable profile panel -->
    <div id="pp-${t.uid}" class="profile-panel"></div>
  </div>`;
}

function toggleViewMore(uid){
  const panel=document.getElementById(`pp-${uid}`);
  const btn=document.getElementById(`vbtn-${uid}`);
  if(expandedStates[uid]){
    panel.style.display='none';
    btn.className='view-more-btn';
    btn.innerHTML='<i class="fa-solid fa-chevron-down" style="font-size:9px"></i> View More';
    expandedStates[uid]=false;
  }else{
    panel.style.display='block';
    btn.className='view-less-btn';
    btn.innerHTML='<i class="fa-solid fa-chevron-up" style="font-size:9px"></i> View Less';
    expandedStates[uid]=true;
    if(!profileCache[uid])fetchPlayerProfile(uid);
    else renderProfile(uid,profileCache[uid]);
  }
}

async function fetchPlayerProfile(uid){
  const panel=document.getElementById(`pp-${uid}`);
  if(!panel)return;
  panel.innerHTML='<div style="text-align:center;padding:18px;color:rgba(0,212,255,.5);font-size:.8rem"><i class="fa-solid fa-circle-notch fa-spin"></i> Loading profile...</div>';
  try{
    const r=await fetch(`/api/player_info/${uid}`);
    const d=await r.json();
    if(d.error||!d.AccountInfo){panel.innerHTML=`<div style="text-align:center;color:#ff4466;padding:12px;font-size:.78rem">Profile unavailable</div>`;return;}
    profileCache[uid]=d;
    renderProfile(uid,d);
  }catch(e){panel.innerHTML='<div style="text-align:center;color:#ff4466;padding:12px;font-size:.78rem">Failed to load</div>';}
}

function renderProfile(uid,d){
  const acc=d.AccountInfo||{};
  const guild=d.GuildInfo||{};
  const cap=d.captainBasicInfo||{};
  const pet=d.petInfo||{};
  const soc=d.socialinfo||{};
  const cr=d.creditScoreInfo||{};

  // Update card header avatar + name + level
  const av=document.getElementById(`av-${uid}`);
  if(av&&acc.AccountAvatarId)av.src=getItemImg(acc.AccountAvatarId);
  const nm=document.getElementById(`nm-${uid}`);
  if(nm&&acc.AccountName)nm.textContent=acc.AccountName;
  const lv=document.getElementById(`lvl-${uid}`);
  if(lv&&acc.AccountLevel)lv.textContent='LVL '+acc.AccountLevel;

  const bannerId=acc.AccountBannerId;
  const bannerSrc=bannerId&&bannerId!==0?getItemImg(bannerId):DEF_IMG;
  const avatarSrc=acc.AccountAvatarId?getItemImg(acc.AccountAvatarId):DEF_IMG;
  const region=acc.AccountRegion||'BD';
  const gender=(soc.gender||'N/A').replace('Gender_','');
  const lang=(soc.language||'N/A').replace('Language_','');
  const banStatus=cr.creditScore!==undefined?`Safe (Credit: ${cr.creditScore})`:'Safe';

  let guildBlock=`<div style="font-family:'Orbitron',sans-serif;color:rgba(255,255,255,.5);font-size:.82rem;padding:8px;text-align:center">NO GUILD</div>`;
  if(guild.GuildName){
    // Leader block (captainBasicInfo)
    let leaderBlock='';
    if(cap.accountId){
      const lAvatar=cap.headPic?getItemImg(cap.headPic):DEF_IMG;
      leaderBlock=`
      <div style="margin-top:10px;background:rgba(255,165,0,.06);border:1px solid rgba(255,165,0,.2);border-radius:10px;padding:10px">
        <div style="font-family:'Orbitron',sans-serif;font-size:.68rem;color:#ffa500;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:8px;font-weight:700">
          <i class="fa-solid fa-crown" style="margin-right:4px"></i> Guild Leader
        </div>
        <div style="display:flex;align-items:center;gap:10px">
          <img src="${lAvatar}" onerror="this.src='${DEF_IMG}'" style="width:46px;height:46px;border-radius:10px;border:2px solid rgba(255,165,0,.4);object-fit:cover;flex-shrink:0">
          <div style="flex:1;min-width:0">
            <div style="font-family:'Orbitron',sans-serif;font-size:.88rem;font-weight:900;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${cap.nickname||'Unknown'}</div>
            <div style="font-size:.7rem;color:rgba(255,165,0,.7);margin-top:2px;font-family:'Orbitron',sans-serif">UID: <span style="color:#ffa500;font-weight:700">${cap.accountId||'N/A'}</span></div>
          </div>
          <div style="text-align:right;flex-shrink:0">
            <div style="background:rgba(255,165,0,.15);border:1px solid rgba(255,165,0,.35);border-radius:7px;padding:3px 9px;font-family:'Orbitron',sans-serif;font-size:.72rem;font-weight:800;color:#ffa500">LVL ${cap.level||0}</div>
            <div style="font-size:.65rem;color:rgba(255,255,255,.35);margin-top:4px">♥ ${(cap.liked||0).toLocaleString()}</div>
          </div>
        </div>
        <div class="p-info-grid" style="margin-top:8px">
          <div class="p-info-box"><div class="p-info-label">BR Rank</div><div class="p-info-val" style="color:#f0c040;font-size:.82rem">${cap.rankingPoints||0}</div></div>
          <div class="p-info-box"><div class="p-info-label">CS Rank</div><div class="p-info-val" style="color:var(--g);font-size:.82rem">${cap.csRankingPoints||0}</div></div>
          <div class="p-info-box"><div class="p-info-label">Last Login</div><div class="p-info-val" style="color:rgba(255,255,255,.6);font-size:.72rem">${cap.lastLoginAt?fmtTs(cap.lastLoginAt).split(' ')[0]:'N/A'}</div></div>
        </div>
      </div>`;
    }
    guildBlock=`
    <div style="display:flex;justify-content:space-between;align-items:center;background:rgba(0,0,0,.4);border:1px solid rgba(255,165,0,.2);border-radius:10px;padding:9px 12px">
      <div>
        <div style="font-family:'Orbitron',sans-serif;font-size:.88rem;font-weight:900;color:#fff;text-transform:uppercase">${guild.GuildName}</div>
        <div style="font-size:.68rem;color:rgba(255,255,255,.38);margin-top:2px;font-family:'Orbitron',sans-serif">ID: ${guild.GuildID||0}</div>
      </div>
      <div style="text-align:right">
        <span style="background:rgba(255,165,0,.15);color:#ffa500;border:1px solid rgba(255,165,0,.35);border-radius:8px;padding:3px 10px;font-size:.72rem;font-family:'Orbitron',sans-serif;font-weight:800">LVL ${guild.GuildLevel||0}</span>
        <div style="font-size:.66rem;color:rgba(255,255,255,.4);margin-top:4px;font-family:'Orbitron',sans-serif">👥 ${guild.GuildMember||0} / ${guild.GuildCapacity||0}</div>
      </div>
    </div>
    ${leaderBlock}`;
  }

  let petBlock='<div style="color:rgba(255,255,255,.35);font-size:.78rem;text-align:center;padding:6px">No companion</div>';
  if(pet.id&&pet.id!==0){
    petBlock=`<div class="companion-box">
      <div class="comp-img"><img src="${getItemImg(pet.id)}" onerror="this.src='${DEF_IMG}'" style="width:100%;height:100%;object-fit:contain"></div>
      <div style="flex:1;font-size:.78rem">
        <div style="display:flex;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,.06);padding-bottom:5px;margin-bottom:5px">
          <span style="color:rgba(255,255,255,.45)">ID: <span style="color:#fff;font-weight:700">${pet.id}</span></span>
          <span style="background:rgba(0,255,136,.1);color:var(--g);border:1px solid rgba(0,255,136,.25);border-radius:6px;padding:1px 8px;font-size:.7rem;font-family:'Orbitron',sans-serif;font-weight:700">LVL ${pet.level||0}</span>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;font-size:.72rem;color:rgba(255,255,255,.45)">
          <span>EXP: <span style="color:#fff;font-weight:600">${pet.exp||0}</span></span>
          <span>Skill: <span style="color:#fff;font-weight:600">${pet.selectedSkillId||'N/A'}</span></span>
        </div>
      </div>
    </div>`;
  }

  const panel=document.getElementById(`pp-${uid}`);
  if(!panel)return;
  panel.innerHTML=`
  <!-- Banner + Avatar + Name -->
  <div class="glass-card-inner" style="padding:0;overflow:hidden">
    <div class="banner-wrap"><img src="${bannerSrc}" onerror="this.src='${DEF_IMG}'"></div>
    <div style="padding:0 14px 14px;text-align:center;margin-top:48px">
      <div class="p-avatar-wrap"><img src="${avatarSrc}" onerror="this.src='${DEF_IMG}'"></div>
      <div style="display:flex;align-items:center;justify-content:center;gap:7px;margin-top:8px">
        <span style="font-family:'Orbitron',sans-serif;color:var(--g);font-size:1rem;font-weight:900">${acc.AccountName||'Unknown'}</span>
        <span style="background:rgba(0,212,255,.1);color:var(--a);border:1px solid rgba(0,212,255,.3);border-radius:5px;padding:1px 7px;font-size:.7rem;font-family:'Orbitron',sans-serif;font-weight:700">${region}</span>
      </div>
      <div class="p-info-grid" style="margin-top:12px">
        <div class="p-info-box">
          <div style="color:var(--g);font-size:1.1rem;margin-bottom:3px">♥</div>
          <div class="p-info-label">Likes</div>
          <div class="p-info-val" style="color:#fff">${(acc.AccountLikes||0).toLocaleString()}</div>
        </div>
        <div class="p-info-box">
          <div style="color:#f0c040;font-size:1.1rem;margin-bottom:3px">★</div>
          <div class="p-info-label">Experience</div>
          <div class="p-info-val" style="color:#fff">${(acc.AccountEXP||0).toLocaleString()}</div>
        </div>
      </div>
      ${soc.signature&&soc.signature!=='No Signature'?`<div style="margin-top:10px;padding:8px;background:rgba(0,0,0,.4);border-left:3px solid var(--a);border-radius:8px;font-size:.78rem;color:rgba(255,255,255,.6);text-align:left">${soc.signature}</div>`:''}
    </div>
  </div>

  <!-- Rank Status -->
  <div class="glass-card-inner">
    <div class="section-hdr" style="color:#f0c040"><i class="fa-solid fa-trophy" style="color:#f0c040;font-size:.8rem"></i> RANK STATUS</div>
    <div class="p-info-grid">
      <div class="p-info-box">
        <div class="p-info-label">BR Point</div>
        <div class="p-info-val" style="color:#f0c040">${acc.BrRankPoint||0}</div>
        <div style="font-size:.65rem;color:rgba(255,255,255,.3);margin-top:2px">MAX: ${acc.BrMaxRank||0}</div>
      </div>
      <div class="p-info-box">
        <div class="p-info-label">CS Point</div>
        <div class="p-info-val" style="color:var(--g)">${acc.CsRankPoint||0}</div>
        <div style="font-size:.65rem;color:rgba(255,255,255,.3);margin-top:2px">MAX: ${acc.CsMaxRank||0}</div>
      </div>
    </div>
  </div>

  <!-- Account Metrics -->
  <div class="glass-card-inner">
    <div class="section-hdr" style="color:var(--a)"><i class="fa-solid fa-circle-info" style="color:var(--a);font-size:.8rem"></i> ACCOUNT METRICS</div>
    <div class="p-info-grid" style="margin-bottom:9px">
      <div class="p-info-box"><div class="p-info-label">Gender</div><div class="p-info-val" style="color:#fff;font-size:.82rem">${gender}</div></div>
      <div class="p-info-box"><div class="p-info-label">Language</div><div class="p-info-val" style="color:#fff;font-size:.82rem">${lang}</div></div>
    </div>
    <div style="background:rgba(0,0,0,.35);border-radius:10px;padding:10px">
      <div class="info-row"><span class="info-key">Created:</span><span class="info-val">${fmtTs(acc.AccountCreateTime)}</span></div>
      <div class="info-row"><span class="info-key">Last Login:</span><span class="info-val">${fmtTs(acc.AccountLastLogin)}</span></div>
      <div style="text-align:right;padding-top:5px;font-size:.68rem;color:var(--g);font-family:'Orbitron',sans-serif;font-weight:700;letter-spacing:1px">TIMELINE AGE: ${calcAge(acc.AccountCreateTime)}</div>
    </div>
  </div>

  <!-- Anti-Cheat -->
  <div class="glass-card-inner">
    <div class="section-hdr" style="color:#ff6060"><i class="fa-solid fa-gavel" style="color:#ff6060;font-size:.8rem"></i> ANTI-CHEAT REGISTRY CHECK</div>
    <div style="display:flex;justify-content:space-between;align-items:center;background:rgba(0,0,0,.4);border:1px solid rgba(0,255,136,.1);border-radius:10px;padding:9px 13px">
      <span style="font-size:.74rem;color:rgba(255,255,255,.45);text-transform:uppercase;letter-spacing:1px;font-family:'Orbitron',sans-serif">Current Status</span>
      <span style="color:var(--g);font-weight:800;font-size:.82rem;font-family:'Orbitron',sans-serif">${banStatus}</span>
    </div>
  </div>

  <!-- Companion -->
  <div class="glass-card-inner">
    <div class="section-hdr" style="color:var(--g)"><i class="fa-solid fa-paw" style="color:var(--g);font-size:.8rem"></i> ACTIVE COMPANION</div>
    ${petBlock}
  </div>

  <!-- Guild -->
  <div class="glass-card-inner">
    <div class="section-hdr" style="color:#ffa500"><i class="fa-solid fa-shield-halved" style="color:#ffa500;font-size:.8rem"></i> GUILD OVERVIEW</div>
    ${guildBlock}
  </div>`;
}

async function fetchStatus(){
  try{
    const d=await(await fetch('/api/status')).json();
    document.getElementById('sTargets').textContent=d.active_targets.length;
    document.getElementById('sRoomConn').textContent=d.room_connected;
    document.getElementById('sRoomTotal').textContent=d.room_total;
    document.getElementById('sBadgeConn').textContent=d.badge_connected;
    document.getElementById('sBadgeTotal').textContent=d.badge_total;
    document.getElementById('sFriendConn').textContent=d.friend_connected;
    document.getElementById('sFriendTotal').textContent=d.friend_total;

    const tDiv=document.getElementById('activeTargets');
    if(!d.active_targets.length){
      tDiv.innerHTML='<p style="color:rgba(255,255,255,.28);font-size:.84rem">No active sessions...</p>';
      Object.keys(expandedStates).forEach(k=>delete expandedStates[k]);
      Object.keys(startTimes).forEach(k=>delete startTimes[k]);
    }else{
      // ── add new cards without destroying existing ones ──
      const activeUids=d.active_targets.map(t=>t.uid);
      // remove cards no longer active
      tDiv.querySelectorAll('.target-card').forEach(card=>{
        const uid=card.id.replace('card-','');
        if(!activeUids.includes(uid)){card.remove();delete expandedStates[uid];delete startTimes[uid];}
      });
      // add / update cards
      d.active_targets.forEach(t=>{
        startTimes[t.uid]=t.start_time||0;
        const existing=document.getElementById(`card-${t.uid}`);
        if(!existing){
          tDiv.insertAdjacentHTML('beforeend',buildTargetCard(t));
          // auto-fetch player info for new card
          fetchPlayerProfile(t.uid);
        }else{
          // update stat numbers
          const s=t.stats||{};
          const mboxes=existing.querySelectorAll('.mstat-num');
          if(mboxes[0])mboxes[0].textContent=s.badge||0;
          if(mboxes[1])mboxes[1].textContent=s.squad||0;
          if(mboxes[2])mboxes[2].textContent=s.room||0;
          if(mboxes[3])mboxes[3].textContent=s.friend||0;
        }
      });
      if(!tDiv.querySelector('.target-card'))
        tDiv.innerHTML='<p style="color:rgba(255,255,255,.28);font-size:.84rem">No active sessions...</p>';
    }

    const logBox=document.getElementById('logBox');
    let allLogs=[];
    d.active_targets.forEach(t=>(t.logs||[]).forEach(l=>allLogs.push({...l,uid:t.uid})));
    allLogs.sort((a,b)=>a.ts.localeCompare(b.ts));
    logBox.innerHTML=allLogs.slice(-60).map(l=>{
      const cls=l.level==='success'?'log-s':l.level==='error'?'log-e':'log-i';
      return `<div class="log-line ${cls}">[${l.ts}][${l.uid}] ${l.msg}</div>`;
    }).join('');
    logBox.scrollTop=logBox.scrollHeight;
  }catch(e){}
}

// ── uptime ticker ──
setInterval(()=>{
  const now=Date.now()/1000;
  for(const uid in startTimes){
    const el=document.getElementById(`up-${uid}`);
    if(el&&startTimes[uid]){el.textContent=fmtElapsed(now-startTimes[uid]);}
  }
},1000);

// ── also set username label ──
fetch('/api/status').then(r=>r.json()).then(d=>{
  // show current user from session (just fetch once)
  const lbl=document.getElementById('userLabel');
  if(lbl&&d.username)lbl.textContent='👤 '+d.username;
}).catch(()=>{});

setInterval(fetchStatus,3000);fetchStatus();
</script>
</body></html>"""

# ─────────────────────── ADMIN LOGIN ───────────────────────
ADMIN_LOGIN_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Admin Login</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
""" + SHARED_CSS + """
</head><body>
<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px">
  <div class="glass glow" style="width:100%;max-width:370px;padding:36px">
    <div style="text-align:center;margin-bottom:24px">
      <i class="fa-solid fa-shield-halved" style="font-size:2.4rem;color:var(--a);margin-bottom:10px;display:block"></i>
      <h2 style="font-family:'Orbitron',sans-serif;font-size:1.15rem;color:var(--a);letter-spacing:3px">ADMIN PANEL</h2>
    </div>
    <div style="margin-bottom:13px"><input class="inp" id="aUser" placeholder="Admin Username"></div>
    <div style="margin-bottom:20px"><input class="inp" id="aPass" placeholder="Admin Password" type="password"></div>
    <button class="btn-ocean" style="width:100%;padding:13px;font-size:.88rem" onclick="adminLogin()"><i class="fa-solid fa-lock"></i> ACCESS ADMIN</button>
    <div style="text-align:center;margin-top:15px">
      <a href="/" style="color:rgba(0,212,255,.38);font-size:.76rem;font-family:'Orbitron',sans-serif;text-decoration:none">← Back</a>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>
function toast(msg,err=false){const el=document.getElementById('toast');el.textContent=msg;el.style.color=err?'#ff6080':'#00d4ff';el.classList.add('show');setTimeout(()=>el.classList.remove('show'),3000)}
async function adminLogin(){
  const u=document.getElementById('aUser').value.trim(),p=document.getElementById('aPass').value.trim();
  if(!u||!p)return toast('Fill all fields',true);
  const d=await(await fetch('/api/admin/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})})).json();
  if(d.success)window.location='/admin/dashboard';else toast(d.message||'Access denied',true);
}
document.addEventListener('keydown',e=>{if(e.key==='Enter')adminLogin()});
</script>
</body></html>"""

# ─────────────────────── ADMIN DASHBOARD ───────────────────────
ADMIN_DASH_HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Admin Dashboard</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
""" + SHARED_CSS + """
<style>
.container{position:relative;z-index:1;max-width:1080px;margin:0 auto;padding:20px}
.user-card{background:rgba(0,8,20,.75);border:1px solid rgba(0,212,255,.14);border-radius:13px;padding:15px;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:9px}
.badge-ok{background:rgba(0,255,136,.13);border:1px solid rgba(0,255,136,.38);color:#00ff88;padding:3px 9px;border-radius:18px;font-size:.7rem;font-family:'Orbitron',sans-serif;font-weight:700;letter-spacing:1px}
.badge-pend{background:rgba(255,165,0,.13);border:1px solid rgba(255,165,0,.38);color:var(--o);padding:3px 9px;border-radius:18px;font-size:.7rem;font-family:'Orbitron',sans-serif;font-weight:700;letter-spacing:1px}
.modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(10px);z-index:1000;align-items:center;justify-content:center}
.modal-bg.show{display:flex}
.modal{background:#000d1c;border:1px solid rgba(0,212,255,.28);border-radius:18px;padding:28px;width:100%;max-width:360px}
</style>
</head><body>
<div class="container">
  <div style="display:flex;align-items:center;justify-content:space-between;padding:20px 0;border-bottom:1px solid rgba(0,212,255,.1);margin-bottom:22px;flex-wrap:wrap;gap:12px">
    <div>
      <h1 style="font-family:'Orbitron',sans-serif;font-size:1.25rem;color:var(--a);letter-spacing:3px"><i class="fa-solid fa-shield-halved"></i> ADMIN DASHBOARD</h1>
      <p style="font-size:.73rem;color:rgba(255,255,255,.35);margin-top:4px">BD ADMIN SPAM TOOLS</p>
    </div>
    <a href="/admin/logout" style="background:rgba(255,0,85,.13);border:1px solid rgba(255,0,85,.3);color:#ff4466;padding:7px 16px;border-radius:10px;font-family:'Orbitron',sans-serif;font-size:.73rem;text-decoration:none;letter-spacing:1px">LOGOUT</a>
  </div>

  <!-- Active Spam Monitor -->
  <div class="glass" style="padding:18px;margin-bottom:18px">
    <h2 style="font-family:'Orbitron',sans-serif;font-size:.88rem;color:#ff4466;margin-bottom:13px;letter-spacing:2px"><i class="fa-solid fa-satellite-dish"></i> ACTIVE SPAM MONITOR</h2>
    {% if active_spam %}
    <div style="display:flex;flex-wrap:wrap;gap:9px">
      {% for target in active_spam %}
      <div style="background:rgba(255,0,85,.08);border:1px solid rgba(255,0,85,.22);border-radius:10px;padding:9px 14px;text-align:center">
        <div style="font-size:.62rem;color:rgba(255,255,255,.35)">TARGET</div>
        <div style="font-family:'Orbitron',sans-serif;color:#ff4466;font-size:.88rem;font-weight:900">{{ target }}</div>
        <div style="font-size:.58rem;color:rgba(255,255,255,.28);margin-top:2px">● Running</div>
      </div>
      {% endfor %}
    </div>
    {% else %}
    <p style="color:rgba(255,255,255,.28);font-size:.84rem">No active spam operations</p>
    {% endif %}
  </div>

  <!-- User Management -->
  <div class="glass" style="padding:18px;margin-bottom:18px">
    <h2 style="font-family:'Orbitron',sans-serif;font-size:.88rem;color:var(--a);margin-bottom:15px;letter-spacing:2px"><i class="fa-solid fa-users"></i> USER MANAGEMENT</h2>
    {% for username, user_data in users.items() %}
    <div class="user-card" id="ucard-{{ username }}">
      <div style="display:flex;align-items:center;gap:11px">
        <div style="width:34px;height:34px;border-radius:50%;background:rgba(0,212,255,.09);border:1px solid rgba(0,212,255,.28);display:flex;align-items:center;justify-content:center">
          <i class="fa-solid fa-user" style="color:var(--a);font-size:.82rem"></i>
        </div>
        <div>
          <div style="font-weight:700;font-size:.88rem">{{ username }}</div>
          <div style="font-size:.7rem;color:rgba(255,255,255,.35)">{{ user_data.get('created_at','N/A') }}</div>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:7px;flex-wrap:wrap">
        <span class="{{ 'badge-ok' if user_data.get('approved') else 'badge-pend' }}">{{ 'APPROVED' if user_data.get('approved') else 'PENDING' }}</span>
        {% if not user_data.get('approved') %}
        <button onclick="approveUser('{{ username }}')" class="btn-green"><i class="fa-solid fa-check"></i> APPROVE</button>
        {% else %}
        <button onclick="rejectUser('{{ username }}')" style="background:linear-gradient(135deg,#ffa500,#cc7700);color:#000;font-weight:700;border:none;border-radius:9px;cursor:pointer;padding:6px 12px;font-size:.72rem"><i class="fa-solid fa-ban"></i> REJECT</button>
        {% endif %}
        {% if username in activities and activities[username].get('targets') %}
        <button onclick="stopAll('{{ username }}')" class="btn-red"><i class="fa-solid fa-stop"></i> STOP</button>
        {% endif %}
        <button onclick="showPassModal('{{ username }}')" class="btn-ocean" style="padding:6px 12px;font-size:.72rem"><i class="fa-solid fa-key"></i></button>
        <button onclick="deleteUser('{{ username }}')" class="btn-red" style="padding:6px 10px"><i class="fa-solid fa-trash"></i></button>
      </div>
      {% if username in activities and activities[username].get('targets') %}
      <div style="width:100%;background:rgba(255,0,85,.06);border:1px solid rgba(255,0,85,.14);border-radius:8px;padding:7px;margin-top:3px">
        <span style="font-size:.7rem;color:#ff4466;font-family:'Orbitron',sans-serif">TARGETS: </span>
        {% for t in activities[username]['targets'] %}
        <span style="background:rgba(255,0,85,.13);border:1px solid rgba(255,0,85,.28);color:#ff4466;font-size:.7rem;padding:2px 7px;border-radius:11px;font-family:monospace">{{ t }}</span>
        {% endfor %}
      </div>
      {% endif %}
    </div>
    {% else %}
    <p style="color:rgba(255,255,255,.28);text-align:center;padding:18px">No users registered yet</p>
    {% endfor %}
  </div>
</div>

<div class="modal-bg" id="passModal">
  <div class="modal">
    <h3 style="font-family:'Orbitron',sans-serif;color:var(--a);margin-bottom:6px;font-size:1rem">Change Password</h3>
    <p style="font-size:.8rem;color:rgba(255,255,255,.45);margin-bottom:15px">User: <span id="mUser" style="color:var(--a);font-weight:700"></span></p>
    <input class="inp" id="newPass" type="password" placeholder="New password" style="margin-bottom:15px">
    <div style="display:flex;gap:9px">
      <button onclick="closeModal()" style="flex:1;padding:10px;border-radius:10px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);color:#fff;cursor:pointer;font-family:'Orbitron',sans-serif;font-size:.78rem">CANCEL</button>
      <button onclick="changePass()" class="btn-ocean" style="flex:1;padding:10px;font-size:.78rem">UPDATE</button>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>
let mUser='';
function toast(msg,err=false){const el=document.getElementById('toast');el.textContent=msg;el.style.color=err?'#ff6080':'#00d4ff';el.classList.add('show');setTimeout(()=>el.classList.remove('show'),3000)}
async function approveUser(u){const d=await(await fetch('/api/admin/approve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u})})).json();if(d.success){toast('✅ '+u+' approved');setTimeout(()=>location.reload(),800)}else toast(d.message,true)}
async function rejectUser(u){const d=await(await fetch('/api/admin/reject',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u})})).json();if(d.success){toast(u+' rejected');setTimeout(()=>location.reload(),800)}else toast(d.message,true)}
async function deleteUser(u){if(!confirm('Delete '+u+'?'))return;const d=await(await fetch('/api/admin/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u})})).json();if(d.success){toast('Deleted');document.getElementById('ucard-'+u).remove()}else toast(d.message,true)}
async function stopAll(u){if(!confirm('Stop all spam for '+u+'?'))return;const d=await(await fetch('/api/admin/stop_all',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u})})).json();toast(d.success?'Stopped '+d.stopped+' sessions':'Failed',!d.success)}
function showPassModal(u){mUser=u;document.getElementById('mUser').textContent=u;document.getElementById('passModal').classList.add('show')}
function closeModal(){document.getElementById('passModal').classList.remove('show');document.getElementById('newPass').value='';mUser=''}
async function changePass(){const p=document.getElementById('newPass').value.trim();if(!p)return toast('Enter password',true);const d=await(await fetch('/api/admin/change_password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:mUser,new_password:p})})).json();if(d.success){toast('✅ Password changed');closeModal()}else toast(d.message,true)}
</script>
</body></html>"""

# ============================================================
# MAIN ENTRY
# ============================================================
if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🔥 BD ADMIN COMBINED SPAM TOOL — ALL 4 METHODS")
    print("   M1: All Badge Spam     (account.txt)")
    print("   M2: Squad/Group Invite (account.txt + xC4)")
    print("   M3: Room Spam          (room.txt)")
    print("   M4: Friend Request     (friend.txt)")
    print(f"   xC4: {'✅ Available' if XC4_AVAILABLE else '❌ Not found'}")
    print("=" * 60)

    # Load friend accounts + start JWT refresh
    friend_accounts = Load_Friend_Accounts()
    if friend_accounts:
        print(f"[+] Loaded {len(friend_accounts)} friend accounts (friend.txt)")
        threading.Thread(target=_update_friend_jwt, daemon=True).start()
    else:
        print("[!] No friend accounts (friend.txt)")

    # Start persistent room spam clients
    room_accs = load_room_accounts()
    if room_accs:
        print(f"[+] Starting {len(room_accs)} room clients (room.txt)...")
        threading.Thread(target=start_room_clients, daemon=True).start()
    else:
        print("[!] No room accounts (room.txt)")

    badge_accs = load_badge_accounts()
    print(f"[+] Badge/Squad accounts: {len(badge_accs)} (account.txt)")
    print("=" * 60 + "\n")

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
