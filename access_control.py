"""Zesty Level Up Engine authentication, sessions, rate limiting and maintenance state."""
import base64, hashlib, hmac, json, os, secrets, time, ipaddress
from aiohttp import web

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(DATA_DIR, "users.json")
ADMIN_IPS_FILE = os.path.join(DATA_DIR, "admin_ips.json")
BLOCKED_IPS_FILE = os.path.join(DATA_DIR, "blocked_ips.json")
MAINTENANCE_FILE = os.path.join(DATA_DIR, "maintenance.json")
AUDIT_FILE = os.path.join(DATA_DIR, "security_audit.json")
SECRET_FILE = os.path.join(DATA_DIR, ".zesty_secret")
SESSION_COOKIE = "zesty_session"
DEFAULT_ADMIN_USERNAME = os.getenv("ZESTY_ADMIN_USERNAME", "Zesty")
DEFAULT_ADMIN_PASSWORD = os.getenv("ZESTY_ADMIN_PASSWORD", "123456")
_failed_logins = {}


def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, value):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _secret():
    if not os.path.exists(SECRET_FILE):
        _save_json(SECRET_FILE, {"secret": secrets.token_hex(32)})
    return str(_load_json(SECRET_FILE, {}).get("secret") or "")


def password_hash(password):
    password = str(password)
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return "pbkdf2$210000$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password, stored):
    password = str(password)
    stored = str(stored or "")
    if stored.startswith("pbkdf2$"):
        try:
            _, rounds, salt_b64, digest_b64 = stored.split("$", 3)
            salt = base64.b64decode(salt_b64.encode())
            expected = base64.b64decode(digest_b64.encode())
            got = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds))
            return hmac.compare_digest(got, expected)
        except Exception:
            return False
    # Backward compatibility for older installations.
    return hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(), stored)


def client_ip(request):
    forwarded = request.headers.get("X-Forwarded-For", "")
    candidate = forwarded.split(",")[0].strip() if forwarded else (request.remote or "")
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return candidate


def bootstrap():
    users = _load_json(USERS_FILE, [])
    if not isinstance(users, list):
        users = []
    found = next((u for u in users if u.get("username") == DEFAULT_ADMIN_USERNAME and u.get("role") == "admin"), None)
    if not found:
        users.append({
            "username": DEFAULT_ADMIN_USERNAME,
            "password_hash": password_hash(DEFAULT_ADMIN_PASSWORD),
            "role": "admin", "access_type": "admin", "created_at": int(time.time()),
            "expires_at": 0, "banned": False, "auth_version": 1
        })
        _save_json(USERS_FILE, users)
    else:
        found.setdefault("auth_version", 1)
        if not found.get("password_hash"):
            found["password_hash"] = password_hash(DEFAULT_ADMIN_PASSWORD)
            found.pop("password", None)
        _save_json(USERS_FILE, users)
    for path, default in [
        (ADMIN_IPS_FILE, {"allowed_ips": []}),
        (BLOCKED_IPS_FILE, {"blocked_ips": []}),
        (MAINTENANCE_FILE, {"enabled": False, "started_at": 0, "total_seconds": 0}),
        (AUDIT_FILE, {"events": []})
    ]:
        value = _load_json(path, default)
        if not isinstance(value, dict): value = default
        _save_json(path, value)
    return users


def _encode(payload):
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    body = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    sig = hmac.new(_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
    return body + "." + sig


def _decode(value):
    try:
        body, sig = value.split(".", 1)
        expected = hmac.new(_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected): return None
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode())
        return payload if int(payload.get("exp", 0)) >= int(time.time()) else None
    except Exception:
        return None


