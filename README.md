# 🔓 azure-insecurity-tools

**A growing collection of offensive Azure tools and scripts** designed to support cloud red teaming, lab work, and deep exploration of Microsoft cloud internals.

---

## 📦 What's Inside

This repo will evolve as I learn more about attacking Azure. The focus is hands-on, practical tooling for real-world and lab scenarios.

### ✅ Initial Tool: `token_multiplexer.py`

Use a single `refresh_token` to mint multiple `access_token`s across different Azure resource scopes (Graph, Key Vault, ARM, etc).

#### Features
- Exchanges refresh tokens for any `.default` scoped resource
- Decodes JWT and extracts `aud`, `scp`, and `exp` claims
- Built as a CLI for flexible reuse
- Useful in phishing/OAuth abuse scenarios like AzRTE labs

#### Example Usage

```bash
python token_multiplexer.py \
  --refresh-token "<paste_here>" \
  --client-id "your-app-client-id" \
  --client-secret "your-app-client-secret" \
  --scope "https://vault.azure.net/.default"
```

### 🔑 kv-dump-old-versions.py — Enumerate and Dump Azure Key Vault Secret Versions

This script enumerates secrets in Azure Key Vaults and retrieves all available versions, including old values that might remain after rotation.

Features
-	Works on a single vault or all vaults in a subscription.
-	Dumps all secret versions with flags for which one is latest.
-	Supports table view (human-friendly) and JSON output (machine-friendly).
-	Flags old values that differ from the latest version.

#### Usage
```bash
# Enumerate all vaults in a subscription
python3 kv-dump-old-versions.py --subscription-id <subscription-id>

# Target a specific vault and output as JSON
python3 kv-dump-old-versions.py --vault kv-1-2e693029 --output json
```

### 🔢 kv-rsa-decrypt.py
Tries common RSA algs against a given Key Vault key ID. Uses az under the hood to leverage existing logon.

#### Usage
```bash
python3 kv-rsa-decrypt.py \
  --key-id "https://kv-2-xxxx.vault.azure.net/keys/key-2-xxxx/<version>" \
  --ciphertext-b64 "G067ensX6Zgz...=="  # full base64 blob
# or force a specific algo:
python3 kv-rsa-decrypt.py --key-id ... --ciphertext-b64 ... --algo RSA-OAEP
```

### 🗑️ kv-recover-deleted.py
List+recover deleted secrets for a vault

#### Usage
```bash
python3 kv-recover-deleted.py --vault kv-3-2e693029
python3 kv-recover-deleted.py --vault kv-3-2e693029 --recover-all
```

### 🔍 role-attack-surf.py
-	Lists your role assignments at a given scope (vault/RG/subscription)
-	Pulls each role definition
-	Flags interesting Actions/DataActions (stuff that tends to be abusable)
-	Prints a summary + optional JSON
-	Suggests quick exploits (e.g., set-policy when it sees accessPolicies/write)

#### Usage
```bash
# At a vault scope (like your lab)
python3 role-attack-surf.py \
  --scope "/subscriptions/<sub>/resourceGroups/key-vault-labs/providers/Microsoft.KeyVault/vaults/<vault>""

# Filter to your SP only (faster to read)
python3 role-attack-surf.py \
  --scope "/subscriptions/<sub>/resourceGroups/key-vault-labs/providers/Microsoft.KeyVault/vaults/<vault>" \
  --assignee <client_id>

# Dump full JSON too
python3 role-attack-surf.py --scope "/subscriptions/<sub>" --json
```

### ﹟psenc.py
Output Powershell-read -EncodedCommand string given a file, command, or stdin

#### Usage
```bash
# direct command
python3 psenc.py -c 'Write-Host "Hello from Mac!"' --print-example

# from a file
python3 psenc.py -f payload.ps1 > encoded.txt

# from stdin (handy in pipelines)
echo '$PSVersionTable.PSVersion' | python3 psenc.py --stdin
```

⚠️ Disclaimer

For educational and lab use only.

Do not use these tools without explicit permission. They are intended to support self-hosted labs, CTF environments, and ethical security testing.
