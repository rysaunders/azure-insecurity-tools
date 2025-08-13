#!/usr/bin/env bash
set -euo pipefail

# az-vars.sh — print export statements for Azure resource JSON
# Requires: jq

INDEX=""
NAME=""
RUN_CMD=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --index) INDEX="$2"; shift 2;;
    --name)  NAME="$2";  shift 2;;
    --run)   RUN_CMD="$2"; shift 2;;
    -h|--help)
      cat <<'H'
Usage: az-vars.sh [--index N | --name NAME] [--run 'az ... -o json']
  - read JSON from stdin, or run the provided command
  - prints: export VAR='value' lines
Examples:
  eval "$(az postgres flexible-server list -o json | az-vars.sh)"
  eval "$(az-vars.sh --run 'az postgres flexible-server list -o json')"
  eval "$(az postgres flexible-server list -o json | az-vars.sh --name myserver)"
H
      exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 1;;
  esac
done

json_input() {
  if [[ -n "$RUN_CMD" ]]; then
    eval "$RUN_CMD"
  else
    cat
  fi
}

# Read JSON
RAW="$(json_input)"

# If it's an array, select by --name or --index (default 0)
select_from_array() {
  local arr="$1"
  if jq -e 'type=="array"' >/dev/null 2>&1 <<<"$arr"; then
    if [[ -n "$NAME" ]]; then
      jq -c --arg n "$NAME" '
        .[] | select((.name//.properties.name//"") == $n) // empty
      ' <<<"$arr" | head -n1
    elif [[ -n "$INDEX" ]]; then
      jq -c --argjson i "$INDEX" '.[ $i ]' <<<"$arr"
    else
      jq -c '.[0]' <<<"$arr"
    fi
  else
    jq -c '.' <<<"$arr"
  fi
}

OBJ="$(select_from_array "$RAW")"
if [[ -z "$OBJ" || "$OBJ" == "null" ]]; then
  echo "# No object selected (empty result / wrong --name/--index)." >&2
  exit 1
fi

# Helpers
esc() { # single-quote safe
  local s="$1"
  printf "%s" "$s" | sed "s/'/'\\\\''/g"
}

emit() {
  local k="$1" v="$2"
  [[ -z "$v" || "$v" == "null" ]] && return 0
  echo "export $k='$(esc "$v")'"
}

# Generic fields
RID="$(jq -r '.id // empty' <<<"$OBJ")"
TYPE="$(jq -r '.type // empty' <<<"$OBJ")"
NAME_FIELD="$(jq -r '.name // empty' <<<"$OBJ")"
LOC="$(jq -r '.location // .properties.location // empty' <<<"$OBJ")"

# Parse subscription & RG from id if present
SUB=""; RG=""
if [[ -n "$RID" ]]; then
  # /subscriptions/<sub>/resourceGroups/<rg>/providers/...
  SUB="$(jq -r '(.id|split("/"))[2] // empty' <<<"$OBJ")"
  RG="$(jq -r  '(.id|split("/"))[4] // empty' <<<"$OBJ")"
fi

echo "# Context: ${TYPE:-unknown}"
emit AZ_RESOURCE_ID "$RID"
emit AZ_RESOURCE_TYPE "$TYPE"
emit AZ_RESOURCE_NAME "$NAME_FIELD"
emit AZ_LOCATION "$LOC"
emit AZ_SUBSCRIPTION_ID "$SUB"
emit AZ_RESOURCE_GROUP "$RG"

# Service-specific enrichments
case "$TYPE" in
  Microsoft.DBforPostgreSQL/flexibleServers)
    PG_ADMIN="$(jq -r '.administratorLogin // empty' <<<"$OBJ")"
    PG_FQDN="$(jq -r '.fullyQualifiedDomainName // empty' <<<"$OBJ")"
    PG_VERSION="$(jq -r '.version // .minorVersion // empty' <<<"$OBJ")"
    emit PG_SERVER "$NAME_FIELD"
    emit PG_ADMIN "$PG_ADMIN"
    emit PG_FQDN "$PG_FQDN"
    emit PG_VERSION "$PG_VERSION"
    ;;

  Microsoft.Compute/virtualMachines)
    VM_SIZE="$(jq -r '.properties.hardwareProfile.vmSize // empty' <<<"$OBJ")"
    VM_OS="$(jq -r '.properties.storageProfile.osDisk.osType // empty' <<<"$OBJ")"
    emit VM_NAME "$NAME_FIELD"
    emit VM_SIZE "$VM_SIZE"
    emit VM_OS   "$VM_OS"
    ;;

  Microsoft.Storage/storageAccounts)
    SA_KIND="$(jq -r '.kind // empty' <<<"$OBJ")"
    SA_SKU="$(jq -r '.sku.name // empty' <<<"$OBJ")"
    emit SA_NAME "$NAME_FIELD"
    emit SA_KIND "$SA_KIND"
    emit SA_SKU  "$SA_SKU"
    ;;

  Microsoft.KeyVault/vaults)
    KV_URI="$(jq -r '.properties.vaultUri // empty' <<<"$OBJ")"
    emit KV_NAME "$NAME_FIELD"
    emit KV_URI  "$KV_URI"
    ;;

  # add more types here as you encounter them…
esac
