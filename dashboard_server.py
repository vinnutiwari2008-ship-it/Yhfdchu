# -*- coding: utf-8 -*-
"""
TEAM 84FF Level Up Bot - Professional Web Dashboard & Real-Time EXP Tracker
Embedded Async Web Server (aiohttp)
Optimized for ultra-smooth operation, zero memory leaks, and dynamic multi-account control.
"""

import asyncio
import json
import os
import time
from typing import Dict, List, Any, Optional
from aiohttp import web
from access_control import (bootstrap, current_user, require_user, require_admin, login_response, logout_response, users, save_users, admin_ips, save_admin_ips, client_ip, password_hash, verify_password, blocked_ips, save_blocked_ips, is_ip_blocked, _csrf_token, _check_csrf, _login_locked, _record_failed, _failed_logins, set_maintenance, maintenance_state, maintenance_enabled, effective_expires_at, audit_event, _load_json, _save_json, AUDIT_FILE)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "index.html")
DASHBOARD_TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "dashboard.html")
LOGIN_TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "login.html")
ADMIN_TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "admin.html")
BROADCAST_FILE = os.path.join(BASE_DIR, "broadcast.json")
SITE_CONFIG_FILE = os.path.join(BASE_DIR, "pricing.json")
DEFAULT_SITE_CONFIG = {
    "currency": "$",
    "plans": [
        {"id":"starting","name":"STARTING","price":"1","duration":"24 Hours","slots":3,"link":"/signup","badge":""},
        {"id":"basic","name":"BASIC","price":"2","duration":"48 Hours","slots":3,"link":"/signup","badge":"MOST POPULAR"},
        {"id":"premium","name":"PREMIUM","price":"2.50","duration":"72 Hours","slots":4,"link":"/signup","badge":""}
    ],
    "support_link": "https://t.me/zestyji",
    "notice_button_link": "https://t.me/zestyji",
    "notice_button_text": "Chat Now"
}

def load_site_config():
    try:
        with open(SITE_CONFIG_FILE, "r", encoding="utf-8") as f:
            data=json.load(f)
        if not isinstance(data, dict): raise ValueError("invalid config")
        return data
    except Exception:
        _save_json(SITE_CONFIG_FILE, DEFAULT_SITE_CONFIG)
        return json.loads(json.dumps(DEFAULT_SITE_CONFIG))

def save_site_config(data):
    clean=json.loads(json.dumps(DEFAULT_SITE_CONFIG))
    if isinstance(data, dict):
        clean.update({k:v for k,v in data.items() if k in ("currency","plans","support_link","notice_button_link","notice_button_text")})
        plans=[]
        for p in data.get("plans", []):
            if not isinstance(p, dict): continue
            plans.append({
                "id": str(p.get("id", "plan")).strip()[:40],
                "name": str(p.get("name", "PLAN")).strip()[:40],
                "price": str(p.get("price", "0")).strip()[:30],
                "duration": str(p.get("duration", "Custom")).strip()[:60],
                "slots": max(1, int(p.get("slots", 1))),
                "link": str(p.get("link", "/signup")).strip()[:300],
                "badge": str(p.get("badge", "")).strip()[:40]
            })
        if plans: clean["plans"]=plans
    _save_json(SITE_CONFIG_FILE, clean)
    return clean


# Level-Up IDs are stored inside users.json under each user's `level_up_ids` list.
# accounts.json is intentionally not used by the web dashboard or engine.
def _clean_levelup_record(record, owner):
    if not isinstance(record, dict):
        return None
    out = {}
    if record.get("uid") is not None:
        out["uid"] = str(record.get("uid")).strip()
        if record.get("password") is not None:
            out["password"] = str(record.get("password"))
    elif record.get("token") is not None:
        out["token"] = str(record.get("token")).strip()
    else:
        return None
    out["owner"] = str(owner)
    mode=str(record.get("mode", "battle_royale")).strip().lower()
    if mode not in ("lone_wolf", "battle_royale", "mix"): mode="battle_royale"
    out["mode"] = mode
    out["label"] = str(record.get("label", "")).strip()[:60]
    return out

def load_saved_accounts():
    """Flatten Level-Up IDs stored in users.json for the engine."""
    rows = []
    for user in users():
        if not isinstance(user, dict):
            continue
        owner = str(user.get("username", ""))
        for item in user.get("level_up_ids", []) or []:
            cleaned = _clean_levelup_record(item, owner)
            if cleaned:
                rows.append(cleaned)
    return rows

def _user_levelup_ids(user):
    ids = user.get("level_up_ids", [])
    if not isinstance(ids, list):
        ids = []
        user["level_up_ids"] = ids
    return ids

def _save_user_levelup_ids(username, records):
    arr = users()
    target = next((u for u in arr if str(u.get("username")) == str(username)), None)
    if not target:
        return False
    target["level_up_ids"] = [r for r in records if isinstance(r, dict)]
    save_users(arr)
    return True

def _all_user_records():
    return load_saved_accounts()

EXP_TABLE: Dict[int, int] = {
    1: 0, 2: 48, 3: 202, 4: 544, 5: 1012, 6: 1844, 7: 2792, 8: 3800,
    9: 4870, 10: 6004, 11: 7192, 12: 8448, 13: 9760, 14: 11140, 15: 12566,
    16: 14060, 17: 15610, 18: 17224, 19: 18902, 20: 20632, 21: 22424, 22: 24278,
    23: 26192, 24: 28166, 25: 30200, 26: 32294, 27: 34448, 28: 37804, 29: 41274,
    30: 44870, 31: 48582, 32: 53394, 33: 58566, 34: 64096, 35: 69994, 36: 76460,
    37: 83506, 38: 91128, 39: 99322, 40: 108092, 41: 120144, 42: 133266, 43: 147472,
    44: 162760, 45: 179126, 46: 196572, 47: 215368, 48: 235516, 49: 257010, 50: 279860,
    51: 304056, 52: 348318, 53: 394982, 54: 444044, 55: 495508, 56: 549364, 57: 633756,
    58: 721744, 59: 813336, 60: 908522, 61: 1041438, 62: 1180352, 63: 1325266,
    64: 1476184, 65: 1634300, 66: 1840946, 67: 2056594, 68: 2281242, 69: 2514880,
    70: 2757530, 71: 3059506, 72: 3372284, 73: 3699456, 74: 4041030, 75: 4397002,
    76: 4829104, 77: 5282204, 78: 5756304, 79: 6251408, 80: 6776502, 81: 7381324,
    82: 8043154, 83: 8752982, 84: 9510808, 85: 10316338, 86: 11277190, 87: 12291748,
    88: 13360304, 89: 14482858, 90: 15659418, 91: 17026708, 92: 18453950, 93: 19941280,
    94: 21488570, 95: 23095858, 96: 24763138, 97: 26490428, 98: 28378704, 99: 30124996,
    100: 32032884
}

