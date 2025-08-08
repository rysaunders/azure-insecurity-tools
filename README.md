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

⚠️ Disclaimer

For educational and lab use only.

Do not use these tools without explicit permission. They are intended to support self-hosted labs, CTF environments, and ethical security testing.
