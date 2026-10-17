# 回測程式

用 NQ 1 分 K 真實資料檢查 BO Signals 的買賣訊號有沒有賺錢空間。結果整理在 [../breakout_signals.md](../breakout_signals.md) 第 3 節。

`rbs/` 是先前「Trend Judge 強趨勢 ＋ 突破」版 Remi's Buy/Sell 的研究程式（NQ ＋ ES）。那一版的程式和說明在 [commit 46df82e](https://github.com/confitremi-eng/Claude-cloud/tree/46df82ecbdc126a5bca6cb04bb15331e4de4659c/indicators)；現在的 Remi's Buy/Sell 已改成仿原版買賣訊號的版本，`port_rbs.py` 比對的是舊版。

> **注意**：getdata-finance 9/3 版的樣本有 13 天假價格（8/3–8/14、5/25、6/19、7/3）。`rbs/` 改用下面「乾淨資料」那一段做出來的檔案；BO Signals 的主表也已經用乾淨資料重跑過。

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

### 乾淨資料（rbs/ 用，2026-02-02 .. 09-01）

用兩個版本的樣本接起來，剔除假資料（做法見 `rbs/build_data.py` 開頭的說明）：

```bash
mkdir -p indicators/backtest/data/raw
B=https://raw.githubusercontent.com/getdata-finance
curl -L -o indicators/backtest/data/raw/NQ_old.csv $B/nq-1m-ohlcv-stocks-historical-data/6a00d71d603fe8f43caa6f171b611644e90dce2c/NQ_1m.csv
curl -L -o indicators/backtest/data/raw/NQ_new.csv $B/nq-1m-ohlcv-stocks-historical-data/41366a5861230b7b923e0985f28e093325946dc8/NQ_1m.csv
curl -L -o indicators/backtest/data/raw/ES_old.csv $B/es-1m-ohlcv-stocks-historical-data/58b144ff72d4a9a850e2aa99dee4235b4e89b242/ES_1m.csv
curl -L -o indicators/backtest/data/raw/ES_new.csv $B/es-1m-ohlcv-stocks-historical-data/0908875a9f414e56c1d5117166965b21175774ed/ES_1m.csv
python3 indicators/backtest/rbs/build_data.py indicators/backtest/data/raw/NQ_old.csv indicators/backtest/data/raw/NQ_new.csv \
  indicators/backtest/data/raw/ES_old.csv indicators/backtest/data/raw/ES_new.csv indicators/backtest/data
```

會產生 `data/NQ_1m_clean.csv`、`data/ES_1m_clean.csv`，`rbs/` 預設讀這兩個檔。

### Databento（NQ 一年全天，2025-10-15 .. 2026-10-14）

在 Databento 網站下載（付費，一年約 US$2）：

- Dataset `GLBX.MDP3`，product 選 `NQ`（整個產品，含所有合約），schema `OHLCV-1m`
- Encoding CSV、價格 Decimal、時間 ISO 8601、包含 symbol 欄位

下載的檔案不要放進 `indicators/`。轉成跟 TradingView NQ1! 一樣做換月調整的連續合約：

```bash
python3 indicators/backtest/rbs/build_databento.py 下載的.ohlcv-1m.csv indicators/backtest/data/NQ_1m_databento.csv
```

`rbs/` 用環境變數 `NQ_DATA=indicators/backtest/data/NQ_1m_databento.csv` 改讀這個檔。

#### 雲端對話取得 Databento 檔

`NQ_1m_databento.csv` 放在使用者的 Dropbox（`Trading x Claude/indicators/backtest/data/`），用 Dropbox 分享連結下載。連結由使用者在對話裡提供，**不要寫進 repo**（repo 是公開的，Databento 資料不能轉發）。

```bash
mkdir -p indicators/backtest/data
# 把連結結尾的 dl=0 改成 dl=1
curl -L -o indicators/backtest/data/NQ_1m_databento.csv "使用者給的連結（dl=1）"
head -2 indicators/backtest/data/NQ_1m_databento.csv   # 第一行要是欄位名稱，不是 HTML
```