def calculate_level_progress(level: int, current_exp: int) -> Dict[str, Any]:
    level = max(1, level)
    next_level = min(100, level + 1)
    base_exp = EXP_TABLE.get(level, 0)
    target_exp = EXP_TABLE.get(next_level, base_exp + 50000)
    
    needed_for_level = max(1, target_exp - base_exp)
    earned_in_level = max(0, current_exp - base_exp)
    remaining_exp = max(0, target_exp - current_exp)
    progress_pct = min(100.0, max(0.0, (earned_in_level / needed_for_level) * 100.0))

    return {
        "next_level": next_level,
        "base_exp": base_exp,
        "target_exp": target_exp,
        "needed_for_level": needed_for_level,
        "earned_in_level": earned_in_level,
        "remaining_exp": remaining_exp,
        "progress_pct": round(progress_pct, 1)
    }

# Global bot state shared between Main.py and Web Dashboard
class BotState:
    def __init__(self):
        self.accounts: Dict[str, Dict[str, Any]] = {}
        self.logs: List[Dict[str, Any]] = []
        self.max_logs = 200
        self.total_matches = 0
        self.total_gained_exp = 0
        self.start_time = time.time()
        self.account_workers: Dict[str, asyncio.Task] = {}
        self.account_token_map: Dict[str, str] = {}  # uid -> token or token_prefix -> uid
        self.auth_to_game_id: Dict[str, str] = {}   # guest login uid -> in-game account id
        self.game_to_auth_id: Dict[str, str] = {}   # in-game account id -> guest login uid
        self.paused_accounts: set = set()
        self.refresh_callbacks: Dict[str, Any] = {}
        self.account_credentials: Dict[str, Dict[str, Any]] = {}
        self.maintenance_mode = maintenance_enabled()

    def log(self, message: str, level: str = "info", uid: Optional[str] = None):
        entry = {
            "time": time.strftime("%H:%M:%S"),
            "level": level,
            "message": message,
            "uid": str(uid) if uid else None
        }
        self.logs.append(entry)
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)

    def register_account(self, uid: str, nickname: str, region: str, level: int, exp: int,
                         likes: int = 0, token: Optional[str] = None, auth_uid: Optional[str] = None):
        uid_str = str(uid)
        auth_uid_str = str(auth_uid) if auth_uid else self.game_to_auth_id.get(uid_str, "")
        if auth_uid_str:
            self.auth_to_game_id[auth_uid_str] = uid_str
            self.game_to_auth_id[uid_str] = auth_uid_str
            self.account_token_map[auth_uid_str] = uid_str
            self.account_token_map[uid_str] = auth_uid_str
        if token:
            self.account_token_map[uid_str] = token
            self.account_token_map[token[:16]] = uid_str
            if auth_uid_str:
                self.account_token_map[auth_uid_str] = token

        prog = calculate_level_progress(level or 1, exp)

        if uid_str not in self.accounts:
            self.accounts[uid_str] = {
                "uid": uid_str,
                "auth_uid": auth_uid_str or "",
                "nickname": nickname or f"Player_{uid_str[:6]}",
                "region": region or "BD",
                "level": level or 1,
                "next_level": prog["next_level"],
                "initial_exp": exp,
                "current_exp": exp,
                "gained_exp": 0,
                "remaining_exp": prog["remaining_exp"],
                "target_exp": prog["target_exp"],
                "needed_for_level": prog["needed_for_level"],
                "earned_in_level": prog["earned_in_level"],
                "progress_pct": prog["progress_pct"],
                "likes": likes or 0,
                "status": "PAUSED" if self.is_paused(uid_str) else "ONLINE",
                "matches_played": 0,
                "active_matches": 0,
                "last_match_time": None,
                "token": token or "",
                "start_time": time.time(),
                "is_paused": self.is_paused(uid_str),
                "paused_at": time.time() if self.is_paused(uid_str) else None,
                "total_pause_duration": 0.0,
                "last_updated": time.strftime("%H:%M:%S")
            }
        else:
            acc = self.accounts[uid_str]
            if auth_uid_str:
                acc["auth_uid"] = auth_uid_str
            if nickname:
                acc["nickname"] = nickname
            if region:
                acc["region"] = region
            if level:
                acc["level"] = level
            if token:
                acc["token"] = token
            acc["current_exp"] = exp
            acc["gained_exp"] = max(0, exp - acc["initial_exp"])
            acc["next_level"] = prog["next_level"]
            acc["remaining_exp"] = prog["remaining_exp"]
            acc["target_exp"] = prog["target_exp"]
            acc["needed_for_level"] = prog["needed_for_level"]
            acc["earned_in_level"] = prog["earned_in_level"]
            acc["progress_pct"] = prog["progress_pct"]
            acc["likes"] = likes
            if not acc.get("is_paused"):
                acc["status"] = "ONLINE"
            acc["last_updated"] = time.strftime("%H:%M:%S")
        self.recalc_totals()

    def get_account_uptime(self, uid_str: str) -> int:
        acc = self.accounts.get(uid_str)
        if not acc:
            mapped = self.game_to_auth_id.get(uid_str) or self.auth_to_game_id.get(uid_str)
            if mapped and mapped in self.accounts:
                acc = self.accounts[mapped]
        if not acc:
            return 0
        start_t = acc.get("start_time", time.time())
        total_pause = acc.get("total_pause_duration", 0.0)
        if acc.get("is_paused") and acc.get("paused_at"):
            return max(0, int(acc["paused_at"] - start_t - total_pause))
        return max(0, int(time.time() - start_t - total_pause))

    def _resolve_account_key(self, uid: str) -> Optional[str]:
        uid_str = str(uid)
        if uid_str in self.accounts:
            return uid_str
        if uid_str in self.auth_to_game_id and self.auth_to_game_id[uid_str] in self.accounts:
            return self.auth_to_game_id[uid_str]
        if uid_str in self.game_to_auth_id and self.game_to_auth_id[uid_str] in self.accounts:
            return self.game_to_auth_id[uid_str]
        if uid_str in self.account_token_map and self.account_token_map[uid_str] in self.accounts:
            return self.account_token_map[uid_str]
        for k, v in self.accounts.items():
            if str(v.get("auth_uid")) == uid_str or str(v.get("uid")) == uid_str:
                return k
        return None

    def is_paused(self, uid: str) -> bool:
        if self.maintenance_mode:
            return True
        uid_str = str(uid)
        target = self._resolve_account_key(uid_str) or uid_str
        if target in self.paused_accounts or uid_str in self.paused_accounts:
            return True
        game_id = self.auth_to_game_id.get(uid_str)
        if game_id and game_id in self.paused_accounts:
            return True
        auth_uid = self.game_to_auth_id.get(uid_str)
        if auth_uid and auth_uid in self.paused_accounts:
            return True
        acc = self.accounts.get(target) or self.accounts.get(uid_str) or (self.accounts.get(game_id) if game_id else None)
        if acc and acc.get("is_paused"):
            return True
        return False

    def toggle_pause(self, uid: str) -> bool:
        uid_str = str(uid)
        candidates = {uid_str}
        if uid_str in self.auth_to_game_id:
            candidates.add(self.auth_to_game_id[uid_str])
        if uid_str in self.game_to_auth_id:
            candidates.add(self.game_to_auth_id[uid_str])
        resolved = self._resolve_account_key(uid_str)
        if resolved:
            candidates.add(resolved)

        target_acc = None
        target_key = uid_str
        for c in candidates:
            if c in self.accounts:
                target_acc = self.accounts[c]
                target_key = c
                break

        is_now_paused = not self.is_paused(uid_str)
        if is_now_paused:
            for c in candidates:
                self.paused_accounts.add(c)
            if target_acc:
                target_acc["is_paused"] = True
                target_acc["paused_at"] = time.time()
                target_acc["status"] = "PAUSED"
            nick = target_acc.get("nickname", target_key) if target_acc else target_key
            self.log(f"⏸ UID {target_key} ({nick}) matchmaking PAUSED.", "warning", target_key)
        else:
            for c in candidates:
                self.paused_accounts.discard(c)
            if target_acc:
                target_acc["is_paused"] = False
                if target_acc.get("paused_at"):
                    pause_dur = time.time() - target_acc["paused_at"]
                    target_acc["total_pause_duration"] = target_acc.get("total_pause_duration", 0.0) + pause_dur
                    target_acc["paused_at"] = None
                target_acc["status"] = "ONLINE"
            nick = target_acc.get("nickname", target_key) if target_acc else target_key
            self.log(f"▶ UID {target_key} ({nick}) matchmaking RESUMED.", "success", target_key)

        return is_now_paused

    def toggle_pause_all(self) -> bool:
        any_active = any(not self.is_paused(k) for k in self.accounts.keys())
        for k in list(self.accounts.keys()):
            current_paused = self.is_paused(k)
            if any_active and not current_paused:
                self.toggle_pause(k)
            elif not any_active and current_paused:
                self.toggle_pause(k)
        return any_active

    def update_exp(self, uid: str, current_exp: int, level: Optional[int] = None):
        uid_str = str(uid)
        target = self._resolve_account_key(uid_str) or uid_str
        if target in self.accounts:
            acc = self.accounts[target]
            old_exp = acc["current_exp"]
            acc["current_exp"] = current_exp
            if level is not None and level > 0:
                acc["level"] = level
            acc["gained_exp"] = max(0, current_exp - acc["initial_exp"])
            
            prog = calculate_level_progress(acc["level"], current_exp)
            acc["next_level"] = prog["next_level"]
            acc["remaining_exp"] = prog["remaining_exp"]
            acc["target_exp"] = prog["target_exp"]
            acc["needed_for_level"] = prog["needed_for_level"]
            acc["earned_in_level"] = prog["earned_in_level"]
            acc["progress_pct"] = prog["progress_pct"]
            acc["last_updated"] = time.strftime("%H:%M:%S")

            diff = current_exp - old_exp
            if diff > 0:
                self.log(
                    f"★ UID {target} ({acc['nickname']}) gained +{diff:,} EXP | Level {acc['level']} ({prog['progress_pct']}% - {prog['remaining_exp']:,} EXP to Lvl {prog['next_level']})",
                    "success",
                    target
                )
            self.recalc_totals()

    def update_status(self, uid: str, status: str, active_matches: Optional[int] = None):
        uid_str = str(uid)
        target = self._resolve_account_key(uid_str) or uid_str
        if target in self.accounts:
            self.accounts[target]["status"] = status
            if active_matches is not None:
                self.accounts[target]["active_matches"] = active_matches
            self.accounts[target]["last_updated"] = time.strftime("%H:%M:%S")

    def increment_match(self, uid: str):
        uid_str = str(uid)
        self.total_matches += 1
        target = self._resolve_account_key(uid_str) or uid_str
        if target in self.accounts:
            self.accounts[target]["matches_played"] += 1
            self.accounts[target]["last_match_time"] = time.strftime("%H:%M:%S")
            self.accounts[target]["last_updated"] = time.strftime("%H:%M:%S")
            self.log(f"⚔ Match #{self.accounts[target]['matches_played']} finished for {self.accounts[target]['nickname']} ({target})", "info", target)

    def recalc_totals(self):
        self.total_gained_exp = sum(acc.get("gained_exp", 0) for acc in self.accounts.values())


