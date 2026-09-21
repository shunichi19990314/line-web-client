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
   - `location.origin` などを拡張機能のオリジンに仮装
   - APIエンドポイントを自前プロキシ経由に変更
3. Node.js (Hono) で静的ファイル配信 + プロキシサーバーを起動

プロキシしている主なエンドポイント：

- `/_proxy/R4` → `https://ci.line-apps.com/R4`
- `/_proxy/CHROME_GW/*` → `https://line-chrome-gw.line-apps.com/*`

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
