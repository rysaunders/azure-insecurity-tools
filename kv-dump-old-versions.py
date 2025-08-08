#!/usr/bin/env python3
import subprocess
import json
import argparse

def run_az(cmd):
    """Run an Azure CLI command and return parsed JSON output."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[!] Error running: {' '.join(cmd)}")
        print(result.stderr)
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.stdout.strip()

def get_vaults(subscription_id=None):
    cmd = ["az", "keyvault", "list", "-o", "json"]
    if subscription_id:
        cmd.extend(["--subscription", subscription_id])
    return run_az(cmd) or []

def get_secrets(vault_name):
    return run_az(["az", "keyvault", "secret", "list", "--vault-name", vault_name, "-o", "json"]) or []

def get_secret_versions(vault_name, secret_name):
    return run_az(["az", "keyvault", "secret", "list-versions", "--vault-name", vault_name, "--name", secret_name, "-o", "json"]) or []

def get_secret_value(vault_name, secret_name, version=None):
    cmd = ["az", "keyvault", "secret", "show", "--vault-name", vault_name, "--name", secret_name, "-o", "json"]
    if version:
        cmd.extend(["--version", version])
    return run_az(cmd)

def main():
    parser = argparse.ArgumentParser(description="Enumerate old Key Vault secret versions and dump values.")
    parser.add_argument("--subscription-id", help="Azure Subscription ID")
    parser.add_argument("--vault", help="Specific Key Vault name to target")
    parser.add_argument("--output", choices=["table", "json"], default="table", help="Output format")
    args = parser.parse_args()

    vaults = [{"name": args.vault}] if args.vault else get_vaults(args.subscription_id)

    results = []
    for vault in vaults:
        vault_name = vault["name"] if isinstance(vault, dict) else vault
        print(f"\n[+] Vault: {vault_name}")
        secrets = get_secrets(vault_name)
        for secret in secrets:
            secret_name = secret["name"]
            print(f"    [*] Secret: {secret_name}")
            versions = get_secret_versions(vault_name, secret_name)
            latest_version = versions[-1]["id"].split("/")[-1] if versions else None
            for v in versions:
                version_id = v["id"].split("/")[-1]
                val = get_secret_value(vault_name, secret_name, version_id)
                if not val:
                    continue
                entry = {
                    "vault": vault_name,
                    "secret": secret_name,
                    "version": version_id,
                    "value": val.get("value", ""),
                    "is_latest": version_id == latest_version
                }
                results.append(entry)
                print(f"        - Version: {version_id} | Latest: {entry['is_latest']} | Value: {entry['value'][:50]}...")

    if args.output == "json":
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