bot_state = BotState()


# Fallback HTML if templates/index.html is missing
FALLBACK_INDEX_HTML = """<!DOCTYPE html>
<html>
<head><title>Bot Dashboard</title></head>
<body style="background:#060913;color:#fff;font-family:sans-serif;text-align:center;padding:50px;">
<h1>TEAM 84FF BOT RUNNING</h1>
<p>templates/index.html is loading...</p>
</body>
</html>"""


# ==================== HTTP HANDLERS ====================

async def handle_index(request: web.Request) -> web.Response:
    if current_user(request):
        raise web.HTTPFound("/dashboard")
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f: html=f.read()
    try:
        with open(BROADCAST_FILE, "r", encoding="utf-8") as bf: msg=str(json.load(bf).get("message", ""))
    except Exception: msg=""
    html=html.replace("{{BROADCAST}}", msg.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"))
    return web.Response(text=html, content_type="text/html", charset="utf-8")

async def handle_login_page(request: web.Request) -> web.Response:
    user = current_user(request)
    if user:
        raise web.HTTPFound("/zestyadmin" if user.get("role") == "admin" else "/dashboard")
    with open(LOGIN_TEMPLATE_PATH, "r", encoding="utf-8") as f: html = f.read()
    return web.Response(text=html.replace("{{CSRF}}", _csrf_token()).replace("{{MESSAGE}}", ""), content_type="text/html")


async def handle_login(request: web.Request) -> web.Response:
    try:
        data = await request.post()
        if not _check_csrf(str(data.get("csrf", ""))):
            return web.Response(text="Invalid security token.", status=403)
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        ip = client_ip(request)
        if _login_locked(ip):
            audit_event(request, "login_rate_limited", username)
            return web.Response(text="Authentication temporarily unavailable. Please try again later.", status=429)
        user = next((u for u in users() if u.get("username") == username), None)
        if not user or user.get("banned") or not verify_password(password, str(user.get("password_hash", ""))):
            _record_failed(ip)
            audit_event(request, "login_failed", username)
            return web.Response(text="Your username or password is incorrect.", status=401)
        if not str(user.get("password_hash", "")).startswith("pbkdf2$"):
            user["password_hash"] = password_hash(password)
            save_users(users())
        expires = int(user.get("expires_at") or 0)
        if expires and expires < int(time.time()):
            audit_event(request, "login_expired", username)
            return web.Response(text="This access ID has expired.", status=403)
        _failed_logins.pop(ip, None)
        audit_event(request, "login_success", username, "admin" if user.get("role") == "admin" else "user")
        # Record a minimal device/IP audit trail; this is not an access gate.
        devices = _load_json(os.path.join(BASE_DIR, "admin_devices.json"), {"devices": []})
        if not isinstance(devices, dict): devices = {"devices": []}
        arr = devices.get("devices", [])
        ua_hash = __import__('hashlib').sha256(request.headers.get('User-Agent','')[:500].encode()).hexdigest()
        arr = [d for d in arr if not (d.get("username") == username and d.get("ua_hash") == ua_hash)]
        arr.append({"username": username, "ua_hash": ua_hash, "last_ip": ip, "last_seen": int(time.time()), "created_at": int(time.time())})
        _save_json(os.path.join(BASE_DIR, "admin_devices.json"), {"devices": arr[-100:]})
        return login_response(username, "/zestyadmin" if user.get("role") == "admin" else "/dashboard", request=request)
    except Exception:
        return web.Response(text="Login failed.", status=400)


async def handle_security_devices(request):
    require_admin(request)
    data = _load_json(os.path.join(BASE_DIR, "admin_devices.json"), {"devices": []})
    return web.json_response({"devices": data.get("devices", [])[-100:]})


async def handle_security_device_action(request):
    require_admin(request)
    data = await request.json()
    action = str(data.get("action", ""))
    devices = _load_json(os.path.join(BASE_DIR, "admin_devices.json"), {"devices": []})
    if action == "clear":
        _save_json(os.path.join(BASE_DIR, "admin_devices.json"), {"devices": []})
        audit_event(request, "device_audit_cleared", current_user(request).get("username", ""))
        return web.json_response({"status":"ok"})
    return web.json_response({"status":"error","error":"Unknown device action"}, status=400)


async def handle_signup(request: web.Request):
    raise web.HTTPFound("https://t.me/zestyji?text=hey%20bro%20I%20want%20to%20buy%20level%20up%20website%20access%20tell%20me%20prices%20%E2%9D%A4%EF%B8%8F")

async def handle_logout(request: web.Request):
    return logout_response()

async def handle_signup(request: web.Request):
    raise web.HTTPFound("https://t.me/zestyji?text=hey%20bro%20I%20want%20to%20buy%20level%20up%20website%20access%20tell%20me%20prices%20%E2%9D%A4%EF%B8%8F")

async def handle_dashboard_page(request: web.Request) -> web.Response:
    require_user(request)
    with open(DASHBOARD_TEMPLATE_PATH, "r", encoding="utf-8") as f: content=f.read()
    return web.Response(text=content, content_type="text/html", charset="utf-8")

async def handle_admin_page(request: web.Request):
    require_admin(request)
    with open(ADMIN_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("{{CSRF}}", _csrf_token()).replace("{{MAINTENANCE}}", "ON" if maintenance_enabled() else "OFF")
    return web.Response(text=html, content_type="text/html")

async def handle_get_stats(request: web.Request) -> web.Response:
    user = require_user(request)
    registry = _all_user_records()
    if user.get("role") != "admin":
        owner = str(user.get("username", ""))
        registry = [a for a in registry if str(a.get("owner", "")) == owner]

    runtime = list(bot_state.accounts.values())
    if user.get("role") != "admin":
        owner = str(user.get("username", ""))
        allowed_auth = {str(a.get("uid", "")) for a in registry}
        runtime = [a for a in runtime if str(a.get("auth_uid", "")) in allowed_auth or str(a.get("uid", "")) in allowed_auth]

    by_game, by_auth, by_token = {}, {}, {}
    for a in runtime:
        item = dict(a)
        if a.get("uid"): by_game[str(a.get("uid"))] = item
        if a.get("auth_uid"): by_auth[str(a.get("auth_uid"))] = item
        if a.get("token"): by_token[str(a.get("token"))] = item

    merged=[]
    for saved in registry:
        saved_uid=str(saved.get("uid", "")).strip()
        saved_token=str(saved.get("token", "")).strip()
        item = by_auth.get(saved_uid) or by_game.get(saved_uid) or (by_token.get(saved_token) if saved_token else None)
        if item:
            item=dict(item)
        else:
            item={
                "uid": saved_uid, "auth_uid": saved_uid, "saved_uid": saved_uid,
                "nickname": "Waiting for login" if saved_uid else "Waiting for token login",
                "region": "BD", "status": "STARTING", "level": 1,
                "current_exp": 0, "initial_exp": 0, "gained_exp": 0,
                "remaining_exp": 0, "target_exp": 48, "needed_for_level": 48,
                "earned_in_level": 0, "progress_pct": 0, "matches_played": 0,
                "active_matches": 0, "last_match_time": None, "last_updated": "—",
                "token": saved_token
            }
        item["saved_uid"] = saved_uid
        item["owner"] = saved.get("owner", user.get("username"))
        item["has_password"] = bool(saved.get("password"))
        item["has_token"] = bool(saved.get("token"))
        item["mode"] = saved.get("mode", "battle_royale")
        item["label"] = saved.get("label", "")
        merged.append(item)

    merged.sort(key=lambda x: (x.get("status") == "STARTING", -(x.get("gained_exp") or 0)))
    uptime_sec=max(1,int(time.time()-bot_state.start_time))
    total_gained=sum(int(a.get("gained_exp",0) or 0) for a in merged)
    total_matches=sum(int(a.get("matches_played",0) or 0) for a in merged)
    active_matches=sum(int(a.get("active_matches",0) or 0) for a in merged)
    exp_per_hour=int((total_gained/max(1,uptime_sec))*3600)
    for a in merged:
        a["uptime_seconds"] = bot_state.get_account_uptime(str(a.get("uid") or a.get("saved_uid")))
    return web.json_response({
        "total_accounts": len(merged), "resolved_accounts": len(runtime),
        "total_gained_exp": total_gained, "total_matches": total_matches,
        "total_active_matches": active_matches, "exp_per_hour": exp_per_hour,
        "uptime": uptime_sec, "accounts": merged
    })

async def handle_account_profile(request: web.Request) -> web.Response:
    user=require_user(request)
    access_type=str(user.get("access_type") or "levelup").lower()
    plan={"label":access_type.upper(),"slots":3}
    if access_type == "premium": plan["slots"]=4
    if access_type == "admin": plan["slots"]=999999
    if user.get("slots") is not None:
        try: plan["slots"]=max(1,int(user.get("slots")))
        except Exception: pass
    owner=str(user.get("username",""))
    rows=[a for a in _all_user_records() if user.get("role")=="admin" or str(a.get("owner"))==owner]
    expires=effective_expires_at(user)
    remaining=max(0, expires-int(time.time())) if expires else 0
    return web.json_response({"username":owner,"role":user.get("role"),"access_type":access_type,"plan":plan,"slots_used":len(rows),"expires_at":expires,"remaining_seconds":remaining,"maintenance":maintenance_enabled()})

async def handle_add_account(request: web.Request) -> web.Response:
    try:
        requester=require_user(request)
        data=await request.json()
        owner=str(requester.get("username",""))
        arr=users()
        target=next((u for u in arr if str(u.get("username"))==owner),None)
        if not target: return web.json_response({"status":"error","error":"User not found"},status=404)
        records=_user_levelup_ids(target)
        access_type=str(requester.get("access_type") or "levelup").lower()
        default_slots={"starting":3,"basic":3,"premium":4}.get(access_type,3)
        try: limit=max(1,int(requester.get("slots",default_slots)))
        except Exception: limit=default_slots
        if requester.get("role")=="admin": limit=999999

        if data.get("uid") is not None:
            uid=str(data.get("uid")).strip(); pwd=str(data.get("password","")).strip()
            if not uid or not pwd: return web.json_response({"status":"error","error":"UID and Password are required"},status=400)
            existing=next((r for r in records if str(r.get("uid",""))==uid),None)
            if existing is None and len(records)>=limit: return web.json_response({"status":"error","error":f"Slot limit reached ({len(records)}/{limit}). Delete an account to free a slot."},status=409)
            records=[r for r in records if str(r.get("uid",""))!=uid]
            mode=str(data.get("mode", "battle_royale")).lower()
            if mode not in ("lone_wolf", "battle_royale", "mix"): mode="battle_royale"
            records.append({"uid":uid,"password":pwd,"mode":mode})
            callback_data={"uid":uid,"password":pwd}
        elif data.get("token") is not None:
            token=str(data.get("token")).strip()
            if not token: return web.json_response({"status":"error","error":"Token is required"},status=400)
            existing=next((r for r in records if str(r.get("token",""))==token),None)
            if existing is None and len(records)>=limit: return web.json_response({"status":"error","error":f"Slot limit reached ({len(records)}/{limit}). Delete an account to free a slot."},status=409)
            records=[r for r in records if str(r.get("token",""))!=token]
            mode=str(data.get("mode", "battle_royale")).lower()
            if mode not in ("lone_wolf", "battle_royale", "mix"): mode="battle_royale"
            records.append({"token":token,"mode":mode})
            callback_data={"token":token}
        else:
            return web.json_response({"status":"error","error":"Invalid payload"},status=400)

        target["level_up_ids"]=records
        save_users(arr)
        callback=bot_state.refresh_callbacks.get("on_account_added")
        if callback: asyncio.create_task(callback(callback_data))
        return web.json_response({"status":"ok","slots_used":len(records),"slots":limit})
    except Exception as e:
        return web.json_response({"status":"error","error":str(e)},status=500)

async def handle_delete_account(request: web.Request) -> web.Response:
    try:
        requester=require_user(request); data=await request.json()
        req_uid=str(data.get("uid","")).strip(); req_auth=str(data.get("auth_uid","")).strip()
        if not req_uid and not req_auth: return web.json_response({"status":"error","error":"UID is required"},status=400)
        candidates={req_uid,req_auth}
        for c in list(candidates):
            if c in bot_state.game_to_auth_id: candidates.add(str(bot_state.game_to_auth_id[c]))
            if c in bot_state.auth_to_game_id: candidates.add(str(bot_state.auth_to_game_id[c]))
        targets=[]
        arr=users()
        for u in arr:
            if requester.get("role")!="admin" and str(u.get("username"))!=str(requester.get("username")): continue
            old=_user_levelup_ids(u); keep=[]; removed=[]
            for r in old:
                rid=str(r.get("uid","")).strip(); tok=str(r.get("token","")).strip()
                match=rid in candidates or any(x and (x==rid or x==tok) for x in candidates)
                if match: removed.append(r)
                else: keep.append(r)
            if removed:
                u["level_up_ids"]=keep; targets.extend(removed)
        if not targets: return web.json_response({"status":"error","error":"Level-Up ID not found"},status=404)
        save_users(arr)

        target_tokens=set()
        for r in targets:
            if r.get("token"): target_tokens.add(str(r.get("token")))
            if r.get("uid"): candidates.add(str(r.get("uid")))
        for cid in list(candidates):
            acc=bot_state.accounts.get(cid,{})
            if acc.get("auth_uid"): candidates.add(str(acc.get("auth_uid")))
            if acc.get("uid"): candidates.add(str(acc.get("uid")))
            if acc.get("token"): target_tokens.add(str(acc.get("token")))
            bot_state.accounts.pop(cid,None); bot_state.account_credentials.pop(cid,None)
            bot_state.auth_to_game_id.pop(cid,None); bot_state.game_to_auth_id.pop(cid,None); bot_state.account_token_map.pop(cid,None)
        for k,w in list(bot_state.account_workers.items()):
            ks=str(k)
            if ks in candidates or any(t and (ks==t[:16] or ks==t) for t in target_tokens):
                try: w.cancel()
                except Exception: pass
                bot_state.account_workers.pop(k,None)
        if bot_state.refresh_callbacks.get("on_account_deleted"):
            asyncio.create_task(bot_state.refresh_callbacks["on_account_deleted"](list(candidates)))
        return web.json_response({"status":"ok","deleted":list(candidates)})
    except Exception as e:
        return web.json_response({"status":"error","error":str(e)},status=500)

async def handle_refresh_account(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        uid = str(data.get("uid", "")).strip()
        if "on_refresh_account" in bot_state.refresh_callbacks:
            asyncio.create_task(bot_state.refresh_callbacks["on_refresh_account"](uid))
        return web.json_response({"status": "ok"})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})


async def handle_restart_account(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        uid = str(data.get("uid", "")).strip()
        if "on_restart_account" in bot_state.refresh_callbacks:
            asyncio.create_task(bot_state.refresh_callbacks["on_restart_account"](uid))
        elif "on_refresh_account" in bot_state.refresh_callbacks:
            asyncio.create_task(bot_state.refresh_callbacks["on_refresh_account"](uid))
        return web.json_response({"status": "ok"})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})