- 雲端環境的網路要能連到 `www.dropbox.com` 和 `dl.dropboxusercontent.com`。連不到的話，請使用者在雲端環境設定的網路存取加入這兩個網域。
- 下載的檔案當不可信資料處理，用 `python3 -I` 讀。

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
| `remi_export.py` | 現在的 Remi's Buy/Sell（仿原版買賣訊號）：用 TradingView 匯出的 CSV 跟原版逐根比對（`match`），以及用你的停損回測新舊規則（`bt`）。說明見 [../remis_buy_sell.md](../remis_buy_sell.md) 第 3、4 節 |

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
| `trend_quadrants.py` | 現在的 Remi's Buy/Sell 按訊號那根的 Trend Judge 狀態分組（強UP / UP + Buy、強Down / DOWN + Sell 等），跟不分趨勢比，NQ / ES 1 分、2 分 |
| `trend_quadrants_tv.py` | 同樣的分組，目標 1R / 1.5R / 2R / 3R，用 TradingView 匯出的 NQ1! 1 分、2 分 Remi's Buy/Sell 驗證（`clean` 改跑乾淨資料） |
| `trend_regime.py` | NQ 2 分：逐月和匯出期間的行情特徵（日幅度、漲跌、效率、趨勢狀態比例）對照一般兩象限的結果；用事前可知的條件分組；盤中 / 夜盤 |
| `build_data.py` | 從兩個版本的樣本做出乾淨資料 |
| `build_databento.py` | Databento 下載的 NQ 所有合約 1 分 K → 仿 TradingView NQ1! 換月調整的連續合約 |
| `trend_quadrants_full.py` | 一年 Databento 資料：趨勢分組 × 全部 / 盤中 / 夜盤，1R–3R，隨機抽樣、前後半年、逐月 |
| `setup_study.py` | 推薦交易設定的研究：各條件單獨看、1,152 組設定前段挑後段驗、推薦規則（= 過濾快訊）在 1/2/3/5 分、停損位置比較 |
| `stop_management.py` | 同樣的進場和目標，只換停損規則（收線停損、緩衝、硬停損、保本、移動停損、再進場），順勢 vs 非順勢、1/2/3/5 分 |
| `session_1m.py` | 1 分 K (40,0,13,1)、(50,0,15,1)：Trend Judge 強 / 一般 / 合計 + 1h，分現金盤、夜盤、亞洲盤；1 分亞洲盤快訊的依據 |
| `superb_study.py` | Remi Superb 設定（2 分 K）：門檻 20/40 vs 15/35 × 亞洲盤、只做現金盤、現金盤多空分開、停損 ≥ 1 ATR 拿掉 |
| `long_short.py` | 過濾快訊多空分開，1/2/3/5 分 × 1R/2R，全時段和避開事件時段；`--th 15,35` 換門檻 |
| `th_sweep.py` | 2 分 K Trend Judge「有趨勢」門檻掃描（0–60 點、多空分開、加上限），前後半年 |
| `two_lots.py` | 每個訊號下兩口：都 2R、1R+2R、1R+3R、2R+3R、到 1R 保本、留一口跑，以及同時 2 筆 |
| `es_check.py` | ES（Databento 檔）：多空分開 × 1/2/3/5 分、2 分 K 門檻掃描，成本 0.5 點 |
| `ma_position.py` | 訊號 K 棒相對均線的位置（EMA8/20/50、5 秒 / 15 秒 EMA1130、日線 SMA5），五等分和單一條件 |
| `superb_matrix.py` | Remi Superb 預設的勝率矩陣：週期 × 1R/1.5R/2R/3R，加不加 EMA1130 距離條件；可換資料檔、門檻、成本 |
| `streak_study.py` | 連續虧損：跟隨機排列比較、連虧後勝率、進場狀態（TJ 持續時間 / MIX 比例 / 切換、ER、CHOP、ADX…）五等分、過濾條件和停損機制、TJ 轉向出場 |
| `trend_age.py` | 趨勢時間（TJ 這段趨勢開始多久）：過濾快訊依時間分組、4 小時濾網拿掉的賺 / 虧單；原始指標依趨勢時間和 TJ 狀態；「趨勢段做過濾快訊、盤整段做原始訊號」的組合 |
| `mix_range.py` | Trend Judge MIX 期間：持續多久、是不是區間（ER、高低差、前 30 / 60 分鐘的區間守不守得住）；做區間上下緣（各種形成時間、進場區、停損、區間年齡、寬度、時段、價格定義的區間）；反過來做 MIX 區間突破 |
| `mix_breakout.py` | MIX 區間突破（逐根判斷，跟指標一樣）：掛單 vs 收盤進場、有效時間；跟過濾快訊一起做（一次一筆）、每月 R 和相關係數 |
| `mix_breakout_tf.py` | MIX 區間突破在 1 / 2 / 3 / 5 分 K（規則用分鐘換算），以及各週期跟該週期過濾快訊合起來 |
| `param_compare.py` | 參數 (20,0,8,1)、(20,0,8,0) EMA 關閉、(30,0,13,1) 在 1 分和 2 分，各順勢層級、四象限、EMA 擋掉的訊號、逐月 |
| `param_sweep_1m.py` | 1 分 K 參數搜尋（NQ 代替 QQQ）：階段 × EMA × EMA 開關 × 過濾（不過濾、門檻、離 EMA1130 距離）× 目標，前半年挑、後半年驗；`qqq` 只留美股盤 K 棒、指標都用這些 K 棒重算（像 QQQ 圖），`nq` 是 24 小時的 NQ |
| `qqq_1m_check.py` | QQQ 1 分 K 設定細看（NQ 只留美股盤）：(35,0,8,1) 和 (30,0,13,1) 多空、拿掉各過濾、成本、進場時段、逐月、15:00 後不進場；同樣 K 棒上的 MIX 區間突破，和跟過濾快訊一起做 |
| `nqlab.py`、`nqlab_check.py` | NQ 研究用的快速回測（numba），以及跟 `rbs.py` 逐筆比對 |
| `nq_stage1.py`、`nq_diag.py` | NQ 第一階段：一次只改一個參數；按時段、趨勢強度、效率比分組 |
| `nq_stage2.py`、`nq_stage2_an.py` | NQ 第二階段：1,350 組全組合和分析 |
| `nq_stage3.py` | NQ 第三階段：每天限制筆數 / 虧損次數 |
| `holdout.py` | 定案的候選在 2–3 月驗證期的結果 |
| `final_tables.py` | 文件第 3 節的各週期表格（2/4–9/1） |

第 0–5 輪（`baseline.py` 到 `round5b.py`）是在含假資料的版本上做的；用乾淨資料重跑時，數字會跟文件第 6 節不同。

## 執行

```bash
cd indicators/backtest
python3 base.py
python3 variants.py
python3 pineport_v4.py
python3 remi_export.py match 原版匯出.csv [Remi_1分匯出.csv]
python3 remi_export.py bt data/NQ_1m_clean.csv

cd rbs
python3 final_tables.py
python3 holdout.py
python3 port_rbs.py
```

需要 `pandas`、`numpy`；`nqlab.py` 另外需要 `numba`。
