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
| `superb_sweep.py` | Remi Superb 過濾快訊的 Trend Judge 門檻掃描，任何 Databento 1 分 K 檔（NQ、ES），有 / 沒有 EMA1130 距離 |
| `txf_check.py` | TXF：TradingView 2 分 K 匯出或 TXFR1 1 分 K 的 SQL 檔（只讀 COPY 資料，不執行 SQL）→ Remi Superb 過濾快訊門檻掃描、萬分比門檻、逐年；換月前後排除 |
| `limit_entry.py` | 進場改用限價單（掛在停損點或一半、新停損、等幾分鐘、碰價或穿價成交）跟市價進場比較，全部在 1 分 K 上模擬；`DATA 門檻 成本`，ES、NQ 都能跑 |
| `trend_mix_matrix.py` | Trend（過濾快訊）和 MIX 突破的 2 分 K 勝率矩陣（1R / 1.5R / 2R / 3R、多空、前後、合起來），`nq` / `es` / `txf` 用各自的預設門檻和成本；TXF 另有逐年 |
| `nq_follow.py` | 用 NQ 2 分 K 的 Remi Superb 訊號（Trend、MIX）做 ES 或 TXF：可下單比例、報酬相關、輸贏一致率，停損用 ATR 換算 / 跟 NQ 出場 / 自己兩根 K，分時段、多空、自己 Trend Judge 同向、晚 1 分鐘、成本；TXF 另有只做夜盤和逐月 |
| `bought_signal_log.py` | 買來的指標 es 3m 2026 v2.1（🦀🍦，沒有原始碼）的勝率紀錄：吃 TradingView 圖表匯出 CSV，多份依時間合併、標出重繪消失的訊號，四種停損的 1 / 1.5 / 2 / 3R 命中與每筆 R；`--mkt nq` 換 NQ；輸出 `signal_log/` |
| `bought_raw_backtest.py` | 同一支指標的原始觸發（100 根新低、收盤站回、不看 EMA）多年回測：`nq 2`、`nq 5`（NQ_1m_5y）、`txf 2 *.sql`，逐年、盤別、連發、EMA200 / 89 上下 |
| `rise_points.py` | 三種起漲點（慢跌收復、急跌反轉、中繼急殺，來自 🦀 / 🍦）在 NQ 2 / 5 分 K 五年：21 種條件分組（固定 1 ATR 停損，對照隨機漫步）、前後兩段；`--search` 兩兩組合並用打亂結果檢驗是不是運氣 |
| `v4_check.py` | V4 候選：v3 現行規則（同 `reentry.py`）只把原版訊號換成 Remi 圖上的 (8, 0, 9, 1)，跟 (20, 0, 8, 1) 逐年比 1 / 1.5 / 2 / 3R 的 R 和勝率、最近半年；NQ 2m、5m |
| `v4_winrate.py` | V4 高勝率研究：v3 會做的趨勢 / MIX 訊號，目標 0.25–1.5R、停損 ×1 / 1.5 / 2，對照隨機漫步；條件分組、兩兩組合打亂檢驗（`search`）、一次一筆的出場比較（`exits`：小目標、分批、保本）、溫和過濾 × 出場逐年（`v4`）；結果在 `../v4_high_winrate.md` |
| `v4_reference.py` | V4 策略版（`../remi_superb_v4_strategy.pine`）的 Python 重跑：每筆 4 口、0.33R ×2 / 0.6R / 3R、保本、高開低走 0.33R，一次一筆照 Pine，成本照 TradingView 屬性；逐月筆數、勝率、TV 筆數 / 勝率、淨利（美元）和最近 20 筆，給策略測試器對照 |
| `one_minute.py` | NQ 1 分 K：1m 和 2m 同時出訊號（只用進場當下已知的資訊）、等 2m 確認再進、2m 還沒出訊號的 1m 訊號贏輸特徵、過濾訊號依趨勢已持續多久（1/2/3/5 分，MIX 長短、反轉或延續）、30–120 分鐘窗口的穩定性和一次一筆結果 |
| `v2_port.py` | Remi Superb v2 照指標逐根重算：趨勢訊號（30–120 分）、MIX 突破、一次一筆虛擬持倉（停損、目標、60 根、17:00 休市、資料中斷），3R / 2R、不限趨勢時間 |
| `trend_time_tf.py` | 3 / 5 分 K（2 分 K 參考）的過濾訊號依指標的趨勢已持續分鐘數：30 分鐘分段、範圍掃描（前後半年都賺）、一次一筆 |
| `market_matrix.py` | 同一套規則套到 NQ / ES / TXF（2m、3m）和 SPY / QQQ（1m、2m，用 ES / NQ 美股盤代替）：趨勢全部、0–180、60–120、90–120 分、ETF 設定、MIX 突破、v2 組合 |
| `qqq_vs_nq.py` | QQQ 1m 訊號（ETF 設定、趨勢 0–180）依進場當下 NQ 2m（24 小時圖）的 Trend Judge 同向 / MIX / 反向、NQ 趨勢時間、NQ 近期訊號分組，加一次一筆 |
| `trend_follow.py` | 強趨勢中的順勢進場（回檔碰快線轉下、跌破 20 根前低）：單獨、依趨勢時間和時段、加進 v3（NQ 2m），以及 2026-10-16 週五 ES 會不會抓到 |
| `raw_vs_filter.py` | 沒過濾的原版訊號（灰色三角）全部 / 逆勢 / 順勢，每拿掉一個條件的結果，只被某個條件擋掉的訊號；週五台灣週六 02:00 以後不交易對 v3 的影響 |
| `nq5m.py` | NQ 5 / 10 / 15 分 K（`python3 -I rbs/nq5m.py 10 15`）：趨勢訊號依趨勢時間、時段、多空、Trend Judge 強弱、目標；MIX 突破（區間 60 / 120 分、持有 2 小時 / 60 根）；一次一筆的組合；`--stages` 試短一點的「階段」 |
| `txf_tf.py` | TXF 3 / 5 分 K（SQL 1 分 K）：過濾訊號依趨勢時間、日盤 / 夜盤、多空、強弱、年份，(20, 0, 8, 1) 和 (35, 0, 8, 1)；MIX 突破；一次一筆（成本 2 / 4 點）；`--candidates` 三組候選逐年 |
| `mix_opt.py` | MIX 突破的改法（NQ 2 / 5 分 K）：一轉 MIX 就進場（反向 / 順勢、停損）、區間要多長、突破距離、有效時間、停損位置、各種條件、目標，放回 v3 一次一筆；`--close` 只算 v3 預設規則下 MIX 突破就進場 vs 等收線進場（2R / 3R） |
| `strong_stage.py` | 趨勢拉開（Trend Judge 差值是「強」門檻的幾倍）時把「階段」改短：QQQ / SPY 1m 35 → 30 / 25 / 20 / 15、NQ 2m 20 → 15 / 12 / 10；各自獨立依拉開程度、短階段多出來的訊號、放回 v3 一次一筆 |
| `oneside_3013.py` | 原版 (30, 0, 13, 1)（單邊日用）在 QQQ / SPY 1m：Trend Judge 順勢 / MIX / 反向、趨勢時間、拉開程度、單邊日（強 + 趨勢已久、NQ 2m 也強、當天已走幾 %）、v3 過濾；附近參數（階段 20–40 × EMA 8 / 13 / 21）；一次一筆和加進 v3 |
| `zerogex_fetch.py` | 下載 ZeroGEX（Pro API）SPY / QQQ 的歷史到 `data/zerogex/`：每分鐘 gamma flip、call / put wall 和 QQQ / SPY 的 1 分 K（`range`）、每 30 分鐘 net GEX（`frames`，很慢）、每天的狀態（`regime`）。金鑰從檔案讀，不要放進 repo；已下載的日子會跳過 |
| `gex_qqq.py` | QQQ 1m 原版 (35, 0, 8, 1) 和 v3 訊號，依 SPY / QQQ 的 gamma 正負（價格 vs gamma flip，當下或開盤）分組，買賣分開；Remi 的規則一次一筆；NQ 代替和 ZeroGEX 的 QQQ 實際 K 棒各算一次 |
| `gex_trend.py` | 順勢訊號（QQQ 1m 原版且 Trend Judge 同向、QQQ 1m v3、NQ 2m v3 美股盤）× GEX：SPY / QQQ gamma 正負、買賣 × gamma、離 QQQ gamma flip 多遠（朝 flip 走 / 離開，再依趨勢時間）、到 call / put wall 的空間（幾倍停損）、等級相關 |
| `qqq_3008.py` | QQQ 1m 原版 (30, 0, 8, 1)：QQQ Trend Judge 順勢、NQ 2m 同向 / MIX / 逆勢，買賣分開，逐一加上 v3 的條件、依趨勢時間；一次一筆對照 v3 的 QQQ；NQ 代替一年 + ZeroGEX 的 QQQ 實際 K 棒 |
| `qqq_3008_when.py` | QQQ 1m 原版 (30, 0, 8, 1) 不過濾，依開盤後幾分鐘、跳空、當天已走、開盤 15 / 30 分區間（假突破收回等）、QQQ / NQ 2m Trend Judge 分組，買賣分開；`--check` 加 (25 / 35, 0, 8, 1) 和 QQQ 實際 K 棒；`--gex` 依 gamma flip 方向和到牆空間 |
| `gex_params.py` | v3 GEX setup（NQ RTH 1m，Trend Judge 順勢 + 朝 QQQ gamma flip 走）的階段 15–50 × EMA 5 / 8 / 13 / 21：筆數、1R 勝率、2R / 3R 每筆、一次一筆合計和回撤，細看幾組 |
| `gex_trend_src.py` | v3 GEX setup 的趨勢條件該看哪個：NQ RTH 1m 自己的 Trend Judge、24 小時 NQ 1m / 2m（ETH）、兩個都要、不看，各自獨立和一次一筆 |
| `gex_matrix.py` | v3 GEX setup（預設）的勝率矩陣：1 / 1.5 / 2 / 3R × 全部、台北 00:00–01:05、買賣、趨勢強弱、趨勢已持續、離 flip、到牆空間、美東時段、月份；一次一筆 |
| `oos_check.py` | v3 樣本外驗證（`oos_plan.md`）：NQ 2021-10 .. 2026-10（`data/NQ_1m_5y.csv`），規則凍結，NQ 2m / 5m / 3m / NQ RTH 逐年；規則開關、趨勢 / MIX 分開、鄰近參數、門檻依真實價格等比例 |
| `mix5_oos.py` | NQ 5m（或 2m）MIX 突破五年逐年：目標 1–5R × 區間 60 / 90 / 120 分 × 停損中線 / 0.75 / 對面 × 前 10 分作廢，整張表看是不是一片都賺 |
| `v3_months.py` | v3（凍結）五年每月 R（NQ 2m / 5m / NQ RTH），日曆月份平均，依當月 / 上月的漲跌、波動、振幅、趨勢效率、Trend Judge 有趨勢時間分三組 |
| `fastline.py` | v3 趨勢訊號依收盤在 5 秒 EMA1130（快線）哪一邊、離快線幾 ATR 分組，v3 那一年 / 2025 年初到 10 月 / 樣本外 4 年；加「只做快線順向」放回 v3 一次一筆 |
| `reversal.py` | v3 趨勢訊號在「前一筆停損、價格在慢線另一邊、差值縮小」時，之後 60 / 120 分 Trend Judge 轉向的比例、60 分走勢、1R / 3R（v3 那一年、五年） |
| `calib.py` | Trend Judge 門檻要不要跟著 NQ 點數校正：`mech` 依訊號時差值（點、換算後）分組逐年看虧在哪；`calib` 門檻依價格 / 過去 20 天日振幅 / 差值大小調整，NQ 2m / 5m / 3m / NQ RTH 逐年 |
| `year_th.py` | 每年固定一個 Trend Judge 門檻（4–20 點）：NQ 2m / 5m 逐年整張表、事後最好的、用前一年最好的、依年初價格換算 |
| `tf_years.py` | 同一套 v3 規則套到 NQ 1 / 2 / 3 / 5 分 K，趨勢 + MIX / 只有趨勢 / 只有 MIX × 1R / 2R / 3R，五年逐年 |
| `stop_target.py` | v3（NQ 2m）訊號不變，停損改兩根 K 極值 / 固定 15–60 點 / 1.5、2 ATR（只換趨勢或 MIX 也換）× 目標 1 / 1.5 / 2 / 3R，五年逐年 |
| `bad_days.py` | v3（NQ 2m）每天 R 依週幾、美股休市 / 提早收盤 / 休市前後、FOMC、非農、選擇權結算、月底分組；連虧 3 天以上和最差 10% 的日子裡各種日子的比例 |
| `night_stop.py` | 夜盤（美東 09:30–16:00 以外）同一交易日連錯 N 次就停當天夜盤、現金盤照做，N = 1–4，NQ 2m / 5m 五年逐年 |
| `flip_wait.py` | 反向轉來的新趨勢未滿 W 分不做趨勢訊號，NQ 2m / 5m 五年逐年；`groups`：每個趨勢訊號依反向 / 延續、趨勢時間、近幾小時翻轉次數分組 |
| `h1_off.py` | v3 關掉 1h EMA20 同向 / 只做逆 1h 的趨勢訊號，NQ 2m / 5m 五年逐年 |
| `m30_ema.py` | 1h EMA20 同向改用 30m EMA89 / 兩個都同向 / 任一同向，NQ 2m / 5m 五年逐年 |
| `h1_span.py` | 1h 同向過濾用 EMA5–200 / 不過濾，NQ 2m / 5m 五年逐年 |
| `trend_old.py` | Trend Judge 趨勢持續 30–400 分後：多久結束、轉反向的機率、之後的走勢、先逆 5 ATR 的比例，NQ 2m 五年 |
| `recent.py` | v3 最近幾個月（預設 2026-07-19 起）每月 R，NQ 2m / 5m 分現金盤 / 夜盤，NQ RTH 1m |
| `gex_night.py` | v3 每筆單（含夜盤）對照當時 QQQ gamma flip（ZeroGEX 每小時，2026-06-29 起）：朝 flip 走 / 離開，NQ 2m / 5m |
| `gex_regime.py` | v3 2m / 5m、NQ RTH 1m 的單按 Short / Long gamma（NQ 在 QQQ flip 下 / 上）× 買賣分組，2026-06-29 起 |
| `gex_both.py` | SPY / QQQ net GEX 都 Long / 都 Short / 不一致，門檻 0 / ±1B / ±2B，v3 2m、NQ RTH 1m，2026-06-29 起 |
| `gex_gap.py` | GEX setup 按開盤跳空大小、大高開 / 大低開、順跳空 / 回補、第一小時分組 |
| `gex_day.py` | 用 TradingView 匯出的 NQ 1 分 K 接在 Databento 後面，重跑某一天的 GEX setup（ZeroGEX 每分鐘 flip），對照匯出裡的 🧲 |
| `gex_lunch.py` | GEX setup 在台北 00:00–01:05 的訊號：每筆附當天 K 線、flip、停損目標的網頁（樣板 `gex_lunch_template.html`） |
| `trend_cap.py` | v3 趨勢時間上限 120 / 180 / 240 / 300 / 400 / 不限，NQ 2m / 5m 五年逐年＋最近 3 個月 |
| `risk_atr.py` | v3 2m 停損門檻 0.8 / 1 / 1.2 / 1.5 ATR，或不到 X ATR 就把停損放大到 X ATR 照做 |
| `junk_time.py` | 垃圾時間（美東 12:00–13:05）趨勢訊號和 MIX 都不做，NQ 2m / 5m 五年逐年 |
| `breakeven.py` | v3 保本停損：賺到 1 / 1.5 / 2R 後移到保本，或 2 / 2.5R 鎖 1R，NQ 2m / 5m 五年逐年 |
| `fast_dist.py` | v3 距離條件：離 15 秒慢線 vs 離 5 秒快線（ATR），NQ 2m / 5m 五年逐年＋依距離分組 |
| `fixed_points.py` | v3 訊號改用固定停損 60 點、目標 50 / 100 點（只換趨勢單或連 MIX），以點數比較 |
| `reentry.py` | 被停損後 N 根內趨勢沒變、收回進場價就再進場一次（兩根 K 停損或原停損），NQ 2m / 5m 五年逐年 |
| `partial50.py` | 兩口單：+30 / 50 / 70 點先出一口，另一口照 v3 或移到保本，NQ 2m / 5m 點數比較 |
| `hit_rates.py` | 各做法（NQ 2/3/5m 趨勢、MIX、NQ RTH、GEX setup）停損前先到 1 / 1.5 / 2 / 3R 的比例 |
| `daily_sma5.py` | 趨勢 / MIX 不逆日線 SMA5（價格在上下、斜率、兩者），NQ 2m / 5m 五年逐年勝率和 R |
| `line_only.py` | 趨勢訊號不用 Trend Judge 門檻，改只看 5s / 15s 線（位置、斜率、快慢線同側），NQ 2m / 5m 五年逐年 |
| `slow_side.py` | Remi 的 15s 規則：超過 15s 線的趨勢訊號，同一段趨勢裡先有 15s 內的單被停損才做，NQ 2m / 5m 五年逐年 |
| `avoid_window.py` | 避開某段時間（台北 / 美東 03:00–07:00）不進場，NQ 2m / 5m 五年逐年，和這段自己的結果 |
| `open_gap.py` | Globex 18:00 開盤跳空、第一根反向收（低開收紅 / 高開收黑）做反向，依缺口大小、週日、收回幅度分組 |
| `rth_open_gap.py` | 美股 09:30 開盤跳空、第一根（1m / 2m）反向收：低開高走做多 / 高開低走做空，依缺口大小、各年 |
| `qqq_2m.py` | QQQ 2 分 K（NQ 美股盤代替）套 NQ 2m / ETF 規則，趨勢 / 加 MIX、3R / 1R，對照 NQ RTH 1m |
| `mix_stop.py` | MIX 突破換比較近的停損（0.4H、0.3H、1 / 1.5 ATR），目標照 R 或維持原價，NQ 2m / 5m 每年勝率和點數 |
| `mix_sma5_dist.py` | 5m MIX 突破依離日線 SMA5 的距離分組（順 / 逆日線），1R / 2R 命中和每筆 R |
| `scale_in.py` | 分批進場：第一口訊號進、第二口等回檔 0.25 / 0.5 / 0.75R，或兩口都等回檔，NQ 2m / 5m 點數和勝率 |
| `early_cut.py` | 回檔到 0.25 / 0.5 / 0.75R 的單後來怎麼結束，和回檔到 X R 就先出場的回測，NQ 2m / 5m |
| `tj_params.py` | Trend Judge EMA 長度、快 / 慢秒數換其他組合（門檻按趨勢時間比例換算），NQ 2m / 5m 五年逐年 |
| `orb_filter.py` | 開盤 30 分鐘區間（Globex 18:00 / 美股 09:30）的方向、ORH / ORL、中線當 v3 過濾，NQ 2m / 5m 五年逐年 |
| `th_sweep_now.py` | 現在的 v3 規則下 Trend Judge 門檻 6–12 點，NQ 2m / 5m 五年逐年 |
| `rth_stage.py` | NQ RTH 1m（QQQ 做法）原版訊號階段 15–60 × EMA 5 / 8 / 13，五年逐年；`nojunk` 不套垃圾時間 |
| `rth_dip.py` | QQQ（NQ 美股盤 1m）強上升趨勢中買回檔：回到 15s 慢線掛買、回檔 2 / 3 ATR 後第一根收紅買，對照強下降賣反彈 |
| `rth_strong_stage.py` | NQ RTH 1m 強勢（> 40）時另外做階段 15–30 的訊號，五年逐年 |
| `qqq2m_sell_gamma.py` | QQQ 2m (20, 0, 11, 1) 賣訊按 Short / Long gamma、加 Trend Judge / 1h 空方分組，1 / 1.5 / 2 / 3R 命中 |
| `v3_failure.py`、`v3_kline.py` | 前幾年怎麼虧的圖：出場方式、停損前走多遠、時段（`v3_failure.html`）；虧最多的日子的 K 線和進出場（`v3_kline.html`） |
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