async def handle_toggle_pause(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        uid = str(data.get("uid", "")).strip()
        if not uid:
            return web.json_response({"status": "error", "error": "UID is required"})
        is_paused = bot_state.toggle_pause(uid)
        return web.json_response({"status": "ok", "is_paused": is_paused})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})


async def handle_toggle_pause_all(request: web.Request) -> web.Response:
    try:
        paused_state = bot_state.toggle_pause_all()
        return web.json_response({"status": "ok", "all_paused": paused_state})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})



async def handle_account_mode(request: web.Request) -> web.Response:
    try:
        requester=require_user(request); data=await request.json()
        uid=str(data.get("uid","")).strip()
        mode=str(data.get("mode","battle_royale")).strip().lower()
        if mode not in ("lone_wolf","battle_royale","mix"):
            return web.json_response({"status":"error","error":"Invalid mode"},status=400)
        arr=users(); changed=False
        candidates={uid}
        if uid in bot_state.game_to_auth_id: candidates.add(str(bot_state.game_to_auth_id[uid]))
        if uid in bot_state.auth_to_game_id: candidates.add(str(bot_state.auth_to_game_id[uid]))
        if uid in bot_state.account_token_map: candidates.add(str(bot_state.account_token_map[uid]))
        for u in arr:
            if requester.get("role")!="admin" and str(u.get("username"))!=str(requester.get("username")): continue
            rows=_user_levelup_ids(u)
            for r in rows:
                rid=str(r.get("uid","")).strip()
                tok=str(r.get("token","")).strip()
                if any(c and (c==rid or c==tok or c==tok[:16]) for c in candidates):
                    r["mode"]=mode; changed=True
        if not changed:
            return web.json_response({"status":"error","error":"Level-Up ID not found"},status=404)
        save_users(arr)
        # Update live state immediately for UI and the next match cycle.
        target=bot_state._resolve_account_key(uid) or uid
        if target in bot_state.accounts: bot_state.accounts[target]["mode"]=mode
        return web.json_response({"status":"ok","mode":mode})
    except Exception as e:
        return web.json_response({"status":"error","error":str(e)},status=500)

