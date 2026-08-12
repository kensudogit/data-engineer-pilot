# Power BI から Snowflake MARTへ接続する

このパイロットの`mart`スキーマ（`daily_sales`・`customer_features`・`daily_product_demand`・
`order_transaction_features`）にPower BI Desktopから接続する手順です。

## 前提

このリポジトリでは`.pbids`ファイルは提供していません。Microsoft公式ドキュメントは
`tds`（SQL Server）・`analysis-services`・`odata`等、限られたプロトコルのみ`.pbids`の
JSON形式を公開しており、**Snowflakeの正式なプロトコル文字列は公式ドキュメントに
存在しません**。実在しない値を捏造するよりも、以下の実在する手順（手動接続 + 実在する
Power Query M関数）を使用してください。

## 手順（Power BI Desktop）

1. **ホーム → データを取得 → その他 → Snowflake** を選択
2. 接続情報を入力:
   - **サーバー**: `<account>.snowflakecomputing.com`（`<account>`はSnowflakeアカウント識別子）
   - **ウェアハウス**: `DATA_ENGINEER_PILOT_WH`（既定値、`SNOWFLAKE_WAREHOUSE`環境変数と一致させる）
3. **データ接続モード**: DirectQuery（MARTデータはSnowflake側で常に最新のため）またはImport（ダッシュボードのパフォーマンス優先の場合）
4. 認証: Snowflakeのユーザー名/パスワード、またはSSO（組織のポリシーに従う）
5. ナビゲーターで対象データベース（既定`DATA_ENGINEER_PILOT`）→ `MART`スキーマ → 4テーブルを選択

## Power Query M スニペット（空のクエリから貼り付け可能）

Power BI Desktopの「空のクエリ」エディタに以下を貼り付けると、`Snowflake.Databases()`
（実在するドキュメント化されたPower Query M関数）経由で同じ接続を再現できます:

```powerquery-m
let
    Source = Snowflake.Databases(
        "<account>.snowflakecomputing.com",
        "DATA_ENGINEER_PILOT_WH",
        [Role = "PUBLIC"]
    ),
    Database = Source{[Name="DATA_ENGINEER_PILOT"]}[Data],
    MartSchema = Database{[Name="MART"]}[Data],
    DailySales = MartSchema{[Name="DAILY_SALES"]}[Data]
in
    DailySales
```

`<account>`を実際のアカウント識別子に置き換えてください。`Role`は環境に応じて調整します。

## 関連

テーブル関連・DAXメジャー例は同ディレクトリの`semantic_model_notes.md`を参照してください。
