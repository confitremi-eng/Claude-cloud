# 回測程式

用 NQ 1 分 K 真實資料檢查 BO Signals 的買賣訊號有沒有賺錢空間。結果整理在 [../breakout_signals.md](../breakout_signals.md) 第 3 節。

## 準備資料

資料不放在 repo 裡，先下載 getdata-finance 的免費樣本（MIT 授權）：

```bash
mkdir -p indicators/backtest/data
curl -L -o indicators/backtest/data/NQ_1m.csv \
  https://raw.githubusercontent.com/getdata-finance/nq-1m-ohlcv-stocks-historical-data/main/NQ_1m.csv
```

換成別的 1 分 K 資料也可以，欄位要是 `datetime,open,high,low,close,volume`，再用環境變數 `NQ_DATA` 指定路徑。

## 檔案

| 檔案 | 用途 |
|------|------|
| `bt.py` | 讀資料、合成 2/3/5 分 K、訊號規則（跟 Pine 一致）、逐筆模擬 |
| `trend.py` | 趨勢判斷：EMA 斜率、價格 vs EMA、EMA 快慢線、更高週期 EMA、共識 K 棒 |
| `families.py` | 其他訊號設計：淺回檔、N 根突破、EMA 回檔，以及另一套逐筆模擬 |
| `base.py` | 現行規則在 1/2/3/5 分 K 的結果，分順勢 / 逆勢 |
| `variants.py` | 12 種規則改法，4–6 月訓練、7–9 月驗證 |
| `explore.py` | 順勢訊號設計 × 趨勢判斷 × 出場方式，訓練 / 驗證 |
| `pineport_v4.py` | 把 Pine 的訊號和回測統計逐行改寫，跟 `bt.py` 逐筆比對 |

## 執行

```bash
cd indicators/backtest
python3 base.py
python3 variants.py
python3 pineport_v4.py
```

需要 `pandas`、`numpy`。
