#!/usr/bin/env python3
import argparse, base64, json, subprocess, sys

ALGOS = ["RSA-OAEP-256", "RSA-OAEP", "RSA1_5"]

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip())
    return p.stdout.strip()

def kv_decrypt(key_id, b64_cipher, algo):
    # az expects the value as base64; most labs give base64 already.
    out = run([
        "az","keyvault","key","decrypt",
        "--id", key_id,
        "--algorithm", algo,
        "--value", b64_cipher,
        "-o","json"
    ])
    j = json.loads(out)
    return j["result"]  # base64 of plaintext

def main():
    ap = argparse.ArgumentParser(description="Try RSA decrypt with common algorithms via Azure Key Vault")
    ap.add_argument("--key-id", required=True, help="KV key ID (e.g., https://<vault>.vault.azure.net/keys/<name>/<version>)")
    ap.add_argument("--ciphertext-b64", required=True, help="Ciphertext (base64)")
    ap.add_argument("--algo", choices=ALGOS, help="Specific algorithm; if omitted, tries all")
    args = ap.parse_args()

    algos = [args.algo] if args.algo else ALGOS
    for a in algos:
        try:
            pt_b64 = kv_decrypt(args.key_id, args.ciphertext_b64, a)
            pt = base64.b64decode(pt_b64)
            print(f"[+] Success with {a}: {pt.decode(errors='ignore')}")
            sys.exit(0)
        except Exception as e:
            print(f"[-] {a} failed: {e}")

    print("[!] No algorithm worked. Check key permissions, key type, ciphertext, or base64 formatting.")
    sys.exit(2)

if __name__ == "__main__":
    main()
