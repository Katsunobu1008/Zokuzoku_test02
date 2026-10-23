
## 1. ローカル起動（追加パッケージ不要）

Python 3.11以降をインストールしてください。

```bash
git clone https://github.com/Katsunobu1008/Zokuzoku_test02.git
cd Zokuzoku_test02
python -m app
```

ブラウザで **http://127.0.0.1:8000** を開きます。初回に `data/zokuzoku.sqlite` が作成され、100件の架空サンプル作品が投入されます。Gitで `data/` は無視されます。

### OpenAI画像生成を有効にする

1. OpenAI Platformで発行した**新しい**APIキーを用意します。チャットやissueに貼ったキーは使わず**ローテーション**してください。
2. 環境変数 `OPENAI_API_KEY` を設定してからサーバーを起動します。

macOS/Linux:

```bash
export OPENAI_API_KEY='YOUR_ROTATED_KEY_HERE'
export OPENAI_IMAGE_MODEL='gpt-image-1-mini'
python -m app
```

PowerShell:

```powershell
$env:OPENAI_API_KEY = 'YOUR_ROTATED_KEY_HERE'
$env:OPENAI_IMAGE_MODEL = 'gpt-image-1-mini'
python -m app
```

**APIキーをHTML、ブラウザJavaScript、GitHubリポジトリ、README、ログに貼り付けないでください。** 画像生成はフォーム内の明示的なチェックをONにした場合のみ実行します。回数上限はデフォルトでユーザーあたり1時間に3回、サーバープロセスあたり計50回（再起動でリセットされる暫定制御）。さらに**OpenAI側の利用上限**を設定してください。画像APIのモデル提供状況・権限・価格はOpenAI Platformで確認してください。

### Docker Compose

```bash
docker compose up --build
```

Composeのポートは`127.0.0.1:8000`に限定しており、データは名前付きボリュームへ保存されます。

### テスト

```bash
python -m unittest discover -s tests -v
# or
make check
```

外部APIを呼ばないテストなので、キーは不要です。

## 2. 画面の操作

1. **発見する**: 100個のクラゲアイデアをマップとカードから探索する。拡大、縮小、ランダム移動、人気順で検索。
2. **継承する**: 気になる作品を開き「この作品を継承する」を選ぶ。親IDを持つ新しい作品が登録される。
3. **画像生成（任意）**: 権利確認をしてチェックを入れると、作品登録後にOpenAI Images APIを呼ぶ。エラー時も投稿済みデータは残る。
4. **応援する**: いいね、コメント、仮想ポイントによる応援意思を記録する。
5. **インサイト**: 集計結果を見る。ただしサンプル100件が含まれるため実際の顧客需要ではない。
6. **PICSY LAB**: 原作者A、二次創作者B、ファンCの評価行列Eと変換後E′、貢献度cの変化を確認する。

**別ブラウザ**で開きデモユーザーを切り替えると、数秒の更新間隔で投稿やいいねが他方に表示されます。同一プロセス・同一SQLiteデータベースへの接続を前提とします。