def _csrf_token():
    payload = f"{int(time.time()) // 1800}"
    sig = hmac.new(_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    return payload + "." + sig


def _check_csrf(token):
    try:
        body, sig = token.split(".", 1)
        good = hmac.compare_digest(sig, hmac.new(_secret().encode(), body.encode(), hashlib.sha256).hexdigest())
        return good and abs(int(time.time()) - int(body) * 1800) <= 3600
    except Exception:
        return False


def _login_locked(ip):
    item = _failed_logins.get(ip, {"count": 0, "until": 0})
    return item.get("until", 0) > time.time()


def _record_failed(ip):
    item = _failed_logins.get(ip, {"count": 0, "until": 0})
    item["count"] += 1
    if item["count"] >= 5:
        item["until"] = time.time() + 300
        item["count"] = 0
    _failed_logins[ip] = item


def blocked_ips(): return _load_json(BLOCKED_IPS_FILE, {"blocked_ips": []})
def save_blocked_ips(value): _save_json(BLOCKED_IPS_FILE, value)
def is_ip_blocked(ip): return False  # No IP-based access gate by design.
def enforce_ip_access(request): return None


def maintenance_state():
    state = _load_json(MAINTENANCE_FILE, {"enabled": False, "started_at": 0, "total_seconds": 0})
    if not isinstance(state, dict): state = {"enabled": False, "started_at": 0, "total_seconds": 0}
    return state


def maintenance_enabled(): return bool(maintenance_state().get("enabled"))


def effective_expires_at(user):
    exp = int(user.get("expires_at") or 0)
    if exp and maintenance_enabled():
        state = maintenance_state()
        exp += max(0, int(time.time()) - int(state.get("started_at") or int(time.time())))
    return exp


def set_maintenance(enabled):
    state = maintenance_state()
    now = int(time.time())
    enabled = bool(enabled)
    if enabled and not state.get("enabled"):
        state["enabled"] = True
        state["started_at"] = now
    elif not enabled and state.get("enabled"):
        elapsed = max(0, now - int(state.get("started_at") or now))
        state["total_seconds"] = int(state.get("total_seconds") or 0) + elapsed
        state["enabled"] = False
        state["started_at"] = 0
        # Freeze all purchased access time during maintenance.
        arr = users()
        for u in arr:
            if int(u.get("expires_at") or 0) > 0:
                u["expires_at"] = int(u["expires_at"]) + elapsed
        save_users(arr)
    _save_json(MAINTENANCE_FILE, state)
    return state


def current_user(request):
    enforce_ip_access(request)
    payload = _decode(request.cookies.get(SESSION_COOKIE, ""))
    if not payload:
        return None
    user = next((u for u in users() if u.get("username") == payload.get("username")), None)
    if not user or user.get("banned"):
        return None
    if int(payload.get("auth_version", 0)) != int(user.get("auth_version", 1)):
        return None
    if payload.get("ua") != _ua_hash(request):
        return None
    expires = effective_expires_at(user)
    return None if expires and expires < int(time.time()) else user


def require_user(request):
    user = current_user(request)
    if not user:
        raise web.HTTPUnauthorized(text=json.dumps({"status":"error","error":"Login required"}), content_type="application/json")
    return user


def require_admin(request):
    user = require_user(request)
    if user.get("role") != "admin":
        raise web.HTTPForbidden(text="Access denied.")
    return user


def login_response(username, redirect="/", request=None):
    user = next((u for u in users() if u.get("username") == username), None)
    role = user.get("role") if user else "user"
    ttl = 12 * 3600 if role == "admin" else 7 * 86400
    resp = web.HTTPFound(redirect)
    payload = {
        "sid": secrets.token_urlsafe(24),
        "username": username, "role": role,
        "auth_version": int((user or {}).get("auth_version", 1)),
        "ua": _ua_hash(request) if request else "",
        "iat": int(time.time()), "exp": int(time.time()) + ttl
    }
    secure = bool(request and request.headers.get("X-Forwarded-Proto", "http").split(",")[0].strip() == "https")
    resp.set_cookie(SESSION_COOKIE, _encode(payload), httponly=True, samesite="Strict", secure=secure, max_age=ttl, path="/")
    return resp


def logout_response():
    resp = web.HTTPFound("/login")
    resp.del_cookie(SESSION_COOKIE, path="/")
    return resp


def users(): return _load_json(USERS_FILE, [])
def save_users(value): _save_json(USERS_FILE, value)
def admin_ips(): return _load_json(ADMIN_IPS_FILE, {"allowed_ips": []})
def save_admin_ips(value): _save_json(ADMIN_IPS_FILE, value)

def _ua_hash(request):
    return hashlib.sha256((request.headers.get("User-Agent", "")[:500]).encode()).hexdigest()

def audit_event(request, event, username="", detail=""):
    data = _load_json(AUDIT_FILE, {"events": []})
    events = data.get("events", []) if isinstance(data, dict) else []
    events.append({"time": int(time.time()), "event": str(event), "username": str(username), "ip": client_ip(request), "detail": str(detail)[:500]})
    data = {"events": events[-500:]}
    _save_json(AUDIT_FILE, data)

def users(): return _load_json(USERS_FILE, [])
def save_users(value): _save_json(USERS_FILE, value)
def admin_ips(): return _load_json(ADMIN_IPS_FILE, {"allowed_ips": []})
def save_admin_ips(value): _save_json(ADMIN_IPS_FILE, value)


def _ua_hash(request): return hashlib.sha256((request.headers.get("User-Agent", "")[:500]).encode()).hexdigest()



bootstrap()
