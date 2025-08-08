#!/usr/bin/env python3
"""
role-attack-surf.py — enumerate RBAC attack surface at a given scope.

Requires: Azure CLI (`az`) logged in and authorized for the scope.
"""

import argparse, json, re, subprocess, sys
from collections import defaultdict

INTERESTING_ACTIONS = {
    # Key Vault mgmt-plane (policy edits; vault writes)
    r"^Microsoft\.KeyVault/vaults/accessPolicies/write$": "KV access policy write → can grant data-plane perms (set-policy).",
    r"^Microsoft\.KeyVault/vaults/write$": "KV vault write → often implies policy edits / config changes.",
    # Role/Assignment manipulation (RBAC escalation)
    r"^Microsoft\.Authorization/roleAssignments/write$": "Write role assignments → assign yourself higher perms.",
    r"^Microsoft\.Authorization/roleDefinitions/write$": "Write role definitions → craft a custom escalator role.",
    # Managed Identity pivot
    r"^Microsoft\.ManagedIdentity/userAssignedIdentities/assign/action$": "Assign UAI → run workloads with new identity.",
    # Automation / Run command / Script runners (code exec on infra)
    r"^Microsoft\.Automation/automationAccounts/*": "Automation powers (runbooks) → potential code execution.",
    r"^Microsoft\.Compute/virtualMachines/runCommand/action$": "VM runCommand → remote code execution on VM.",
    r"^Microsoft\.Web/sites/write$": "App Service write → deploy code/modify app settings.",
    # Storage account keys (data exfil / SAS minting)
    r"^Microsoft\.Storage/storageAccounts/listKeys/action$": "List storage keys → full data access to that account.",
    # Key Vault data-plane (if RBAC mode enabled on a vault)
    r"^Microsoft\.KeyVault/vaults/secrets/read$": "Mgmt read (metadata) of secrets; not the value but useful recon.",
    r"^Microsoft\.KeyVault/vaults/keys/read$": "Mgmt read (metadata) of keys.",
    # Broad wildcards
    r"^\*$": "Wildcard: full control at this scope."
}

INTERESTING_DATAACTIONS = {
    # These only apply when a resource uses RBAC-for-data (e.g., KV with enableRbacAuthorization true)
    r"^Microsoft\.KeyVault/vaults/secrets/read$": "KV secret read (data-plane under RBAC mode).",
    r"^Microsoft\.KeyVault/vaults/keys/decrypt/action$": "KV key decrypt (data-plane) → server-side decrypt.",
    r"^Microsoft\.KeyVault/vaults/keys/unwrapKey/action$": "KV unwrapKey (data-plane) → recover DEKs.",
    r"^Microsoft\.Storage/storageAccounts/blobServices/containers/blobs/read$": "Blob read via RBAC data actions.",
    r"^Microsoft\.Storage/storageAccounts/listKeys/action$": "List storage keys (again, data-plane-ish power)."
}

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print(p.stderr.strip(), file=sys.stderr)
        sys.exit(p.returncode)
    return p.stdout

def get_assignments(scope, assignee=None):
    cmd = ["az", "role", "assignment", "list", "--scope", scope, "-o", "json"]
    if assignee:
        cmd += ["--assignee", assignee]
    out = run(cmd)
    return json.loads(out)

def get_role_definition_by_id(role_def_id: str):
    # role_def_id ends with .../roleDefinitions/<GUID>
    rid = role_def_id.split("/")[-1]
    out = run(["az", "role", "definition", "list", "--name", rid, "-o", "json"])
    arr = json.loads(out)
    return arr[0] if arr else None

def match_interest(items, rules):
    hits = []
    for i in items:
        for pat, why in rules.items():
            if re.match(pat, i, flags=re.IGNORECASE):
                hits.append((i, why))
                break
    return hits

def analyze_permissions(role_def: dict):
    perms = role_def.get("permissions", []) or []
    findings = []
    for p in perms:
        actions = p.get("actions", []) or []
        not_actions = p.get("notActions", []) or []
        data_actions = p.get("dataActions", []) or []
        not_data = p.get("notDataActions", []) or []

        # Filter explicit actions (minus notActions)
        eff_actions = [a for a in actions if a not in not_actions]
        eff_data = [a for a in data_actions if a not in not_data]

        action_hits = match_interest(eff_actions, INTERESTING_ACTIONS)
        data_hits = match_interest(eff_data, INTERESTING_DATAACTIONS)

        findings.append({
            "actions": eff_actions,
            "dataActions": eff_data,
            "interestingActions": action_hits,
            "interestingDataActions": data_hits
        })
    return findings

