#!/usr/bin/env python3
# kv-recover-deleted.py
import subprocess, json, argparse, sys

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr.strip(), file=sys.stderr)
        sys.exit(p.returncode)
    return p.stdout

def list_deleted(vault):
    out = run(["az","keyvault","secret","list-deleted","--vault-name",vault,"-o","json"])
    return json.loads(out)

def recover_secret(secret_id):
    out = run(["az","keyvault","secret","recover","--id",secret_id,"-o","json"])
    return json.loads(out)

def show_secret(secret_id):
    out = run(["az","keyvault","secret","show","--id",secret_id,"-o","json"])
    return json.loads(out)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Recover deleted secrets from an Azure Key Vault")
    ap.add_argument("--vault", required=True, help="Vault name (e.g., kv-3-xxxx)")
    ap.add_argument("--recover-all", action="store_true", help="Recover every deleted secret found")
    args = ap.parse_args()

    deleted = list_deleted(args.vault)
    if not deleted:
        print(f"[+] No deleted secrets in {args.vault}")
        sys.exit(0)

    print(f"[+] Deleted secrets in {args.vault}:")
    for s in deleted:
        sid = s["id"]
        name = s["name"]
        print(f"    - {name} ({sid})  deletedDate={s.get('deletedDate')} purgeDate={s.get('scheduledPurgeDate')}")

    if args.recover_all:
        print("\n[+] Recovering…")
        for s in deleted:
            sid = s["id"]
            r = recover_secret(sid)
            current_id = r["id"].split("/versions/")[0] if "/versions/" in r["id"] else r["id"]
            shown = show_secret(current_id)
            print(f"    - {s['name']}: {shown.get('value')[:80]}...")
