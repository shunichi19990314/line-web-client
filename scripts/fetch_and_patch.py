#!/usr/bin/env python3
"""
Download official LINE Chrome extension and patch it for web deployment.

Critical for QR login:
  - HMAC signs (path + body). Path must stay /api/... not /_proxy/...
  - R4 config must go through same-origin /R4 (not direct ci.line-apps.com)
  - After qrCodeLoginV2, access token must be set BEFORE processAfterLogin's getProfile
  - LTSM sandbox trmInit must accept web origin (not only chrome-extension://)
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

    import json as _json

    man = os.path.join(dest, "manifest.json")
    if os.path.exists(man):
        try:
            with open(man, encoding="utf-8") as f:
                ver = _json.load(f).get("version", "")
            if ver:
                with open(os.path.join(dest, ".line_chrome_version"), "w") as f:
                    f.write(ver.strip())
                print(f"  extension version: {ver}")
        except Exception as e:
            print(f"  (version read skipped: {e})")


def patch_post_login_token(content: str) -> tuple[str, bool]:
    """Set access token in memory BEFORE processAfterLogin calls getProfile."""
    old = (
        "_T=async(e,t)=>{try{const{dispatch:n}=IA;"
        "n(Eg.setLoginState(md.LOG_IN_PROGRESSING));"
        "const r=await pj"
    )
    new = (
        "_T=async(e,t)=>{try{const{dispatch:n}=IA;"
        "e&&rT().setTokenV3IssueResult(e);"
        "n(Eg.setLoginState(md.LOG_IN_PROGRESSING));"
        "const r=await pj"
    )
    if old not in content:
        print("  WARN: processAfterLogin token patch pattern not found")
        return content, False
    return content.replace(old, new, 1), True


def patch_trm_init_origin(content: str) -> tuple[str, int]:
    """Allow trmInit postMessage from web origin (real origin cannot be spoofed)."""
    old = (
        'e.origin==="chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc"'
        '&&"trmInit"===e.data'
    )
    # Accept extension origin OR same web page origin
    new = (
        '(e.origin===location.origin||e.origin==='
        '"chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc")'
        '&&"trmInit"===e.data'
    )
    count = content.count(old)
    if count:
        content = content.replace(old, new)
    return content, count


def patch_files():
    files = []
    for root, _, names in os.walk(WWW_DIR):
        for name in names:
            if not name.endswith((".js", ".mjs", ".html")):
                continue
            path = os.path.join(root, name)
            if name in (
                "main.js",
                "ltsmSandbox.js",
                "ltsmSandbox.html",
                "background.js",
            ) or os.path.getsize(path) > 40_000:
                files.append(path)

    if not files:
        print("WARNING: no JS to patch")
        return

    origin_repls = [
        (r"window\.origin", '"chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc"'),
        (r"window\.location\.origin", '"chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc"'),
        (r"(?<![.\w$`])location\.origin(?!\s*\})", '"chrome-extension://ophjlpahpchlmihnnnihgmmeilfjmjjc"'),
    ]

    r4_hosts = [
        "ci.line-apps.com",
        "cix.line-apps.com",
        "ci-beta.line-apps-beta.com",
        "ci-beta2.line-apps-beta.com",
        "ci-beta3.line-apps-beta.com",
        "ci-rc.line-apps-rc.com",
        "ci-rc2.line-apps-rc.com",
        "ci-rc3.line-apps-rc.com",
        "cix-beta.line-apps-beta.com",
        "cix-beta2.line-apps-beta.com",
        "cix-beta3.line-apps-beta.com",
        "cix-rc.line-apps-rc.com",
        "cix-rc2.line-apps-rc.com",
        "cix-rc3.line-apps-rc.com",
    ]
    r4_repls = []
    for h in r4_hosts:
        r4_repls.append((re.escape(f'"https://{h}/R4"'), "`${location.origin}/R4`"))
        r4_repls.append((re.escape(f"'https://{h}/R4'"), "`${location.origin}/R4`"))

    host_repls = [
        (r'"https://line-chrome-gw\.line-apps\.com"', "`${location.origin}`"),
        (r"'https://line-chrome-gw\.line-apps\.com'", "`${location.origin}`"),
        (r'"https://obs\.line-apps\.com"', "`${location.origin}`"),
        (r"'https://obs\.line-apps\.com'", "`${location.origin}`"),
        (r'"https://uts-front\.line-apps\.com"', "`${location.origin}`"),
        (r"'https://uts-front\.line-apps\.com'", "`${location.origin}`"),
        (r'"line-chrome-gw\.line-apps\.com"', "location.host"),
        (r"'line-chrome-gw\.line-apps\.com'", "location.host"),
        (r'"obs\.line-apps\.com"', "location.host"),
        (r"'obs\.line-apps\.com'", "location.host"),
    ]

    for path in files:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        original = content
        notes = []

        for pat, repl in origin_repls:
            content = re.sub(pat, repl, content)
        for pat, repl in r4_repls:
            content = re.sub(pat, repl, content)
        for pat, repl in host_repls:
            content = re.sub(pat, repl, content)

        content = re.sub(
            r'"https://ci\.line-apps\.com"(?!/)',
            "`${location.origin}`",
            content,
        )

        # Web-specific behavioral fixes (mainly main.js)
        if path.endswith("main.js") or path.endswith("ltsmSandbox.js"):
            content, trm_n = patch_trm_init_origin(content)
            if trm_n:
                notes.append(f"trmInit-origin x{trm_n}")

        if path.endswith("main.js"):
            content, ok = patch_post_login_token(content)
            if ok:
                notes.append("setToken-before-getProfile")

        if content != original:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            r4_left = len(
                re.findall(
                    r"https://ci(?:x)?(?:-[a-z0-9]+)?\.line-apps(?:-[a-z]+)?\.com/R4",
                    content,
                )
            )
            extra = (", " + ", ".join(notes)) if notes else ""
            print(f"  patched {path} (R4 left={r4_left}{extra})")
        else:
            print(f"  skip    {path}")


def main():
    print("=" * 60)
    print("LINE Chrome → Web (HMAC + R4 + post-login token fix)")
    print("=" * 60)
    crx = download_crx()
    extract_crx(crx, WWW_DIR)
    print("Patching...")
    patch_files()
    print("Done. Run: npm install && npm start")


if __name__ == "__main__":
    main()
