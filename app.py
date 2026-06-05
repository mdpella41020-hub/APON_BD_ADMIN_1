import os, time, json, random, socket, threading, asyncio
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
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
active_spam_targets = {}        # target uid -> True
active_spam_lock = threading.Lock()

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
            1: 1, 2: 15, 3: 5, 4: "[FFFF00]ʙᴅ➺ꫝᴅᴍɪɴ", 5: "1", 6: 12, 7: 1, 8: 1, 9: 1,
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
        # If socket is dead, try to reconnect
        if not client.online_sock or client._need_reconnect:
            print(f"[{client.uid}] Reconnecting...")
            client.reconnect()
            if not client.online_sock:
                continue
        try:
            client.online_sock.send(openroom(client.key, client.iv))
            print(f"[{client.uid}] Room khola")
            time.sleep(1.5)
            for i in range(10):
                client.online_sock.send(spmroom(client.key, client.iv, target_id))
                print(f"[{client.uid}] {target_id} ko spam bheja - {i+1}")
                time.sleep(0.2)
        except (BrokenPipeError, OSError) as e:
            print(f"[{client.uid}] Error: {e} -> reconnecting")
            client._need_reconnect = True
        except Exception as e:
            print(f"[{client.uid}] Other error: {e}")

def spam_worker(target_id, duration_minutes):
    print(f"Target {target_id} pe spam start ({duration_minutes} min)")
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
            time.sleep(60)
        except Exception as e:
            print(f"Spam error: {e}")
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
        open_id, access_token = self._run_async(GeNeRaTeAccEss(self.uid, self.password))
        if not open_id or not access_token:
            return False
        payload = self._run_async(EncRypTMajoRLoGin(open_id, access_token))
        login_res = self._run_async(MajorLogin(payload))
        if not login_res:
            return False
        dec = self._run_async(DecRypTMajoRLoGin(login_res))
        self.key = dec.key
        self.iv = dec.iv
        token = dec.token
        timestamp = dec.timestamp
        account_uid = dec.account_uid
        login_data = self._run_async(GetLoginData(dec.url, payload, token))
        if not login_data:
            return False
        ports = self._run_async(DecRypTLoGinDaTa(login_data))
        online_ip, online_port = ports.Online_IP_Port.split(":")
        self.online_ip = online_ip
        self.online_port = int(online_port)
        self.auth_token = self._run_async(xAuThSTarTuP(
            int(account_uid), token, int(timestamp), self.key, self.iv
        ))
        return True

    def _connect_online(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.online_ip, self.online_port))
        sock.send(bytes.fromhex(self.auth_token))
        resp = sock.recv(4096)
        if not resp:
            sock.close()
            return None
        print(f"[+] {self.uid} Online connected")
        return sock

    def _reader(self, sock):
        while self.running:
            try:
                data = sock.recv(4096)
                if not data:
                    break
                # Optionally handle responses (not needed for spam)
            except Exception as e:
                print(f"[{self.uid}] Reader error: {e}")
                break
        self.running = False
        self._need_reconnect = True

    def _connect(self):
        if not self._full_auth():
            print(f"[-] {self.uid} Auth failed")
            return
        sock = self._connect_online()
        if not sock:
            return
        self.online_sock = sock
        self.running = True
        self._need_reconnect = False
        threading.Thread(target=self._reader, args=(sock,), daemon=True).start()
        with connected_clients_lock:
            connected_clients[self.uid] = self
            print(f"Account {self.uid} online aa gaya. Total: {len(connected_clients)}")

    def reconnect(self):
        """Close old socket and reconnect."""
        if self.online_sock:
            try:
                self.online_sock.close()
            except:
                pass
        self.running = False
        self._connect()