async def handle_admin_site_config(request: web.Request):
    require_admin(request)
    if request.method == "GET":
        return web.json_response(load_site_config())
    try:
        data=await request.json()
        return web.json_response({"status":"ok","config":save_site_config(data)})
    except Exception as e:
        return web.json_response({"status":"error","error":str(e)},status=400)

async def handle_public_site_config(request):
    cfg=load_site_config()
    return web.json_response(cfg)

async def handle_admin_pause_all(request):
    require_admin(request)
    try:
        paused=bot_state.toggle_pause_all()
        return web.json_response({"status":"ok","all_paused":paused})
    except Exception as e:
        return web.json_response({"status":"error","error":str(e)},status=500)

async def handle_admin_delete_all_user_ids(request):
    require_admin(request)
    try:
        arr=users(); deleted=0; cancelled=0
        for u in arr:
            if u.get("role")=="admin":
                continue
            rows=_user_levelup_ids(u); deleted += len(rows); u["level_up_ids"]=[]
        save_users(arr)
        for key, task in list(bot_state.account_workers.items()):
            try:
                if not task.done(): task.cancel(); cancelled += 1
            except Exception: pass
        bot_state.account_workers.clear()
        bot_state.accounts.clear(); bot_state.account_credentials.clear(); bot_state.auth_to_game_id.clear(); bot_state.game_to_auth_id.clear(); bot_state.account_token_map.clear(); bot_state.paused_accounts.clear()
        return web.json_response({"status":"ok","deleted_ids":deleted,"cancelled_workers":cancelled})
    except Exception as e:
        return web.json_response({"status":"error","error":str(e)},status=500)

