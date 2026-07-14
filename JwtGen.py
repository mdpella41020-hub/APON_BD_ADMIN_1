import os
import sys
import json
import binascii
import time
import urllib3
import base64
import re
import socket
import threading
import ssl
import random
import pytz
import aiohttp
import asyncio
import psutil
from datetime import datetime
from protobuf_decoder.protobuf_decoder import Parser
from google.protobuf.timestamp_pb2 import Timestamp
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
from cfonts import render, say

# Crypto/AES Imports
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# external file imports (নিশ্চিত করুন এই ফাইলগুলো আপনার প্রজেক্ট ডিরেক্টরিতে আছে)
try:
    from Functions import *
    from xHeaders import *
    from Pb2 import DEcwHisPErMsG_pb2, MajoRLoGinrEs_pb2, PorTs_pb2, MajoRLoGinrEq_pb2, sQ_pb2, Team_msg_pb2
except ImportError:
    pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  

Chat_Leave = False
joining_team = False

# Global Config
login_url = "https://loginbp.ggblueshark.com"
ob = "OB54"
version = "1.126.1"

Hr = {
    'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 11; ASUS_Z01QD Build/PI)",
    'Connection': "Keep-Alive",
    'Accept-Encoding': "gzip",
    'Content-Type': "application/x-www-form-urlencoded",
    'Expect': "100-continue",
    'X-Unity-Version': "2018.4.11f1",
    'X-GA': "v1 1",
    'ReleaseVersion': ob
}

# --- Helper Utilities ---

def get_random_color():
    colors = [
        "[FF0000]", "[00FF00]", "[0000FF]", "[FFFF00]", "[FF00FF]", "[00FFFF]", "[FFFFFF]", "[FFA500]",
        "[A52A2A]", "[800080]", "[FFD700]", "[ADD8E6]", "[90EE90]", "[00CED1]", "[FF1493]", "[00BFFF]"
    ]
    return random.choice(colors)

def DecodE_HeX(H):
    R = hex(H) 
    F = str(R)[2:]
    if len(F) == 1: 
        return "0" + F
    return F

def xMsGFixinG(n):
    return '🗿'.join(str(n)[i:i + 1] for i in range(0, len(str(n)), 1))

# --- Encryption Functions ---

async def encrypted_proto(encoded_hex):
    key = b'Yg&tc%DEuh6%Zc^8'
    iv = b'6oyZDr22E3ychjM%'
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_message = pad(encoded_hex, AES.block_size)
    encrypted_payload = cipher.encrypt(padded_message)
    return encrypted_payload

async def EnC_PacKeT(HeX, K, V):
    cipher = AES.new(K, AES.MODE_CBC, V)
    return cipher.encrypt(pad(bytes.fromhex(HeX), 16)).hex()

# --- Authentication & Login (JwtGen) ---

