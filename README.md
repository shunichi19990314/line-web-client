# LINE Web Client (Unofficial)

公式の **LINE Chrome拡張機能** をパッチして、普通のWebサイトとして動くようにした非公式クライアントです。

> **注意**  
> これは非公式の実装です。LINEの利用規約に違反する可能性があります。  
> 自己責任で利用してください。

対応デプロイ先: **Render** / **Railway**（どちらも同じコード）

---

## 必要なもの

- Node.js 18以上
- Python 3 + `requests`（拡張機能の取得用）
  ```bash
  pip install requests
  ```

---

## セットアップ手順（ローカル）

### 1. リポジトリをクローン

```bash
git clone https://github.com/shunichi19990314/line-web-client.git
cd line-web-client
```

### 2. 公式拡張機能を取得してパッチ

```bash
python3 scripts/fetch_and_patch.py
```

これで `www/` フォルダにパッチ済みのファイルが展開されます。

### 3. 依存関係をインストール

```bash
npm install
```

### 4. ローカルで起動

```bash
npm start
```

ブラウザで http://localhost:3000 を開いてください。

---

## Railway へのデプロイ手順

1. このリポジトリを GitHub に push する（済ならそのまま）

2. [Railway](https://railway.app) にログインし、**New Project → Deploy from GitHub repo** でこのリポジトリを選ぶ

3. サービスが作成されたら、必要に応じて次を確認する

   | 項目 | 推奨 |
   |------|------|
   | **Build Command** | `pip install requests && python3 scripts/fetch_and_patch.py && npm install` |
   | **Start Command** | `npm start` |
   | **Healthcheck Path** | `/healthz` |

   リポジトリ直下の `railway.toml` / `nixpacks.toml` がある場合、上記は自動で使われます。

4. **Settings → Networking → Generate Domain** で公開 URL を発行する

5. デプロイ完了後、`https://あなたのサービス.up.railway.app` を開く

### Railway での注意

- サーバーは `0.0.0.0` と `process.env.PORT` で待受（Railway 必須）
- ビルド時に公式 CRX を取得するため、ビルド環境からインターネットに出られること
- QR ログインは長めのタイムアウト（約 210 秒）を使うため、プロキシのアイドル制限に注意
- ビルドで Python が見つからない場合は、Dashboard の Build Command を手動設定するか、`Dockerfile` でデプロイする

### Dockerfile でデプロイする場合

Railway のサービス設定で **Dockerfile** を使うと、Node + Python が揃った環境でビルドできます。

---

## Render へのデプロイ手順

1. このリポジトリを GitHub に push する

2. [Render Dashboard](https://dashboard.render.com) にログイン

3. **New → Web Service** をクリック

4. GitHub リポジトリを接続

5. 以下のように設定：

   | 項目 | 値 |
   |------|-----|
   | **Name** | `linedayo`（好きな名前） |
   | **Runtime** | `Node` |
   | **Build Command** | `pip install requests && python3 scripts/fetch_and_patch.py && npm install` |
   | **Start Command** | `npm start` |
   | **Instance Type** | `Free` |

6. **Create Web Service** をクリック

数分待つと `https://あなたのサービス名.onrender.com` で公開されます。

（任意）`render.yaml` を使った Blueprint デプロイも可能です。

---

## 仕組みの概要

1. 公式 LINE Chrome 拡張機能（ID: `ophjlpahpchlmihnnnihgmmeilfjmjjc`）をダウンロード
2. 中の `main.js` などをパッチ
   - `location.origin` などを拡張機能のオリジンに偽装
   - API ホストを same-origin にし、path は `/api/...` のまま維持（X-Hmac 用）
3. Node.js (Hono) で静的ファイル配信 + プロキシサーバーを起動

プロキシしている主なパス：

- `/api/*` → `https://line-chrome-gw.line-apps.com`
- `/R4` → `https://ci.line-apps.com`

---

## 環境変数（任意）

| 変数 | 説明 |
|------|------|
| `PORT` | 待受ポート（Railway / Render が自動設定） |
| `HOST` | 待受アドレス（既定 `0.0.0.0`） |
| `LINE_CHROME_VERSION` | 拡張バージョン上書き |
| `LINE_UA` | User-Agent 上書き |
| `DEBUG_PROXY` | `1` でパスのみデバッグログ |

---

## 無料枠の注意

- **Render Free**: 一定時間アクセスがないとスリープすることがあります
- **Railway**: プラン・クレジットに依存（スリープ有無はプラン次第）
- 常時起動や本番利用は各サービスの有料枠を検討してください

---

## ライセンス・免責

- 本リポジトリのコード（プロキシサーバー部分など）は MIT ライセンスとします
- 公式 LINE 拡張機能のコード自体は LINE ヤフー株式会社の著作物です
- 本プロジェクトは教育・研究目的のサンプルです

---

## BAN リスクを下げるための実装メモ

このリポジトリは次の対策を入れています（**BAN を防ぐ保証はありません**）。

- リクエスト path を公式と同じ `/api/...` のまま維持（X-Hmac 用）
- `Origin` / `User-Agent` / `x-line-chrome-version` を公式拡張に近づける
- プロキシ側の簡易レート制限（1 IP あたり毎分上限）
- トークンや本文をログに出さない
- Cookie を Web オリジンから上流へ転送しない

### 利用上の注意（重要）

1. **メインの大切なアカウントでは使わない**
2. 自動化・大量送信・BOT 用途はしない
3. 通常の人間の操作頻度を超えない
4. 公式 PC アプリや公式 Chrome 拡張がある場合はそちらを優先する

それでも非公式クライアントである限り、制限や BAN の可能性は残ります。