async def handle_admin_broadcast(request):
    require_admin(request)
    if request.method == "GET":
        try:
            with open(BROADCAST_FILE,"r",encoding="utf-8") as f: data=json.load(f)
        except Exception: data={"message":""}
        return web.json_response(data)
    data=await request.json(); message=str(data.get("message","")).strip()[:240]
    button_text=str(data.get("button_text", "Chat Now")).strip()[:40] or "Chat Now"
    button_link=str(data.get("button_link", load_site_config().get("notice_button_link", "https://t.me/zestyji"))).strip()[:300]
    with open(BROADCAST_FILE,"w",encoding="utf-8") as f: json.dump({"message":message,"button_text":button_text,"button_link":button_link,"updated_at":int(time.time())},f,indent=2)
    return web.json_response({"status":"ok","message":message,"button_text":button_text,"button_link":button_link})

async def handle_admin_users(request):
    require_admin(request)
    out=[]
    now=int(time.time())
    for u in users():
        item={k:v for k,v in dict(u).items() if k not in ("password","password_hash")}
        item["effective_expires_at"] = effective_expires_at(item)
        item["expired"]=bool(item.get("expires_at")) and item["effective_expires_at"] < now
        out.append(item)
    return web.json_response({"users":out, "admin_ips":admin_ips().get("allowed_ips",[]), "client_ip":client_ip(request)})

async def handle_admin_create_user(request):
    require_admin(request)
    data=await request.json()
    username=str(data.get("username","")).strip()
    password=str(data.get("password",""))
    access_type=str(data.get("type","levelup")).strip().lower()
    days=max(0,int(data.get("days",30) or 0))
    slots=max(1,int(data.get("slots",3) or 3))
    if not username or not password:
        return web.json_response({"status":"error","error":"Username and password are required"}, status=400)
    if any(u.get("username")==username for u in users()):
        return web.json_response({"status":"error","error":"Username already exists"}, status=409)
    role="admin" if access_type=="admin" else "user"
    expires=0 if days==0 else int(time.time())+days*86400
    arr=users()
    arr.append({"username":username,"password_hash":password_hash(password),"role":role,"access_type":access_type,"slots":(999999 if role=="admin" else slots),"created_at":int(time.time()),"expires_at":expires,"banned":False,"auth_version":1})
    save_users(arr)
    return web.json_response({"status":"ok","user":arr[-1]})

async def handle_admin_user_action(request):
    require_admin(request)
    data=await request.json()
    username=str(data.get("username","")).strip()
    action=str(data.get("action","")).strip()
    arr=users()
    target=next((u for u in arr if u.get("username")==username),None)
    if not target:
        return web.json_response({"status":"error","error":"User not found"},status=404)
    if target.get("role")=="admin" and action in ("ban","delete"):
        return web.json_response({"status":"error","error":"Use a separate admin account before changing another admin"},status=400)
    if action=="ban": target["banned"]=True
    elif action=="unban": target["banned"]=False
    elif action=="delete": arr=[u for u in arr if u.get("username")!=username]
    elif action=="extend":
        days=max(1,int(data.get("days",30) or 30))
        base_exp = effective_expires_at(target)
        if base_exp:
            target["expires_at"] = base_exp + days*86400
            if maintenance_enabled():
                state = maintenance_state()
                target["expires_at"] -= max(0, int(time.time()) - int(state.get("started_at") or int(time.time())))
        else:
            target["expires_at"] = int(time.time()) + days*86400
    elif action=="slots":
        target["slots"] = 999999 if target.get("role")=="admin" else max(1,int(data.get("slots",3) or 3))
    elif action=="password":
        pw=str(data.get("password",""));
        if len(pw)<6: return web.json_response({"status":"error","error":"Password must be at least 6 characters"},status=400)
        target.pop("password",None); target["password_hash"]=password_hash(pw); target["auth_version"]=int(target.get("auth_version",1))+1
    else: return web.json_response({"status":"error","error":"Unknown action"},status=400)
    save_users(arr)
    return web.json_response({"status":"ok"})