async def GeNeRaTeAccEss(uid, password):
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    headers = {
        "Host": "100067.connect.garena.com",
        "User-Agent": "GarenaMSDK/4.0.18P6 (SM-A125F;Android 11;en-US;USA;)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "close"
    }
    data = {
        "uid": uid,
        "password": password,
        "response_type": "token",
        "client_type": "2",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": "100067"
    }
    
    attempt = 1
    while True:
        print(f"[+] Connecting to Garena... Attempt {attempt} for UID: {uid}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=data, timeout=15) as response:
                    if response.status == 200:
                        res_json = await response.json()
                        open_id = res_json.get("open_id")
                        access_token = res_json.get("access_token")
                        if open_id and access_token:
                            print(f"[+] Login Successful on Attempt {attempt}!")
                            return (open_id, access_token)
                    
                    print(f"[-] Attempt {attempt} failed (Status: {response.status}). Retrying...")
        except Exception as e:
            print(f"[-] Network Error on attempt {attempt}: {e}")
        
        attempt += 1
        await asyncio.sleep(5)

async def EncRypTMajoRLoGin(open_id, access_token):
    major_login = MajoRLoGinrEq_pb2.MajorLogin()
    major_login.event_time = str(datetime.now())[:-7]
    major_login.game_name = "free fire"
    major_login.platform_id = 2
    major_login.client_version = "1.126.2"
    major_login.client_version_code = "2024010012"
    major_login.system_software = "Android OS 11 / API-30 (RQ3A.210805.001)"
    major_login.system_hardware = "Handheld"
    major_login.device_type = "Handheld"
    major_login.telecom_operator = "Verizon"
    major_login.network_operator_a = "Verizon"
    major_login.network_type = "WIFI"
    major_login.network_type_a = "WIFI"
    major_login.screen_width = 1080
    major_login.screen_height = 2400
    major_login.screen_dpi = "440"
    major_login.processor_details = "ARMv8"
    major_login.cpu_type = 2
    major_login.cpu_architecture = "64"
    major_login.memory = 6144
    major_login.gpu_renderer = "Adreno (TM) 650"
    major_login.gpu_version = "OpenGL ES 3.2 V@1.50"
    major_login.graphics_api = "OpenGLES3"
    major_login.unique_device_id = "Google|34a7dcdf-a7d5-4cb6-8d7e-3b0e448a0c57"
    major_login.client_ip = ""
    major_login.language = "en"
    major_login.open_id = open_id
    major_login.open_id_type = "4"
    major_login.login_open_id_type = 4
    major_login.access_token = access_token
    major_login.login_by = 3
    major_login.platform_sdk_id = 2
    major_login.origin_platform_type = "4"
    major_login.primary_platform_type = "4"
    
    string = major_login.SerializeToString()
    return await encrypted_proto(string)

async def MajorLogin(payload):
    url = f"{login_url}/MajorLogin"
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=payload, headers=Hr, ssl=ssl_context) as response:
            if response.status == 200: 
                return await response.read()
            return None

async def GetLoginData(base_url, payload, token):
    url = f"{base_url}/GetLoginData"
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    Hr['Authorization'] = f"Bearer {token}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=payload, headers=Hr, ssl=ssl_context) as response:
            if response.status == 200: 
                return await response.read()
            return None

async def DecRypTMajoRLoGin(MajoRLoGinResPonsE):
    proto = MajoRLoGinrEs_pb2.MajorLoginRes()
    proto.ParseFromString(MajoRLoGinResPonsE)
    return proto

async def DecRypTLoGinDaTa(LoGinDaTa):
    proto = PorTs_pb2.GetLoginData()
    proto.ParseFromString(LoGinDaTa)
    return proto

async def DecodeWhisperMessage(hex_packet):
    packet = bytes.fromhex(hex_packet)
    proto = DEcwHisPErMsG_pb2.DecodeWhisper()
    proto.ParseFromString(packet)
    return proto

