#!/usr/bin/env python3
"""
Download official LINE Chrome extension and patch it for web deployment.

Critical for QR login:
  - HMAC signs (path + body). Path must stay /api/... not /_proxy/...
  - Therefore we rewrite hosts to location.origin (same-origin), and the
    Node server proxies /api/* and /R4 to the real LINE hosts.
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
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    resp = requests.get(CRX_URL, headers=headers, allow_redirects=True, timeout=120)
    resp.raise_for_status()
    print(f"  size={len(resp.content)} bytes")
    return resp.content


def extract_crx(crx_data: bytes, dest: str):
    if crx_data[:4] != b"Cr24":
        raise ValueError("Not a valid CRX3 file")
    header_len = struct.unpack("<I", crx_data[8:12])[0]
    zip_data = crx_data[12 + header_len :]
    zip_path = f"{EXTENSION_ID}.zip"
    with open(zip_path, "wb") as f:
        f.write(zip_data)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest)
    os.remove(zip_path)
    print(f"Extracted -> ./{dest}/")


def patch_files():
    files = []
    for root, _, names in os.walk(WWW_DIR):
        for name in names:
            if not name.endswith((".js", ".mjs", ".html")):
                continue
            path = os.path.join(root, name)
            if name in ("main.js", "ltsmSandbox.js", "ltsmSandbox.html", "background.js") or os.path.getsize(path) > 40_000:
                files.append(path)

    if not files:
        print("WARNING: no JS to patch")
        return

    origin_repls = [
        (r"window\.origin", '"chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc"'),
        (r"window\.location\.origin", '"chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc"'),
        (r"(?<![.\w])location\.origin", '"chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc"'),
    ]

    host_repls = [
        (r'"https://line-chrome-gw\.line-apps\.com"', "`${location.origin}`"),
        (r"'https://line-chrome-gw\.line-apps\.com'", "`${location.origin}`"),
        (r'"https://ci\.line-apps\.com"', "`${location.origin}`"),
        (r"'https://ci\.line-apps\.com'", "`${location.origin}`"),
        (r'"https://obs\.line-apps\.com"', "`${location.origin}`"),
        (r"'https://obs\.line-apps\.com'", "`${location.origin}`"),
        (r'"https://uts-front\.line-apps\.com"', "`${location.origin}`"),
        (r"'https://uts-front\.line-apps\.com'", "`${location.origin}`"),
        (r'"line-chrome-gw\.line-apps\.com"', "`${location.host}`"),
        (r"'line-chrome-gw\.line-apps\.com'", "`${location.host}`"),
        (r'"ci\.line-apps\.com"', "`${location.host}`"),
        (r"'ci\.line-apps\.com'", "`${location.host}`"),
        (r'"obs\.line-apps\.com"', "`${location.host}`"),
        (r"'obs\.line-apps\.com'", "`${location.host}`"),
    ]

    for path in files:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        original = content
        for pat, repl in origin_repls + host_repls:
            content = re.sub(pat, repl, content)
        if content != original:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  patched {path}")
        else:
            print(f"  skip    {path}")


def main():
    print("=" * 60)
    print("LINE Chrome \u2192 Web (HMAC-safe path-preserving proxy)")
    print("=" * 60)
    crx = download_crx()
    extract_crx(crx, WWW_DIR)
    print("Patching...")
    patch_files()
    print("Done. Run: npm install && npm start")


if __name__ == "__main__":
    main()