async def handle_admin_ips(request):
    require_admin(request)
    data=await request.json()
    action=data.get("action")
    ip=str(data.get("ip","")).strip()
    cfg=admin_ips(); ips=set(cfg.get("allowed_ips",[]))
    if action=="add" and ip: ips.add(ip)
    elif action=="remove" and ip: ips.discard(ip)
    elif action=="clear": ips=set()
    else: return web.json_response({"status":"error","error":"Invalid IP action"},status=400)
    cfg["allowed_ips"]=sorted(ips); save_admin_ips(cfg)
    return web.json_response({"status":"ok","admin_ips":cfg["allowed_ips"]})

async def handle_admin_blocked_ips(request):
    require_admin(request)
    data = await request.json()
    action = str(data.get("action", "")).strip().lower()
    ip = str(data.get("ip", "")).strip()
    cfg = blocked_ips()
    values = set(str(x).strip() for x in cfg.get("blocked_ips", []) if str(x).strip())
    if action == "add" and ip:
        # Never allow the primary admin IP to be blocked from the control panel.
        if ip == "103.13.194.90":
            return web.json_response({"status":"error","error":"Primary admin IP cannot be blocked"}, status=400)
        values.add(ip)
    elif action == "remove" and ip:
        values.discard(ip)
    elif action == "clear":
        values.clear()
    else:
        return web.json_response({"status":"error","error":"Invalid blocked-IP action"}, status=400)
    cfg["blocked_ips"] = sorted(values)
    save_blocked_ips(cfg)
    return web.json_response({"status":"ok", "blocked_ips": cfg["blocked_ips"]})


async def handle_download_ids(request):
    user=require_user(request)
    rows=_all_user_records()
    if user.get("role")!="admin":
        rows=[a for a in rows if str(a.get("owner"))==str(user.get("username"))]
    lines=["UID,PASSWORD,TYPE,OWNER"]
    for a in rows:
        if a.get("uid"):
            lines.append(",".join([str(a.get("uid","")),str(a.get("password","")),"guest",str(a.get("owner",""))]))
        elif a.get("token"):
            lines.append(",".join(["TOKEN",str(a.get("token","")),"token",str(a.get("owner",""))]))
    return web.Response(text="\n".join(lines)+"\n", content_type="text/csv", headers={"Content-Disposition":"attachment; filename=zesty-level-up-ids.csv"})

async def handle_download_ids_zip(request):
    """Fast personal Level-Up ID export as a ZIP without exposing other users."""
    user = require_user(request)
    import io, zipfile, json as _json
    owner = str(user.get("username", ""))
    rows = _all_user_records()
    if user.get("role") != "admin":
        rows = [a for a in rows if str(a.get("owner")) == owner]
    safe_rows = []
    for a in rows:
        if a.get("uid"):
            safe_rows.append({"uid": str(a.get("uid")), "password": str(a.get("password", "")), "type": "guest"})
        elif a.get("token"):
            safe_rows.append({"token": str(a.get("token")), "type": "token"})
    payload = _json.dumps(safe_rows, ensure_ascii=False, indent=2)
    csv_lines = ["UID,PASSWORD,TYPE"]
    for a in safe_rows:
        if a.get("uid"):
            uid = a["uid"].replace('"','""'); pw = a.get("password","").replace('"','""')
            csv_lines.append(f'"{uid}","{pw}","guest"')
        else:
            tok = a.get("token","").replace('"','""')
            csv_lines.append(f'"TOKEN","{tok}","token"')
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("level_up_ids.json", payload)
        z.writestr("level_up_ids.csv", "\n".join(csv_lines) + "\n")
        z.writestr("README.txt", "Zesty Level Up ID export\nKeep this file private.\n")
    audit_event(request, "ids_exported", owner, f"count={len(safe_rows)}")
    return web.Response(body=bio.getvalue(), content_type="application/zip", headers={"Content-Disposition": "attachment; filename=zesty-level-up-ids.zip", "Cache-Control": "no-store"})

