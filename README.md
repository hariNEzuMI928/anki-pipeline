# anki-pipeline

Unified Anki 学習パイプライン — 密度トラッキング + Google Translate お気に入りからのカード自動作成。

## 概要

2 つの Anki 自動化ツールを統合した CLI ツールです。

### 1. GTrans — Google Translate お気に入り → Anki カード作成

Playwright で Google Translate のお気に入りページをスクレイピングし、Gemini API で単語/フレーズ/文を判別・加工して Anki カードを直接作成します。

- お気に入りを取得 → Gemini で構造化（単語は例文・意味付き、文は対訳）
- 処理済みの ID は JSON で管理し重複登録を防止
- 処理後は自動で Google Translate から削除

### 2. Density Tracking — 学習密度・進捗トラッキング

Anki コレクションを直接読み取り、学習密度や進捗を Google Sheets に記録し、Slack に通知します。

- 30 分単位の学習密度（デッキ別）
- 若いカード / 成熟カードの比率
- デッキ別学習時間（日次・30 日間）
- 週間進捗レポート（期日切れ・日曜までの見込み・今日の学習数）
- 時間帯に応じたタイトル付き Slack 通知

## アーキテクチャ

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ Google       │────▶│ anki-pipeline    │────▶│ Anki (apy)       │
│ Translate    │     │ CLI              │     │ コレクション      │
│ (Playwright) │     │                  │     └──────────────────┘
└──────────────┘     │                  │
                     │  ┌────────────┐  │     ┌──────────────────┐
┌──────────────┐     │  │ Gemini     │  │     │ Google Sheets    │
│ 学習データ    │────▶│  │ Processor  │  │────▶│ (3 シート)        │
│ (Anki DB)    │     │  └────────────┘  │     └──────────────────┘
└──────────────┘     │                  │
                     │  ┌────────────┐  │     ┌──────────────────┐
                     │  │ Slack      │  │────▶│ Slack Webhook    │
                     │  │ Reporter   │  │     └──────────────────┘
                     │  └────────────┘  │
                     └──────────────────┘
```

## セットアップ

1. **依存関係のインストール**

```bash
mise install  # Python 3.12
uv sync       # または pip install -e .
playwright install chromium
```

2. **環境変数の設定**

`.env` ファイルを作成（`.env.example` を参照）。

| 変数 | 必須 | 説明 |
|------|------|------|
| `ANKI_BASE` | 任意 | Anki ベースパス（デフォルト: `~/Library/Application Support/Anki2`） |
| `ANKI_PROFILE` | 任意 | Anki プロファイル名（デフォルト: `同期用`） |
| `SLACK_WEBHOOK_URL` | Density 利用時 | Slack Incoming Webhook URL |
| `SPREADSHEET_ID` | Density 利用時 | Google Sheets ID（学習データ書き込み先） |
| `GOOGLE_CREDENTIALS_PATH` | Density 利用時 | サービスアカウントの credentials.json のパス |
| `GEMINI_API_KEY` | GTrans 利用時 | Google Gemini API キー |
| `GEMINI_MODEL` | 任意 | Gemini モデル名（デフォルト: `gemini-2.0-flash`） |
| `BATCH_LIMIT` | 任意 | 1 回のバッチ処理上限（デフォルト: 50） |

3. **Google Translate 認証**

初回のみ手動ログインが必要です。

```bash
mise run run-all --manual-login
```

または

```bash
python -m anki_pipeline manual-login
```

## 使い方

### mise タスク（推奨）

プロジェクトルートで `mise run <タスク名>` で各サブコマンドを実行できます。

```bash
# フルパイプライン（GTrans → 密度トラッキング → レポート）
mise run run-all                     # 全ての処理を連続実行
mise run run-all -- --limit 30       # 上限指定（-- で挟んで引数渡し）
mise run run-all -- --skip-delete    # 削除スキップ

# 密度トラッキングのみ（読み取り → Sheets/Slack）
mise run run-density

# GTrans のみ（お気に入り取得 → カード作成）
mise run run-gtrans

# 新規お気に入り数の確認（Anki 起動不要、軽量）
mise run check-new

# Google Translate の再認証
mise run manual-login

# Anki 同期のみ
mise run sync-only
```

### CLI サブコマンド（直接実行）

パッケージがインストール済み（`.venv/bin/anki-pipeline`）の場合、Python モジュールとしても実行できます。

```bash
.venv/bin/python -m anki_pipeline run-density
.venv/bin/python -m anki_pipeline run-all --limit 30
.venv/bin/python -m anki_pipeline check-new
```

### launchd 自動実行

macOS launchd による定期実行が設定されています。

- **スケジュール**: 毎日 0:00, 12:05, 17:05, 21:05, 23:05
- **ラベル**: `com.user.anki-pipeline`
- **設定ファイル**: `launchd/com.user.anki-pipeline.plist.template`

インストール:

```bash
~/dotfiles/launchd/install_launchd.sh --all
```

## プロジェクト構成

```
anki-pipeline/
├── src/anki_pipeline/
│   ├── __main__.py        # CLI エントリーポイント
│   ├── config.py          # 設定管理（.env → 定数）
│   ├── sync.py            # Anki 状態管理・同期（apy）
│   ├── storage.py         # 処理済み ID の永続化
│   ├── anki_writer.py     # Anki カード作成
│   ├── density/
│   │   └── stats.py       # 学習密度・統計計算
│   ├── gtrans/
│   │   ├── scraper.py     # Playwright スクレイパー
│   │   ├── processor.py   # Gemini 処理
│   │   └── selectors.json # CSS セレクタ定義
│   └── report/
│       ├── sheets.py      # Google Sheets 書き込み
│       └── slack.py       # Slack 通知
├── launchd/               # launchd plist テンプレート
├── data/                  # ランタイムデータ（auth state, processed IDs）
│   ├── auth_state.json
│   └── processed_ids.json
├── logs/                  # ログファイル
│   └── anki-pipeline.log
├── .env.example           # 環境変数テンプレート
├── pyproject.toml
├── mise.toml
└── README.md
```

## 技術スタック

- Python 3.12+ / `apyanki`（AnkiConnect 不要、直接 DB アクセス）
- Playwright（Google Translate スクレイピング）
- Google Gemini API（テキスト構造化）
- Google Sheets API / gspread（学習データ蓄積）
- Slack Webhook（通知）
- macOS launchd（定期実行）
- mise（ツール・タスク管理）

## 注意事項

- **macOS 専用**: Anki のライフサイクル管理に AppleScript を使用しています。
- **Anki 停止必須**: 密度トラッキングと GTrans のカード作成は Anki が起動していない状態で実行します（パイプラインが自動で終了・同期を行います）。
- **Google Translate セレクタ**: `selectors.json` の CSS セレクタは Google Translate の UI 変更で動作しなくなる可能性があります。その場合は `manual-login` + スクリーンショットを元に修正してください。