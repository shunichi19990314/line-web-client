#!/usr/bin/env python3
"""
Fetch the official LINE Chrome extension and patch it so it can run as a normal website.
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
    resp = requests.get(CRX_URL, headers=headers, allow_redirects=True, timeout=60)
    resp.raise_for_status()
    return resp.content


def extract_crx(crx_data: bytes, dest: str):
    """CRX3 format: skip the header and treat the rest as a ZIP."""
    if crx_data[:4] != b"Cr24":
        raise ValueError("Not a valid CRX file")

    # CRX3 header length is at offset 8 (little-endian uint32)
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
    """Apply the necessary patches so the extension works as a website."""
    main_js = os.path.join(WWW_DIR, "static", "js", "main.js")
    ltsm_js = os.path.join(WWW_DIR, "static", "js", "ltsmSandbox.js")

    files_to_patch = []
    if os.path.exists(main_js):
        files_to_patch.append(main_js)
    if os.path.exists(ltsm_js):
        files_to_patch.append(ltsm_js)

    if not files_to_patch:
        # Sometimes the path is different depending on version
        for root, _, files in os.walk(WWW_DIR):
            for f in files:
                if f in ("main.js", "ltsmSandbox.js") or f.endswith(".js"):
                    full = os.path.join(root, f)
                    # Only patch large JS files that look like the main bundle
                    if os.path.getsize(full) > 100_000:
                        files_to_patch.append(full)

    if not files_to_patch:
        print("Warning: Could not find main.js / ltsmSandbox.js to patch.")
        print("Please check the extracted structure under ./www/")
        return

    # Origin patches (make the code think it is still running inside the extension)
    origin_patterns = [
        (r"window\.origin", r'"chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc"'),
        (r"window\.location\.origin", r'"chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc"'),
        (r"(?<![.\w])location\.origin", r'"chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc"'),
    ]

    # CORS / endpoint patches → route through our proxy
    cors_patterns = [
        (r'"https://ci\.line-apps\.com/R4"', r"`${location.origin}/_proxy/R4`"),
        (r"'https://ci\.line-apps\.com/R4'", r"`${location.origin}/_proxy/R4`"),
        (r'"line-chrome-gw\.line-apps\.com"', r"`${location.host}/_proxy/CHROME_GW`"),
        (r"'line-chrome-gw\.line-apps\.com'", r"`${location.host}/_proxy/CHROME_GW`"),
        (r'"https://line-chrome-gw\.line-apps\.com"', r"`${location.origin}/_proxy/CHROME_GW`"),
        (r"'https://line-chrome-gw\.line-apps\.com'", r"`${location.origin}/_proxy/CHROME_GW`"),
    ]

    for path in files_to_patch:
        print(f"Patching {path} ...")
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        original = content
        for pattern, repl in origin_patterns + cors_patterns:
            content = re.sub(pattern, repl, content)

        if content != original:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  → patched successfully")
        else:
            print(f"  → no changes (patterns may already be applied or different in this version)")


def main():
    print("=" * 60)
    print("LINE Chrome Extension → Web Client converter")
    print("=" * 60)

    crx = download_crx()
    extract_crx(crx, WWW_DIR)
    patch_files()

    print()
    print("Done!")
    print("Next steps:")
    print("  1. npm install")
    print("  2. npm start          # local test → http://localhost:3000")
    print("  3. Push to GitHub and deploy to Render")
    print()


if __name__ == "__main__":
    main()