async def handle_user_notice(request):
    require_user(request)
    try:
        with open(BROADCAST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {"message": ""}
    return web.json_response({"message": str(data.get("message", ""))[:240], "updated_at": int(data.get("updated_at", 0) or 0)}, headers={"Cache-Control":"no-store"})

async def handle_admin_export(request):
    require_admin(request)
    bundle={}
    for fn in ("users.json","devices.json","token_cache.json","admin_ips.json"):
        p=os.path.join(BASE_DIR,fn)
        if os.path.exists(p):
            try:
                with open(p,"r",encoding="utf-8") as f: bundle[fn]=json.load(f)
            except Exception: pass
    return web.json_response(bundle, headers={"Content-Disposition":"attachment; filename=zesty-db-export.json"})

async def handle_admin_import(request):
    require_admin(request)
    data=await request.json()
    if not isinstance(data,dict): return web.json_response({"status":"error","error":"JSON object required"},status=400)
    allowed={"users.json","devices.json","token_cache.json","admin_ips.json"}
    for fn,val in data.items():
        if fn in allowed: 
            with open(os.path.join(BASE_DIR,fn),"w",encoding="utf-8") as f: json.dump(val,f,indent=2)
    bootstrap()
    return web.json_response({"status":"ok"})


async def handle_admin_settings(request):
    require_admin(request)
    data = await request.json()
    action = str(data.get("action", "")).strip()
    if action == "change_credentials":
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        current_password = str(data.get("current_password", ""))
        if len(username) < 3 or len(password) < 8 or len(current_password) < 1:
            return web.json_response({"status":"error","error":"Username must be 3+ chars and password 8+ chars"}, status=400)
        arr = users(); me = next((u for u in arr if u.get("username") == current_user(request).get("username")), None)
        if not me: return web.json_response({"status":"error","error":"Admin not found"}, status=404)
        if not verify_password(current_password, str(me.get("password_hash", ""))):
            audit_event(request, "credential_change_rejected", me.get("username", ""))
            return web.json_response({"status":"error","error":"Current password is incorrect"}, status=403)
        if any(u is not me and u.get("username") == username for u in arr):
            return web.json_response({"status":"error","error":"Username already exists"}, status=409)
        old_username = me.get("username")
        me["username"] = username; me["password_hash"] = password_hash(password); me["auth_version"] = int(me.get("auth_version",1))+1
        save_users(arr)
        _save_json(os.path.join(BASE_DIR, "admin_devices.json"), {"devices": []})
        audit_event(request, "credentials_changed", old_username)
        resp = web.json_response({"status":"ok","message":"Credentials changed. Sign in again."})
        resp.del_cookie("zesty_session", path="/")
        return resp
    if action == "maintenance":
        enabled = bool(data.get("enabled"))
        state = set_maintenance(enabled)
        bot_state.maintenance_mode = enabled
        for acc in bot_state.accounts.values():
            acc["status"] = "MAINTENANCE" if enabled else ("PAUSED" if acc.get("is_paused") else "ONLINE")
        return web.json_response({"status":"ok","maintenance":state})
    return web.json_response({"status":"error","error":"Unknown settings action"}, status=400)


async def handle_admin_devices(request):
    require_admin(request)
    from access_control import _device_store, _save_json, DEVICES_FILE
    data = _device_store()
    if request.method == "GET":
        safe=[]
        for d in data.get("devices",[]):
            safe.append({k:v for k,v in d.items() if k != "token_hash"})
        return web.json_response({"devices":safe})
    body=await request.json(); action=str(body.get("action","")); username=str(body.get("username","")); ua_hash=str(body.get("ua_hash",""))
    if action=="revoke":
        data["devices"]=[d for d in data.get("devices",[]) if not (d.get("username")==username and (not ua_hash or d.get("ua_hash")==ua_hash))]
        _save_json(DEVICES_FILE,data); return web.json_response({"status":"ok"})
    return web.json_response({"status":"error","error":"Unknown device action"},status=400)


async def handle_admin_export_zip(request):
    require_admin(request)
    import io, zipfile
    files = ("users.json","devices.json","token_cache.json","admin_ips.json","blocked_ips.json","maintenance.json","broadcast.json","admin_devices.json","pricing.json")
    bio=io.BytesIO()
    with zipfile.ZipFile(bio,"w",zipfile.ZIP_DEFLATED) as z:
        for fn in files:
            path=os.path.join(BASE_DIR,fn)
            if os.path.exists(path): z.write(path,fn)
    return web.Response(body=bio.getvalue(), content_type="application/zip", headers={"Content-Disposition":"attachment; filename=zesty-backup.zip"})


async def handle_admin_import_zip(request):
    require_admin(request)
    import io, zipfile
    raw=await request.read()
    if len(raw)>25*1024*1024: return web.json_response({"status":"error","error":"Backup is too large"},status=413)
    allowed={"users.json","devices.json","token_cache.json","admin_ips.json","blocked_ips.json","maintenance.json","broadcast.json","admin_devices.json"}
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names=z.namelist()
            if any(n not in allowed or n.endswith("/") for n in names): raise ValueError("Backup contains unsupported files")
            parsed={n:json.loads(z.read(n).decode("utf-8")) for n in names}
        for fn,val in parsed.items():
            if fn in allowed and isinstance(val,(dict,list)):
                with open(os.path.join(BASE_DIR,fn),"w",encoding="utf-8") as f: json.dump(val,f,indent=2,ensure_ascii=False)
        bootstrap()
        return web.json_response({"status":"ok"})
    except Exception as e:
        return web.json_response({"status":"error","error":f"Invalid backup: {e}"},status=400)


async def handle_security_audit(request):
    require_admin(request)
    data = _load_json(AUDIT_FILE, {"events": []})
    return web.json_response({"events": data.get("events", [])[-200:]})


@web.middleware
async def admin_csrf_middleware(request, handler):
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.path.startswith("/api/admin/"):
        token = request.headers.get("X-CSRF-Token", "")
        if not _check_csrf(token):
            return web.json_response({"status":"error","error":"Invalid security token"}, status=403)
    response = await handler(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self' 'unsafe-inline' https: data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    # Private dashboard/API responses should never be cached by browsers/proxies.
    if request.path.startswith(("/dashboard", "/zestyadmin", "/api/")):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    if request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip() == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


async def start_web_dashboard(host: str = "0.0.0.0", port: int = 5000):
    app = web.Application(middlewares=[admin_csrf_middleware])
    async def _robots(_request):
        return web.Response(text="User-agent: *\nDisallow: /dashboard\nDisallow: /zestyadmin\nDisallow: /api/\nDisallow: /login\n", content_type="text/plain")
    app.router.add_get("/robots.txt", _robots)
    app.router.add_get("/", handle_index)
    app.router.add_get("/dashboard", handle_dashboard_page)
    app.router.add_get("/login", handle_login_page)
    app.router.add_post("/login", handle_login)
    app.router.add_get("/logout", handle_logout)
    app.router.add_get("/signup", handle_signup)
    app.router.add_get("/zestyadmin", handle_admin_page)
    app.router.add_get("/api/stats", handle_get_stats)
    app.router.add_get("/api/download/ids", handle_download_ids)
    app.router.add_get("/api/download/ids.zip", handle_download_ids_zip)
    app.router.add_get("/api/notice", handle_user_notice)
    app.router.add_get("/api/account/profile", handle_account_profile)
    app.router.add_get("/api/site-config", handle_public_site_config)
    app.router.add_post("/api/account/mode", handle_account_mode)
    app.router.add_get("/api/admin/broadcast", handle_admin_broadcast)
    app.router.add_post("/api/admin/broadcast", handle_admin_broadcast)
    app.router.add_get("/api/admin/users", handle_admin_users)
    app.router.add_post("/api/admin/users/create", handle_admin_create_user)
    app.router.add_post("/api/admin/users/action", handle_admin_user_action)
    app.router.add_post("/api/admin/ips", handle_admin_ips)
    app.router.add_get("/api/admin/blocked-ips", lambda request: (require_admin(request), web.json_response(blocked_ips()))[1])
    app.router.add_post("/api/admin/blocked-ips", handle_admin_blocked_ips)
    app.router.add_get("/api/admin/export-db", handle_admin_export)
    app.router.add_post("/api/admin/import-db", handle_admin_import)
    app.router.add_get("/api/admin/export-zip", handle_admin_export_zip)
    app.router.add_post("/api/admin/import-zip", handle_admin_import_zip)
    app.router.add_post("/api/admin/settings", handle_admin_settings)
    app.router.add_get("/api/admin/site-config", handle_admin_site_config)
    app.router.add_post("/api/admin/site-config", handle_admin_site_config)
    app.router.add_post("/api/admin/pause-all", handle_admin_pause_all)
    app.router.add_post("/api/admin/delete-all-user-ids", handle_admin_delete_all_user_ids)
    app.router.add_get("/api/admin/devices", handle_security_devices)
    app.router.add_post("/api/admin/devices", handle_security_device_action)
    app.router.add_get("/api/admin/audit", handle_security_audit)
    app.router.add_post("/api/account/add", handle_add_account)
    app.router.add_post("/api/account/delete", handle_delete_account)
    app.router.add_post("/api/account/refresh", handle_refresh_account)
    app.router.add_post("/api/account/restart", handle_restart_account)
    app.router.add_post("/api/account/pause", handle_toggle_pause)
    app.router.add_post("/api/account/pause_all", handle_toggle_pause_all)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    return runner
