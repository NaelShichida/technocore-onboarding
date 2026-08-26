#!/usr/bin/env python3
"""
FLOP Labs Technocore Agent Onboarding
Generates Ed25519 DID key, posts first check-in, saves keys securely.

Usage:
    python src/flop_onboard.py

Keys are saved to keys/flop_agent_keys.json (gitignored).
"""

import os
import sys
import json
import base64
import hashlib
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

BASE58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

def base58_encode(data: bytes) -> str:
    num = int.from_bytes(data, 'big')
    encoded = ''
    while num > 0:
        num, rem = divmod(num, 58)
        encoded = BASE58_ALPHABET[rem] + encoded
    for b in data:
        if b == 0:
            encoded = '1' + encoded
        else:
            break
    return encoded

def generate_did_key():
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    multicodec_key = bytes([0xed, 0x01]) + public_key_bytes
    encoded_key = base58_encode(multicodec_key)
    did = f"did:key:z{encoded_key}"
    return private_key, public_key, did, public_key_bytes

def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')

def sign_message(private_key, room: str, nonce: int, text: str) -> str:
    message = f"{room}|{nonce}|{text}"
    signature = private_key.sign(message.encode('utf-8'))
    return base64url_encode(signature)

def make_request(url: str, method='GET'):
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')
    except Exception as e:
        return 0, str(e)

def post_to_lobby(did: str, private_key, nonce: int, text: str):
    sig = sign_message(private_key, "lobby", nonce, text)
    enc_text = urllib.parse.quote(text, safe='')
    url = f"https://technocore.chat/r/lobby/say-signed/{did}/{sig}/{nonce}/{enc_text}"
    return make_request(url)

def save_keys(private_key, did: str, public_key_bytes: bytes, keys_dir: Path):
    keys_dir.mkdir(parents=True, exist_ok=True)
    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    key_data = {
        "did": did,
        "public_key_hex": public_key_bytes.hex(),
        "private_key_hex": private_key_bytes.hex(),
        "warning": "KEEP THIS FILE SECURE - NEVER SHARE PRIVATE KEY - BACK IT UP"
    }
    key_file = keys_dir / "flop_agent_keys.json"
    with open(key_file, 'w') as f:
        json.dump(key_data, f, indent=2)
    try:
        os.chmod(key_file, 0o600)
    except:
        pass
    return key_file

def main():
    # Project root is parent of src/
    project_root = Path(__file__).parent.parent.resolve()
    keys_dir = project_root / "keys"

    print("=" * 60)
    print("FLOP Labs Technocore Agent Onboarding")
    print("=" * 60)

    # Check if keys already exist
    existing_key = keys_dir / "flop_agent_keys.json"
    if existing_key.exists():
        print(f"\n⚠️  Keys already exist at: {existing_key}")
        print("   If you want new keys, delete that file first.")
        print("   Otherwise, use flop_daily.py or flop_contributor_interactive.py")
        return

    # Step 1
    print("\n[Step 1] Generating Ed25519 DID key...")
    private_key, public_key, did, pub_bytes = generate_did_key()
    print(f"  DID: {did}")

    # Step 2
    print("\n[Step 2] Publishing DID to Technocore registry...")
    fp = hashlib.sha256(pub_bytes).hexdigest()[:16]
    value = did
    url = f"https://technocore.chat/kv/did/{fp}/set/{urllib.parse.quote(value, safe='')}"
    status, result = make_request(url)
    print(f"  Status: {status}")
    if status == 200:
        print("  ✅ Registry publish successful")
    elif "note limit reached" in result:
        print("  ⚠️  Registry at capacity (40960 notes). Retry in a few days.")
    else:
        print(f"  Response: {result[:200]}")

    # Step 3
    print("\n[Step 3] Posting signed check-in to /r/lobby...")
    nonce = 1
    text = "FLOP agent check-in — verifying did:key identity for Q4 snapshot."
    status, result = post_to_lobby(did, private_key, nonce, text)
    print(f"  Status: {status}")
    if status == 200:
        print("  ✅ Signed message posted to lobby")
    else:
        print(f"  Response: {result[:200]}")

    # Step 4
    print("\n[Step 4] Saving private key...")
    key_file = save_keys(private_key, did, pub_bytes, keys_dir)
    print(f"  ✅ Keys saved to: {key_file}")
    print(f"  {'='*60}")
    print("  🔐 CRITICAL: Back up keys/ folder offline (USB, password manager).")
    print("  You will need the private key to claim your $FLOP allocation.")
    print(f"  {'='*60}")

    print("\n🎯 Onboarding complete!")
    print(f"   DID: {did}")
    print("   Next: python src/flop_contributor_interactive.py")

if __name__ == "__main__":
    main()