# ---------- Load accounts from Eren.txt ----------
def load_accounts():
    accounts = []
    try:
        with open("Eren.txt", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and ":" in line and not line.startswith("#"):
                    uid, pwd = line.split(":", 1)
                    accounts.append((uid, pwd))
    except FileNotFoundError:
        print("Eren.txt nahi mili")
    return accounts

def start_all_accounts():
    for uid, pwd in load_accounts():
        threading.Thread(target=lambda: FF_CLient(uid, pwd), daemon=True).start()
        time.sleep(3)

# ---------- Flask Web App (Hinglish, Eren Yeager) ----------
app = Flask(__name__)

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ʙᴅ➺ꫝᴅᴍɪɴ ULTRA TERMINAL</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">

    <style>
        /* Premium Multi-Color Cyber Theme */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Rajdhani', sans-serif;
            -webkit-font-smoothing: antialiased;
        }

        body {
            background: linear-gradient(135deg, #0a0a0a 0%, #1a0000 25%, #001a00 50%, #0a0a1a 75%, #1a0a00 100%);
            background-size: 400% 400%;
            animation: gradientShift 15s ease infinite;
            color: #ffffff;
            min-height: 100vh;
        }

        @keyframes gradientShift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: 
                radial-gradient(circle at 20% 50%, rgba(255, 0, 0, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 80% 50%, rgba(0, 255, 0, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 50% 80%, rgba(255, 215, 0, 0.05) 0%, transparent 50%);
            pointer-events: none;
            z-index: -1;
        }

        .brand-name {
            background: linear-gradient(90deg, #ff0000, #ff6b00, #ffd700, #00ff00, #00d2ff, #ff00ff, #ff0000);
            background-size: 200% auto;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            animation: rainbowFlow 3s linear infinite;
            font-weight: 900;
            letter-spacing: 2px;
            filter: drop-shadow(0 0 10px rgba(255, 0, 0, 0.5));
        }

        @keyframes rainbowFlow {
            0% { background-position: 0% center; }
            100% { background-position: 200% center; }
        }

        .brand-name-small {
            background: linear-gradient(90deg, #ff3333, #ffaa00, #ffdd44);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            font-weight: 700;
        }

        .stat-box {
            background: linear-gradient(145deg, rgba(20, 0, 0, 0.8), rgba(0, 20, 0, 0.8));
            border: 1px solid rgba(255, 0, 0, 0.3);
            border-radius: 16px;
            text-align: center;
            padding: 15px 10px;
            box-shadow: 0 0 20px rgba(255, 0, 0, 0.1), inset 0 0 15px rgba(0, 255, 0, 0.05);
            transition: all 0.3s ease;
        }
        .stat-box:hover {
            border-color: rgba(255, 215, 0, 0.5);
            box-shadow: 0 0 30px rgba(255, 215, 0, 0.2);
            transform: translateY(-2px);
        }
        .stat-val {
            font-size: 2.2rem;
            font-weight: 700;
            background: linear-gradient(180deg, #ff3333, #ffaa00);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            line-height: 1;
            filter: drop-shadow(0 0 8px rgba(255, 50, 50, 0.6));
        }
        .stat-lbl {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #ff8888;
            margin-top: 4px;
            font-weight: 600;
        }

        .nav-tab {
            background: linear-gradient(145deg, #1a0000, #001a00);
            border: 1px solid rgba(255, 0, 0, 0.3);
            color: #ff6b6b;
            border-radius: 30px;
            font-weight: 700;
            font-size: 0.85rem;
            letter-spacing: 1px;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            will-change: background, box-shadow;
        }
        .nav-tab.active {
            background: linear-gradient(90deg, #ff0000, #ff6b00);
            color: #ffffff;
            box-shadow: 0 0 25px rgba(255, 0, 0, 0.5), 0 0 50px rgba(255, 100, 0, 0.3);
            border-color: #ff6b00;
        }

        .cyber-link-btn {
            background: linear-gradient(145deg, rgba(255, 0, 0, 0.1), rgba(0, 255, 0, 0.05));
            border: 1px solid rgba(255, 0, 0, 0.3);
            color: #ff6b6b;
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 1px;
            padding: 6px 16px;
            border-radius: 20px;
            transition: all 0.25s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .cyber-link-btn:hover {
            background: linear-gradient(90deg, #ff0000, #ff6b00);
            color: #ffffff;
            box-shadow: 0 0 20px rgba(255, 0, 0, 0.5);
            border-color: #ff6b00;
            transform: scale(1.05);
        }

        .cyber-panel {
            background: linear-gradient(145deg, rgba(20, 0, 0, 0.6), rgba(0, 10, 0, 0.6), rgba(10, 0, 20, 0.6));
            border: 1px solid rgba(255, 0, 0, 0.2);
            border-radius: 20px;
            padding: 22px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5), 0 0 30px rgba(255, 0, 0, 0.05);
            position: relative;
            overflow: hidden;
        }
        .cyber-panel::before {
            content: '';
            position: absolute;
            top: -2px;
            left: -2px;
            right: -2px;
            bottom: -2px;
            background: linear-gradient(45deg, #ff0000, #00ff00, #ffd700, #ff0000);
            border-radius: 22px;
            z-index: -1;
            opacity: 0.3;
            filter: blur(10px);
        }
        .panel-title-bar {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 1.1rem;
            font-weight: 700;
            letter-spacing: 1px;
            color: #ff6b6b;
            text-shadow: 0 0 10px rgba(255, 0, 0, 0.3);
            margin-bottom: 20px;
        }
        .panel-indicator {
            width: 4px;
            height: 18px;
            background: linear-gradient(180deg, #ff0000, #ff6b00);
            border-radius: 2px;
            box-shadow: 0 0 8px #ff0000;
        }

        .cyber-input {
            background: linear-gradient(145deg, #0a0000, #000a00);
            border: 1px solid rgba(255, 0, 0, 0.3);
            border-radius: 30px;
            color: #ffffff;
            font-size: 1rem;
            padding: 14px 24px;
            width: 100%;
            outline: none;
            transition: all 0.25s ease;
        }
        .cyber-input:focus {
            border-color: #ff6b00;
            box-shadow: inset 0 0 8px rgba(255, 100, 0, 0.2), 0 0 15px rgba(255, 0, 0, 0.2);
        }
        .cyber-input::placeholder {
            color: #664444;
        }

        .btn-glow-cyan {
            background: linear-gradient(90deg, #ff0000, #ff6b00);
            color: #ffffff;
            font-weight: 700;
            border-radius: 30px;
            font-size: 1rem;
            letter-spacing: 1px;
            box-shadow: 0 0 20px rgba(255, 0, 0, 0.4);
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            will-change: transform, box-shadow;
            border: none;
        }
        .btn-glow-cyan:hover {
            transform: scale(1.02);
            box-shadow: 0 0 35px rgba(255, 0, 0, 0.7), 0 0 60px rgba(255, 100, 0, 0.4);
            background: linear-gradient(90deg, #ff3333, #ff8800);
        }

        .btn-glow-pink {
            background: linear-gradient(90deg, #ff0055, #ff00aa);
            color: #ffffff;
            font-weight: 700;
            border-radius: 30px;
            font-size: 1rem;
            letter-spacing: 1px;
            box-shadow: 0 0 20px rgba(255, 0, 85, 0.4);
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            will-change: transform, box-shadow;
            border: none;
        }
        .btn-glow-pink:hover {
            transform: scale(1.02);
            box-shadow: 0 0 35px rgba(255, 0, 85, 0.7), 0 0 60px rgba(255, 0, 150, 0.4);
            background: linear-gradient(90deg, #ff3388, #ff33cc);
        }

        .inline-stop-btn {
            background: linear-gradient(145deg, rgba(255, 0, 85, 0.2), rgba(255, 0, 150, 0.1));
            border: 1px solid #ff0055;
            color: #ff5588;
            font-size: 10px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .inline-stop-btn:hover {
            background: linear-gradient(90deg, #ff0055, #ff00aa);
            color: #ffffff;
            box-shadow: 0 0 15px #ff0055;
            transform: scale(1.1);
        }

        .panel-scroll::-webkit-scrollbar {
            width: 4px;
        }
        .panel-scroll::-webkit-scrollbar-track {
            background: transparent;
        }
        .panel-scroll::-webkit-scrollbar-thumb {
            background: linear-gradient(180deg, #ff0000, #00ff00);
            border-radius: 10px;
        }

        .toast-box {
            opacity: 0;
            transform: translateY(5px);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            pointer-events: none;
        }
        .toast-box.show {
            opacity: 1;
            transform: translateY(0);
        }

        .header-title {
            background: linear-gradient(90deg, #ff0000, #ffd700, #00ff00, #00d2ff, #ff00ff, #ff0000);
            background-size: 200% auto;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            animation: rainbowFlow 4s linear infinite;
            font-weight: 900;
        }

        .footer-brand {
            background: linear-gradient(90deg, #ff3333, #ffaa00, #ffdd44);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            font-weight: 900;
            animation: rainbowFlow 3s linear infinite;
            background-size: 200% auto;
        }

        .subtitle-text {
            color: #ff8888;
        }

        @keyframes multiColorPulse {
            0%, 100% { box-shadow: 0 0 5px rgba(255, 0, 0, 0.5); }
            25% { box-shadow: 0 0 15px rgba(0, 255, 0, 0.5); }
            50% { box-shadow: 0 0 10px rgba(255, 215, 0, 0.5); }
            75% { box-shadow: 0 0 15px rgba(255, 0, 255, 0.5); }
        }
        .multi-pulse {
            animation: multiColorPulse 2s infinite;
        }
    </style>
</head>
<body class="py-6 px-4 max-w-xl mx-auto flex flex-col justify-start">

    <header class="flex flex-col items-center justify-center my-4 text-center">
        <h1 class="text-3xl font-extrabold tracking-wider uppercase text-shadow">
            <span class="brand-name">ʙᴅ➺ꫝᴅᴍɪɴ</span> CONTROL PANEL
        </h1>
        <p class="text-xs font-semibold tracking-widest subtitle-text uppercase mt-1 mb-3">
            Premium Cyber Infrastructure v3.0
        </p>

        <div class="flex items-center gap-3 mt-1 mb-2">
            <a href="https://t.me/BD_ADMIN_CODER_OFFICIAL" target="_blank" class="cyber-link-btn">
                <i class="fa-brands fa-telegram text-base"></i> TELEGRAM CHANNEL
            </a>
            <a href="https://t.me/BD_ADMIN_20" target="_blank" class="cyber-link-btn" style="color: #00ff88; border-color: rgba(0, 255, 136, 0.3); background: linear-gradient(145deg, rgba(0, 255, 136, 0.1), rgba(0, 200, 100, 0.05));">
                <i class="fa-solid fa-address-card text-base"></i> CONTACT DEVELOPER
            </a>
        </div>
    </header>

    <div class="grid grid-cols-3 gap-3 mb-6">
        <div class="stat-box">
            <div class="stat-val" id="activeSpamCount">0</div>
            <div class="stat-lbl">Active Spam</div>
        </div>
        <div class="stat-box">
            <div class="stat-val" id="autoSpamCount">0</div>
            <div class="stat-lbl">Auto Spam</div>
        </div>
        <div class="stat-box">
            <div class="stat-val" id="accCount">99</div>
            <div class="stat-lbl">Connected</div>
        </div>
    </div>

    <div class="w-full mb-6">
        <button class="nav-tab active w-full py-2.5 px-2 flex items-center justify-center gap-1.5">
            <i class="fa-solid fa-gamepad text-xs"></i> SPAM
        </button>
    </div>

    <div class="space-y-6">

        <div class="cyber-panel">
            <div class="panel-title-bar">
                <div class="panel-indicator"></div>
                <i class="fa-solid fa-crosshairs text-[#ff3366]"></i>
                <h2><span class="brand-name-small">ʙᴅ➺ꫝᴅᴍɪɴ</span> UNLIMITED MODE</h2>
            </div>

            <div class="space-y-4">
                <input type="text" id="targetUid" class="cyber-input" placeholder="Enter Target UID">
                <input type="number" id="duration" class="cyber-input hidden" placeholder="Enter Duration (Minutes)">

                <button id="startBtn" class="btn-glow-cyan w-full py-3.5 flex items-center justify-center gap-2">
                    <i class="fa-solid fa-play text-xs"></i> START OPERATION
                </button>
            </div>

            <div id="startMessage" class="toast-box bg-red-500/10 border border-red-500/30 text-red-400 rounded-xl p-3 mt-3 text-sm font-medium flex items-center gap-2"></div>
        </div>

        <div class="cyber-panel">
            <div class="panel-title-bar">
                <div class="panel-indicator" style="background:linear-gradient(180deg, #ff0055, #ff00aa); box-shadow:0 0 8px #ff0055;"></div>
                <i class="fa-solid fa-octagon-xmark text-red-500"></i>
                <h2>TERMINATION SYSTEM</h2>
            </div>

            <div class="space-y-4">
                <input type="text" id="stopTargetUid" class="cyber-input" placeholder="Enter UID to Stop">

                <button id="stopBtn" class="btn-glow-pink w-full py-3.5 flex items-center justify-center gap-2">
                    <i class="fa-solid fa-square text-xs"></i> STOP OPERATION
                </button>
            </div>

            <div id="stopMessage" class="toast-box bg-red-500/10 border border-red-500/30 text-red-400 rounded-xl p-3 mt-3 text-sm font-medium flex items-center gap-2"></div>
        </div>

        <div class="cyber-panel">
            <div class="panel-title-bar">
                <div class="panel-indicator" style="background:linear-gradient(180deg, #ff0000, #ffd700); box-shadow:0 0 8px #ff0000;"></div>
                <i class="fa-solid fa-satellite-dish"></i>
                <h2><span class="brand-name-small">ʙᴅ➺ꫝᴅᴍɪɴ</span> ACTIVE PIPELINE</h2>
            </div>
            <div id="activeTargets" class="text-center text-sm text-gray-500 py-2 flex flex-col items-center gap-3">
                <span class="flex items-center gap-2"><i class="fa-solid fa-mailbox"></i> No active vectors</span>
            </div>
        </div>

        <div class="cyber-panel">
            <div class="panel-title-bar">
                <div class="panel-indicator"></div>
                <i class="fa-solid fa-robot"></i>
                <h2>CONNECTED <span class="brand-name-small">ʙᴅ➺ꫝᴅᴍɪɴ</span> BOTS</h2>
            </div>
            <div class="panel-scroll overflow-y-auto max-h-[110px] space-y-2" id="accountList">
                <div class="text-center text-sm text-gray-500 py-2 flex items-center justify-center gap-2">
                    <i class="fa-solid fa-circle-notch animate-spin text-xs"></i> Scanning cluster cores...
                </div>
            </div>
        </div>

    </div>

    <footer class="mt-8 text-center text-[11px] font-semibold text-[#ff8888] tracking-widest uppercase">
        System Managed & Engineered By <span class="footer-brand">ʙᴅ➺ꫝᴅᴍɪɴ</span> &copy; 2026
    </footer>

    <script>
        function triggerStopFromTarget(uid) {
            document.getElementById('stopTargetUid').value = uid;
            document.getElementById('stopBtn').click();
        }

        function fetchStatus() {
            fetch('/api/status')
                .then(res => res.json())
                .then(data => {
                    document.getElementById('accCount').innerText = data.connected_accounts;
                    document.getElementById('activeSpamCount').innerText = data.active_spam.length;
                    document.getElementById('autoSpamCount').innerText = data.active_spam.length ? "1" : "0";

                    const accListDiv = document.getElementById('accountList');
                    if (data.accounts && data.accounts.length) {
                        accListDiv.innerHTML = data.accounts.map(acc => `
                            <div class="text-xs account-node px-4 py-2.5 rounded-full text-gray-300 flex items-center justify-between">
                                <span class="flex items-center gap-2"><span class="w-1.5 h-1.5 rounded-full account-node-dot"></span> <span class="brand-name-small">ʙᴅ➺ꫝᴅᴍɪɴ</span>_NODE</span>
                                <span class="text-gray-400 font-mono">${acc}</span>
                            </div>
                        `).join('');
                    } else {
                        accListDiv.innerHTML = '<div class="text-gray-500 text-sm text-center py-2"><i class="fa-solid fa-robot opacity-40 mr-1.5"></i> No active bot servers linked</div>';
                    }

                    const targetsDiv = document.getElementById('activeTargets');
                    if (data.active_spam.length) {
                        targetsDiv.innerHTML = data.active_spam.map(t => `
                            <div class="w-full bg-[#091926] border border-[#ff0055]/20 px-4 py-2 rounded-full flex items-center justify-between shadow-inner multi-pulse">
                                <span class="flex items-center gap-2 text-xs text-gray-300 font-mono">
                                    <span class="w-1.5 h-1.5 rounded-full bg-[#ff0055] animate-pulse"></span> PIPELINE UID: ${t}
                                </span>
                                <button onclick="triggerStopFromTarget('${t}')" class="inline-stop-btn">
                                    <i class="fa-solid fa-stop text-[8px] mr-1"></i> STOP
                                </button>
                            </div>
                        `).join('');
                    } else {
                        targetsDiv.innerHTML = '<span class="text-gray-500 text-sm flex items-center gap-2 py-2"><i class="fa-solid fa-envelope-open opacity-40"></i> No active vectors running</span>';
                    }
                })
                .catch(err => console.error(err));
        }

        function showMessage(elementId, text, isError = false) {
            const el = document.getElementById(elementId);
            el.innerHTML = isError 
                ? `<i class="fa-solid fa-triangle-exclamation"></i> <span>${text}</span>` 
                : `<i class="fa-solid fa-circle-check"></i> <span>${text}</span>`;

            if(isError) {
                el.classList.remove('bg-emerald-500/10', 'border-emerald-500/30', 'text-emerald-400');
                el.classList.add('bg-red-500/10', 'border-red-500/30', 'text-red-400');
            } else {
                el.classList.remove('bg-red-500/10', 'border-red-500/30', 'text-red-400');
                el.classList.add('bg-emerald-500/10', 'border-emerald-500/30', 'text-emerald-400');
            }

            el.classList.add('show');
            setTimeout(() => { el.classList.remove('show'); }, 3500);
        }

        document.getElementById('startBtn').onclick = () => {
            const uid = document.getElementById('targetUid').value.trim();
            const duration = document.getElementById('duration').value.trim();
            if (!uid) {
                showMessage('startMessage', 'Bhai, please target UID input karo!', true);
                return;
            }
            const url = `/start_spam?uid=${encodeURIComponent(uid)}` + (duration ? `&duration=${parseInt(duration)}` : '');
            fetch(url)
                .then(res => res.json())
                .then(data => {
                    if (data.error) {
                        showMessage('startMessage', data.error, true);
                    } else {
                        showMessage('startMessage', `<span class="brand-name-small">ʙᴅ➺ꫝᴅᴍɪɴ</span> Core Deploy: ${data.status}`);
                        document.getElementById('targetUid').value = '';
                        fetchStatus();
                    }
                })
                .catch(err => showMessage('startMessage', 'Server Transmission Failed', true));
        };

        document.getElementById('stopBtn').onclick = () => {
            const uid = document.getElementById('stopTargetUid').value.trim();
            if (!uid) {
                showMessage('stopMessage', 'Bhai, stop korar jonno UID oboshshoi dorkar!', true);
                return;
            }
            fetch(`/stop_spam?uid=${encodeURIComponent(uid)}`)
                .then(res => res.json())
                .then(data => {
                    if (data.error) {
                        showMessage('stopMessage', data.error, true);
                    } else {
                        showMessage('stopMessage', `<span class="brand-name-small">ʙᴅ➺ꫝᴅᴍɪɴ</span> Core Aborted: ${data.status}`);
                        document.getElementById('stopTargetUid').value = '';
                        fetchStatus();
                    }
                })
                .catch(err => showMessage('stopMessage', 'Server Transmission Failed', true));
        };

        fetchStatus();
        setInterval(fetchStatus, 3000);
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def api_status():
    with active_spam_lock:
        active = list(active_spam_targets.keys())
    with connected_clients_lock:
        acc_list = list(connected_clients.keys())
    return jsonify({
        'connected_accounts': len(connected_clients),
        'accounts': acc_list,
        'active_spam': active
    })

@app.route('/start_spam')
def start_spam_route():
    target = request.args.get('uid')
    duration = request.args.get('duration', type=int)
    if not target:
        return jsonify({'error': 'uid parameter chahiye'}), 400
    if not connected_clients:
        return jsonify({'error': 'Koi bot online nahi hai'}), 500
    with active_spam_lock:
        if target in active_spam_targets:
            return jsonify({'error': f'{target} pe already spam chal raha hai'}), 409
        active_spam_targets[target] = True
        threading.Thread(target=spam_worker, args=(target, duration), daemon=True).start()
    return jsonify({
        'status': 'Spam shuru kar diya',
        'target': target,
        'duration_minutes': duration
    })

@app.route('/stop_spam')
def stop_spam_route():
    target = request.args.get('uid')
    if not target:
        return jsonify({'error': 'uid parameter chahiye'}), 400
    with active_spam_lock:
        if target in active_spam_targets:
            del active_spam_targets[target]
            return jsonify({'status': f'{target} ka spam band kar diya'})
        else:
            return jsonify({'error': f'{target} pe koi spam nahi chal raha'}), 404

import os

if __name__ == '__main__':
    # ব্যাকগ্রাউন্ড থ্রেড স্টার্ট করা
    threading.Thread(target=start_all_accounts, daemon=True).start()
    
    # Render-এর দেওয়া PORT খুঁজে নেওয়া, না থাকলে ডিফল্ট ৫০০০ ব্যবহার করা
    port = int(os.environ.get("PORT", 5000))
    
    # পোর্ট ভেরিয়েবলটি এখানে পাস করুন
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)