async def xAuThSTarTuP(TarGeT, token, timestamp, key, iv):
    uid_hex = hex(TarGeT)[2:]
    uid_length = len(uid_hex)
    encrypted_timestamp = DecodE_HeX(timestamp)
    encrypted_account_token = token.encode().hex()
    encrypted_packet = await EnC_PacKeT(encrypted_account_token, key, iv)
    encrypted_packet_length = hex(len(encrypted_packet) // 2)[2:]
    
    if uid_length == 9: headers = '0000000'
    elif uid_length == 8: headers = '00000000'
    elif uid_length == 10: headers = '000000'
    elif uid_length == 7: headers = '000000000'
    else: headers = '0000000'
    
    return f"0115{headers}{uid_hex}{encrypted_timestamp}00000{encrypted_packet_length}{encrypted_packet}"

# --- CLIENT CLASS ---

class CLIENT:
    def __init__(self):
        self.whisper_writer = None
        self.online_writer = None
        self.uid = None
        self.room_uid = None
        self.response = None
        self.inPuTMsG = None
        self.chat_id = None
        self.data = None
        self.data2 = None
        self.key = None
        self.iv = None
        self.STATUS = None
        self.AutHToKen = None
        self.OnLineiP = None
        self.OnLineporT = None
        self.ChaTiP = None
        self.ChaTporT = None
        self.LoGinDaTaUncRypTinG = None
        self.region = None  
        self.XX = None
        self.insquad = None
        self.sent_inv = None
        self.JWT = None

    async def cHTypE(self, H):
        if not H: return 'Squid'
        elif H == 1: return 'CLan'
        elif H == 2: return 'PrivaTe'
        
    async def SEndMsG(self, H, message, Uid, chat_id, key, iv):
        TypE = await self.cHTypE(H)
        if TypE == 'Squid': msg_packet = await xSEndMsgsQ(message, chat_id, key, iv)
        elif TypE == 'CLan': msg_packet = await xSEndMsg(message, 1, chat_id, chat_id, key, iv)
        elif TypE == 'PrivaTe': msg_packet = await xSEndMsg(message, 2, Uid, Uid, key, iv)
        return msg_packet

    async def SEndPacKeT(self, OnLinE, ChaT, TypE, PacKeT):
        if TypE == 'ChaT' and self.whisper_writer: 
            self.whisper_writer.write(PacKeT)
            await self.whisper_writer.drain()
        elif TypE == 'OnLine' and self.online_writer: 
            self.online_writer.write(PacKeT)
            await self.online_writer.drain()
           
    async def TcPOnLine(self, ip, port, key, iv, AutHToKen, reconnect_delay=0.5):
        global joining_team
        while True:
            try:
                reader, writer = await asyncio.open_connection(ip, int(port))
                self.online_writer = writer
                self.online_writer.write(bytes.fromhex(AutHToKen))
                await self.online_writer.drain()
                
                while True:
                    self.data2 = await reader.read(9999)
                    if not self.data2: break
                    
                    hex_data = self.data2.hex()
                    if hex_data.startswith("0f00"):
                        info = await DeCode_PackEt(hex_data[10:])
                        self.STATUS = get_player_status(info)
                        if "IN_ROOM" in self.STATUS:
                            room_uid = self.STATUS['room_uid']
                            await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', await SendRoomInfo(int(room_uid), key, iv))
                        else:
                            P = await self.SEndMsG(2, self.STATUS, self.uid, self.chat_id, key, iv)
                            await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)

                    if hex_data.startswith("0e00"):
                        info = await DeCode_PackEt(hex_data[10:])
                        message = get_room_info(info)
                        P = await self.SEndMsG(2, message, self.uid, self.chat_id, key, iv)
                        await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)

                    if hex_data.startswith("0500") and self.insquad is None and not joining_team:
                        try:
                            packet = json.loads(await DeCode_PackEt(hex_data[10:]))
                            invite_uid = packet['5']['data']['2']['data']['1']['data']
                            squad_owner = packet['5']['data']['1']['data']
                            squad_code = packet['5']['data']['8']['data']

                            await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', await RedZedRefuse(squad_owner, invite_uid, key, iv))
                            await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', await RedZed_SendInv(invite_uid, key, iv))
                            self.insquad = False
                        except:
                            continue
                        if not self.insquad:
                            await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', await RedZedAccepted(squad_owner, squad_code, key, iv))
                            self.insquad = True

                    if hex_data.startswith('0500') and len(hex_data) > 1000 and joining_team:
                        try:
                            packet = json.loads(await DeCode_PackEt(hex_data[10:]))
                            OwNer_UiD, CHaT_CoDe, SQuAD_CoDe = await GeTSQDaTa(packet)
                            await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', await AutH_Chat(3, OwNer_UiD, CHaT_CoDe, key, iv))
                            message = f'[B][C]{get_random_color()}\n- WeLComE To Emote Bot !\n\n[00FF00]Dev : @{xMsGFixinG("redzedking")}'
                            P = await self.SEndMsG(0, message, OwNer_UiD, OwNer_UiD, key, iv)
                            await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)
                        except:
                            pass
                        joining_team = False

            except Exception as e: 
                print(f"- ErroR With OnLine {ip}:{port} - {e}")
            finally:
                if self.online_writer:
                    try:
                        self.online_writer.close()
                        await self.online_writer.wait_closed()
                    except: pass
                    self.online_writer = None
                self.insquad = None
            await asyncio.sleep(reconnect_delay)
                                
    async def TcPChaT(self, ip, port, AutHToKen, key, iv, LoGinDaTaUncRypTinG, ready_event, reconnect_delay=0.5):
        global joining_team
        while True:
            try:
                reader, writer = await asyncio.open_connection(ip, int(port))
                self.whisper_writer = writer
                self.whisper_writer.write(bytes.fromhex(AutHToKen))
                await self.whisper_writer.drain()
                ready_event.set()
                
                if LoGinDaTaUncRypTinG.Clan_ID:
                    clan_id = LoGinDaTaUncRypTinG.Clan_ID
                    clan_compiled_data = LoGinDaTaUncRypTinG.Clan_Compiled_Data
                    pK = await AuthClan(clan_id, clan_compiled_data, key, iv)
                    if self.whisper_writer: 
                        self.whisper_writer.write(pK)
                        await self.whisper_writer.drain()
                        
                while True:
                    self.data = await reader.read(9999)
                    if not self.data: break

                    hex_data = self.data.hex()
                    if hex_data.startswith("120000"):
                        chatdata = json.loads(await DeCode_PackEt(hex_data[10:]))
                        try:
                            self.response = await DecodeWhisperMessage(hex_data[10:])
                            self.uid = self.response.Data.uid
                            self.chat_id = self.response.Data.Chat_ID
                            self.XX = self.response.Data.chat_type
                            self.inPuTMsG = self.response.Data.msg.lower()
                        except:
                            self.response = None

                        if self.response and self.inPuTMsG:
                            if self.inPuTMsG.startswith('/mq'):
                                # lag ফাংশনটি সিঙ্ক হলে লুপটি থ্রেডে চালানো উচিত, নয়তো অসিনক্রোনাস রাখুন
                                for _ in range(100):
                                    lag(self.JWT)
                                    await asyncio.sleep(0.001)
                                    
                            if self.inPuTMsG.startswith('/room'):
                                parts = self.inPuTMsG.strip().split()
                                if len(parts) >= 3:
                                    self.room_uid = parts[1].strip()
                                    password = parts[2].strip()
                                    await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', await RedZedJoinRomm(self.room_uid, password, key, iv))

                            if self.inPuTMsG.startswith('/leave') and self.room_uid:
                                await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', await RedZedLeaveRoom(self.room_uid, key, iv))

                            if self.inPuTMsG.startswith(("/s5")):
                                try:
                                    await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', await self.SEndMsG(self.XX, f"[B][C]{get_random_color()}\n\nAccepT My InV FasT\n\n", self.uid, self.chat_id, key, iv))
                                    await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', await OpEnSq(key, iv, self.region))
                                    await asyncio.sleep(0.5)
                                    await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', await cHSq(5, self.uid, key, iv, self.region))
                                    await asyncio.sleep(0.5)
                                    await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', await SEnd_InV(5, self.uid, key, iv, self.region))
                                    await asyncio.sleep(3)
                                    await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', await ExiT(None, key, iv))
                                except: pass

                            if self.inPuTMsG.startswith('@a'):
                                parts = self.inPuTMsG.strip().split()
                                message = f'[B][C]{get_random_color()}\nACITVE TarGeT -> {xMsGFixinG(self.uid)}\n'
                                await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', await self.SEndMsG(self.XX, message, self.uid, self.chat_id, key, iv))
                                
                                # Parallel Attack/Emote logic using gather
                                tasks = []
                                try:
                                    idT = int(parts[-1])
                                    for p_uid in parts[1:-1]:
                                        clean_uid = p_uid.replace("***", "106") if "***" in p_uid else p_uid
                                        if clean_uid.isdigit():
                                            tasks.append(Emote_k(int(clean_uid), idT, key, iv, self.region))
                                    if tasks:
                                        results = await asyncio.gather(*tasks, return_exceptions=True)
                                        for res in results:
                                            if isinstance(res, bytes):
                                                await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'OnLine', res)
                                except: pass

                            if self.inPuTMsG in ("hi", "hello", "slm", "salam"):
                                message = 'Hello Im Dev RedZed\nTelegram : @RedZedKing'
                                P = await self.SEndMsG(self.XX, message, self.uid, self.chat_id, key, iv)
                                await self.SEndPacKeT(self.whisper_writer, self.online_writer, 'ChaT', P)
                                
                            self.response = None

            except Exception as e: 
                print(f"ErroR Chat {ip}:{port} - {e}")
            finally:
                if self.whisper_writer:
                    try:
                        self.whisper_writer.close()
                        await self.whisper_writer.wait_closed()
                    except: pass
                    self.whisper_writer = None
            await asyncio.sleep(reconnect_delay)

    async def restart(self, task1, task2):
        while True:
            await asyncio.sleep(1) # ইনফিনিট লুপ সেফটি পজ
            if self.online_writer is None or self.whisper_writer is None:
                print("[!] One of the TCP connections dropped. Re-gathering tasks...")
                break
                
    async def MaiiiinE(self):
        Uid, Pw = '5240743519', 'BFD20BEBC1E0D1184981D3538675935F8A620CCD4EA23500DBE62CAEF79F5BF4'
        
        open_id, access_token = await GeNeRaTeAccAccess(Uid, Pw)
        
        PyL = await EncRypTMajoRLoGin(open_id, access_token)
        MajoRLoGinResPonsE = await MajorLogin(PyL)
        if not MajoRLoGinResPonsE: 
            print("TarGeT AccounT => BannEd / NoT ReGisTeReD ! ")
            return None
        
        MajoRLoGinauTh = await DecRypTMajoRLoGin(MajoRLoGinResPonsE)
        UrL = MajoRLoGinauTh.url
        self.JWT = MajoRLoGinauTh.token
        self.region = MajoRLoGinauTh.region  
        TarGeT = MajoRLoGinauTh.account_uid
        key = MajoRLoGinauTh.key
        iv = MajoRLoGinauTh.iv
        timestamp = MajoRLoGinauTh.timestamp
        
        LoGinDaTa = await GetLoginData(UrL, PyL, self.JWT)
        if not LoGinDaTa: 
            print("ErroR - GeTinG PorTs From LoGin DaTa !")
            return None
            
        LoGinDaTaUncRypTinG = await DecRypTLoGinDaTa(LoGinDaTa)
        ReGioN = LoGinDaTaUncRypTinG.Region
        AccountName = LoGinDaTaUncRypTinG.AccountName
        OnLinePorTs = LoGinDaTaUncRypTinG.Online_IP_Port
        ChaTPorTs = LoGinDaTaUncRypTinG.AccountIP_Port
        
        self.OnLineiP, self.OnLineporT = OnLinePorTs.split(":")
        ChaTiP, ChaTporT = ChaTPorTs.split(":")
        
        try:
            equie_emote(self.JWT, UrL)
        except: pass
        
        AutHToKen = await xAuThSTarTuP(int(TarGeT), self.JWT, int(timestamp), key, iv)
        ready_event = asyncio.Event()
        
        task1 = asyncio.create_task(self.TcPChaT(ChaTiP, ChaTporT, AutHToKen, key, iv, LoGinDaTaUncRypTinG, ready_event))
        await ready_event.wait()
        await asyncio.sleep(1)
        task2 = asyncio.create_task(self.TcPOnLine(self.OnLineiP, self.OnLineporT, key, iv, AutHToKen))
        
        print(render('REDZED', colors=['white', 'red'], align='center'))
        print(f" - SerVeR LoGiN UrL => {login_url} | SerVer Url => {UrL}\n")
        print(f" - GaMe sTaTus > Good | OB => {ob} | Version => {version}\n")
        print(f" - BoT STarTinG And OnLine on TarGet : {AccountName} , UiD : {TarGeT} | ReGioN => {ReGioN}\n")
        
        await asyncio.gather(task1, task2)
        await self.restart(task1, task2)

client = CLIENT()

async def StarTinG():
    while True:
        try: 
            await asyncio.wait_for(client.MaiiiinE(), timeout=7 * 60 * 60)
        except asyncio.TimeoutError: 
            print("Token ExpiRed ! , ResTartinG")
        except Exception as e:
            import traceback
            print(f"ErroR TcP - {e} => ResTarTinG ...")
            traceback.print_exc()
            await asyncio.sleep(5)

if __name__ == '__main__':
    asyncio.run(StarTinG())
