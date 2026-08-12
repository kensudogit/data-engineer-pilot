# Power BI セマンティックモデル ノート

`connection_guide.md`の手順でMARTスキーマの4テーブルをPower BIに読み込んだ後の、
テーブル関連付け・DAXメジャー例です。実際のPower BI Desktopでの動作検証は
行っていません（実Snowflakeアカウント同様、今回のセッションでは未検証）。

## テーブル関連

| From | To | 関連キー |
|---|---|---|
| `DAILY_SALES` | （独立、日付軸で他テーブルとスライサー連携する場合はDateテーブルを別途作成） | `ORDER_DATE` |
| `CUSTOMER_FEATURES` | （独立、`CUSTOMER_ID`で顧客ディメンションを別途作る場合はそこに接続） | `CUSTOMER_ID` |
| `DAILY_PRODUCT_DEMAND` | （独立、`PRODUCT_ID`で商品ディメンションを別途作る場合はそこに接続） | `PRODUCT_ID` |
| `ORDER_TRANSACTION_FEATURES` | `CUSTOMER_FEATURES`（最新スナップショットのみ） | `CUSTOMER_ID` |

いずれも粒度の異なるファクトテーブル（日次集計 vs 取引単位 vs 顧客スナップショット）のため、
無理に1つの共有ディメンションモデルに統合せず、レポートページごとに必要なテーブルの
組み合わせのみをビジュアルに使うシンプルな構成を推奨します。

## DAXメジャー例

```dax
Total Revenue = SUM(DAILY_SALES[TOTAL_AMOUNT])

Churn Rate =
DIVIDE(
    CALCULATE(COUNTROWS(CUSTOMER_FEATURES), CUSTOMER_FEATURES[CHURNED_NEXT_30D] = TRUE),
    COUNTROWS(CUSTOMER_FEATURES)
)

High Risk Customer Count =
CALCULATE(
    DISTINCTCOUNT(CUSTOMER_FEATURES[CUSTOMER_ID]),
    CUSTOMER_FEATURES[CHURNED_NEXT_30D] = TRUE,
    CUSTOMER_FEATURES[SNAPSHOT_DATE] = MAX(CUSTOMER_FEATURES[SNAPSHOT_DATE])
)

Anomaly Order Amount Total =
CALCULATE(
    SUM(ORDER_TRANSACTION_FEATURES[ORDER_AMOUNT]),
    ORDER_TRANSACTION_FEATURES[SCORE] > 0.5  -- しきい値は運用に応じて調整
)

Top Product Demand (30d) =
CALCULATE(
    SUM(DAILY_PRODUCT_DEMAND[QUANTITY_SOLD]),
    DATESINPERIOD(DAILY_PRODUCT_DEMAND[ORDER_DATE], MAX(DAILY_PRODUCT_DEMAND[ORDER_DATE]), -30, DAY)
)
```

`Anomaly Order Amount Total`のしきい値（0.5）は`order_transaction_features`の`score`列の
実際の分布を見ながら調整してください——本パイロットのデモ経路では`contamination=0.015`
（想定異常率1.5%）でIsolationForestを学習しているため、Snowflake側でも同程度の閾値が
目安になります。
