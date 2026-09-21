# LINE Web Client (Unofficial)

公式の **LINE Chrome拡張機能** をパッチして、普通のWebサイトとして動くようにした非公式クライアントです。

> **注意**  
> これは非公式の実装です。LINEの利用規約に違反する可能性があります。  
> 自己責任で利用してください。

---

## 必要なもの

- Node.js 18以上
- Python 3 + `requests`（拡張機能の取得用）
  ```bash
  pip install requests
  ```

---

## セットアップ手順

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

## Renderへのデプロイ手順

1. このリポジトリをGitHubにpushする

2. [Render Dashboard](https://dashboard.render.com) にログイン

3. **New → Web Service** をクリック

4. GitHubリポジトリを接続

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

---

## 仕組みの概要

1. 公式LINE Chrome拡張機能（ID: `ophjlpahpchlmihnnnihgmmeilfjmjjc`）をダウンロード
2. 中の `main.js` などをパッチ
   - `location.origin` などを拡張機能のオリジンに偽装
   - APIホストを same-origin にし、path は `/api/...` のまま維持（X-Hmac用）
3. Node.js (Hono) で静的ファイル配信 + プロキシサーバーを起動

プロキシしている主なパス：

- `/api/*` → `https://line-chrome-gw.line-apps.com`
- `/R4` → `https://ci.line-apps.com`

---

## 無料枠の注意

- 15分間アクセスがないとスリープします
- 次のアクセス時に起動まで時間がかかることがあります
- 常時起動させたい場合は有料プランが必要です

---

## ライセンス・免責

- 本リポジトリのコード（プロキシサーバー部分など）はMITライセンスとします
- 公式LINE拡張機能のコード自体はLINEヤフー株式会社の著作物です
- 本プロジェクトは教育・研究目的のサンプルです

---

## BANリスクを下げるための実装メモ

このリポジトリは次の対策を入れています（**BANを防ぐ保証はありません**）。

- リクエスト path を公式と同じ `/api/...` のまま維持（X-Hmac 用）
- `Origin` / `User-Agent` / `x-line-chrome-version` を公式拡張に近づける
- プロキシ側の簡易レート制限（1 IP あたり毎分上限）
- トークンや本文をログに出さない
- Cookie をWebオリジンから上流へ転送しない

### 利用上の注意（重要）

1. **メインの大切なアカウントでは使わない**
2. 自動化・大量送信・BOT用途はしない
3. 通常の人間の操作頻度を超えない
4. 公式PCアプリや公式Chrome拡張がある場合はそちらを優先する

それでも非公式クライアントである限り、制限やBANの可能性は残ります。
