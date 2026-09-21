#!/usr/bin/env python3
"""
Fetch the official LINE Chrome extension and patch it so it can run as a normal website.
Improved patches for QR code login (long-polling endpoints + more hosts).
"""

import os
import re
import shutil
import struct
import sys
import zipfile

try:
    import requests
except ImportError:
    print("Please install requests: pip install requests")
    sys.exit(1)

EXTENSION_ID = "ophjlpahpchlmihnnnihgmmeilfjmjjc"
WWW_DIR = "www"
CRX_URL = (
    "https://clients2.google.com/service/update2/crx"
    f"?response=redirect&prodversion=120.0.0.0&acceptformat=crx3"
    f"&x=id%3D{EXTENSION_ID}%26installsource%3Dondemand%26uc"
)


def download_crx():
    print("Downloading official LINE Chrome extension...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    resp = requests.get(CRX_URL, headers=headers, allow_redirects=True, timeout=120)
    resp.raise_for_status()
    print(f"  downloaded {len(resp.content)} bytes")
    return resp.content


def extract_crx(crx_data: bytes, dest: str):
    """CRX3 format: skip the header and treat the rest as a ZIP."""
    if crx_data[:4] != b"Cr24":
        raise ValueError("Not a valid CRX file")

    header_len = struct.unpack("<I", crx_data[8:12])[0]
    zip_start = 12 + header_len
    zip_data = crx_data[zip_start:]

    zip_path = f"{EXTENSION_ID}.zip"
    with open(zip_path, "wb") as f:
        f.write(zip_data)

    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest)

    os.remove(zip_path)
    print(f"Extracted to ./{dest}/")


def patch_files():
    """Apply patches so the extension works as a website, including QR login."""
    candidates = []
    for root, _, files in os.walk(WWW_DIR):
        for f in files:
            if not f.endswith((".js", ".mjs")):
                continue
            full = os.path.join(root, f)
            size = os.path.getsize(full)
            if size > 50_000 or f in ("main.js", "ltsmSandbox.js", "background.js"):
                candidates.append(full)

    if not candidates:
        print("Warning: No JS files found to patch under ./www/")
        return

    origin_patterns = [
        (r"window\.origin", r'"chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc"'),
        (r"window\.location\.origin", r'"chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc"'),
        (r"(?<![.\w])location\.origin", r'"chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc"'),
    ]

    cors_patterns = [
        (r'"https://line-chrome-gw\.line-apps\.com"', r"`${location.origin}/_proxy/CHROME_GW`"),
        (r"'https://line-chrome-gw\.line-apps\.com'", r"`${location.origin}/_proxy/CHROME_GW`"),
        (r'"line-chrome-gw\.line-apps\.com"', r"`${location.host}/_proxy/CHROME_GW`"),
        (r"'line-chrome-gw\.line-apps\.com'", r"`${location.host}/_proxy/CHROME_GW`"),
        (r'"https://ci\.line-apps\.com/R4"', r"`${location.origin}/_proxy/R4`"),
        (r"'https://ci\.line-apps\.com/R4'", r"`${location.origin}/_proxy/R4`"),
        (r'"https://ci\.line-apps\.com"', r"`${location.origin}/_proxy/CI`"),
        (r"'https://ci\.line-apps\.com'", r"`${location.origin}/_proxy/CI`"),
        (r'"https://obs\.line-apps\.com"', r"`${location.origin}/_proxy/OBS`"),
        (r"'https://obs\.line-apps\.com'", r"`${location.origin}/_proxy/OBS`"),
        (r'"https://uts-front\.line-apps\.com"', r"`${location.origin}/_proxy/UTS`"),
        (r"'https://uts-front\.line-apps\.com'", r"`${location.origin}/_proxy/UTS`"),
    ]

    for path in candidates:
        print(f"Patching {path} ({os.path.getsize(path)} bytes) ...")
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        original = content
        for pattern, repl in origin_patterns + cors_patterns:
            content = re.sub(pattern, repl, content)

        if content != original:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print("  \u2192 patched")
        else:
            print("  \u2192 no matching patterns")


def main():
    print("=" * 60)
    print("LINE Chrome Extension \u2192 Web Client converter")
    print("=" * 60)

    crx = download_crx()
    extract_crx(crx, WWW_DIR)
    patch_files()

    print()
    print("Done!")
    print("Next steps:")
    print("  1. npm install")
    print("  2. npm start")
    print("  3. Open the page and try QR code login")
    print()


if __name__ == "__main__":
    main()