def summarize_findings(findings):
    summary = []
    for f in findings:
        for a, why in f["interestingActions"]:
            summary.append(("Action", a, why))
        for a, why in f["interestingDataActions"]:
            summary.append(("DataAction", a, why))
    return summary

def suggest_exploits(summary, scope):
    tips = []
    acts = [x[1] for x in summary]
    # Key Vault policy edit
    if any(re.match(r"^Microsoft\.KeyVault/vaults/accessPolicies/write$", a, re.I) for a in acts):
        tips.append(f"KV policy write at this scope → if vault not in RBAC mode, run:\n"
                    f"  az keyvault set-policy --name <vault> --spn <spn-or-appId> --secret-permissions get list")
    # Role assignment write
    if any(re.match(r"^Microsoft\.Authorization/roleAssignments/write$", a, re.I) for a in acts):
        tips.append("Can write role assignments → try self-assign at this scope:\n"
                    "  az role assignment create --assignee <me> --role Contributor --scope " + scope)
    # Storage keys
    if any(re.match(r"^Microsoft\.Storage/storageAccounts/listKeys/action$", a, re.I) for a in acts):
        tips.append("List storage keys → enumerate accounts and pull keys:\n"
                    "  az storage account list -o table\n"
                    "  az storage account keys list -g <rg> -n <acct>")
    # VM runCommand
    if any(re.match(r"^Microsoft\.Compute/virtualMachines/runCommand/action$", a, re.I) for a in acts):
        tips.append("VM runCommand present → code exec on VMs:\n"
                    "  az vm run-command invoke -g <rg> -n <vm> --command-id RunShellScript --scripts 'id'")

    return tips

def main():
    ap = argparse.ArgumentParser(description="Enumerate RBAC attack surface (role assignments + definitions) at a scope.")
    ap.add_argument("--scope", required=True,
                    help="ARM scope, e.g., /subscriptions/<sub>, or /subscriptions/<sub>/resourceGroups/<rg>, "
                         "or full resource scope like a specific Key Vault.")
    ap.add_argument("--assignee", help="Object ID, SPN (appId), or UPN/email. If omitted, shows all principals at scope.")
    ap.add_argument("--json", action="store_true", help="Emit JSON with full details.")
    args = ap.parse_args()

    assigns = get_assignments(args.scope, assignee=args.assignee)
    if not assigns:
        print("[!] No role assignments found at this scope (for this assignee, if specified).")
        sys.exit(0)

    report = []
    print(f"[+] Role assignments at scope:\n    {args.scope}\n")
    by_role = defaultdict(list)

    for a in assigns:
        role_def_id = a["roleDefinitionId"]
        principal = a.get("principalId")
        principal_name = a.get("principalName") or principal
        role_def = get_role_definition_by_id(role_def_id)
        if not role_def:  # shouldn’t happen, but shrug
            continue

        role_name = role_def["roleName"]
        findings = analyze_permissions(role_def)
        summary = summarize_findings(findings)

        by_role[role_name].append({
            "principalId": principal,
            "principalName": principal_name,
            "findings": summary,
            "roleDefinitionId": role_def_id
        })

        report.append({
            "principalId": principal,
            "principalName": principal_name,
            "roleName": role_name,
            "roleDefinitionId": role_def_id,
            "scope": a.get("scope"),
            "findings": summary,
            "rawPermissions": role_def.get("permissions", [])
        })

    # Human-readable
    for role_name, entries in by_role.items():
        print(f"== Role: {role_name} ==")
        for e in entries:
            print(f"  Principal: {e['principalName']} ({e['principalId']})")
            if e["findings"]:
                for kind, action, why in e["findings"]:
                    print(f"    - {kind}: {action}")
                    print(f"      → {why}")
            else:
                print("    - (no flagged actions; review raw permissions if curious)")
        print()

    # Suggestions (only if single scope)
    # Collate all summaries
    all_summary = []
    for e in report:
        all_summary.extend(e["findings"])
    tips = suggest_exploits(all_summary, args.scope)
    if tips:
        print("== Suggested pivots ==")
        for t in tips:
            print(t, "\n")

    if args.json:
        print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
