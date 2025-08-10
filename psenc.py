#!/usr/bin/env python3
# psenc.py — make PowerShell -EncodedCommand payloads

import sys, argparse, base64, pathlib

def encode_ps(command: str) -> str:
    # PowerShell expects UTF-16LE, then Base64
    data = command.encode("utf-16le")
    return base64.b64encode(data).decode()

def main():
    p = argparse.ArgumentParser(description="Generate PowerShell -EncodedCommand strings")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("-c", "--command", help="PowerShell command to encode (quote it)")
    g.add_argument("-f", "--file", type=pathlib.Path, help="Read command from file")
    g.add_argument("--stdin", action="store_true", help="Read command from STDIN")
    p.add_argument("--print-example", action="store_true", help="Show full powershell invocation")
    args = p.parse_args()

    if args.command:
        cmd = args.command
    elif args.file:
        cmd = args.file.read_text(encoding="utf-8")
    else:
        cmd = sys.stdin.read()

    encoded = encode_ps(cmd)
    print(encoded)

    if args.print_example:
        print("\n# Example run on target:")
        print(f"powershell -EncodedCommand {encoded}")

if __name__ == "__main__":
    main()
