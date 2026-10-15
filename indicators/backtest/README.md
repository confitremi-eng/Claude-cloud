# 回測程式

用 NQ 1 分 K 真實資料檢查 BO Signals 的買賣訊號有沒有賺錢空間。結果整理在 [../breakout_signals.md](../breakout_signals.md) 第 3 節。

`rbs/` 是 Remi's Buy/Sell 的研究程式（NQ ＋ ES、Trend Judge 趨勢過濾），結果整理在 [../remis_buy_sell.md](../remis_buy_sell.md)。

## 準備資料

資料不放在 repo 裡，先下載 getdata-finance 的免費樣本（MIT 授權）：

```bash
mkdir -p indicators/backtest/data
curl -L -o indicators/backtest/data/NQ_1m.csv \
  https://raw.githubusercontent.com/getdata-finance/nq-1m-ohlcv-stocks-historical-data/main/NQ_1m.csv
# rbs/ 另外需要 ES
curl -L -o indicators/backtest/data/ES_1m.csv \
  https://raw.githubusercontent.com/getdata-finance/es-1m-ohlcv-stocks-historical-data/main/ES_1m.csv
```

換成別的 1 分 K 資料也可以，欄位要是 `datetime,open,high,low,close,volume`，再用環境變數 `NQ_DATA`、`ES_DATA` 指定路徑。

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

### rbs/（Remi's Buy/Sell）

| 檔案 | 用途 |
|------|------|
| `rbs.py` | 讀 NQ / ES、用 1 分 K 推算 Trend Judge（5 秒 / 15 秒 EMA 1130 差值，每 2 分鐘鎖定）、逐筆模擬 |
| `fams.py` | 三類訊號：買賣訊號、回檔到 Trend Judge 快線、N 根突破，以及趨勢過濾 |
| `baseline.py` | 第 0 輪：買賣訊號 (25) ＋ Trend Judge 方向 |
| `round1.py`、`analyze1.py` | 第 1 輪：訊號 × 參數 × 出場，前半段 / 後半段 |
| `round2.py`、`regime.py` | 第 2 輪：組合規則；逐月表現 |
| `round3.py` | 第 3 輪：開盤區間、趨勢加速、停損根數、突破根數等 |
| `round4.py` | 第 4 輪：突破根數、ADX、效率比 |
| `final_cmp.py` | 定案比較：現行組合和 C1–C4，8 格 × 1R / 1.5R / 2R |
| `round5.py`、`round5b.py` | 第 5 輪：停損寬度、固定口數點數、1 分 K 專用參數 |
| `port_rbs.py` | 把 `remis_buy_sell.pine` 逐行改寫，跟研究規則逐筆比對；分鐘換算的趨勢一致率 |
| `check_tj.py` | Trend Judge 各狀態所佔比例 |

## 執行

```bash
cd indicators/backtest
python3 base.py
python3 variants.py
python3 pineport_v4.py

cd rbs
python3 final_cmp.py
python3 port_rbs.py
```

需要 `pandas`、`numpy`。
