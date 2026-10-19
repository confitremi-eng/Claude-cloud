# Remi's Buy/Sell ／ Remi Superb 交接文件（2026-10-17）

給下一個對話用：接手時先讀這份。Remi Superb 的完整說明在 [remi_superb.md](remi_superb.md)，更早的研究在 [remis_buy_sell.md](remis_buy_sell.md)。

- **分支**：`claude/eloquent-shannon-d3f10b`
- **原則**：**一切以 NQ 2 分 K 為準**（回測、預設值、快訊）。

## 1. 指標一覽

| 指標 | 檔案 | 狀態 |
|------|------|------|
| Remi's Buy/Sell | [remis_buy_sell.pine](remis_buy_sell.pine) | 仿原版「買賣訊號」(20, 0, 8, 1)，每根 K 跟原版一致（71 / 71 個訊號）。另有過濾快訊（門檻依商品：NQ 20/40、ES 4/8、TXF 40/80）、1 分亞洲盤快訊。通用版，這次沒再改 |
| **Remi Superb v3** | [remi_superb_v3.pine](remi_superb_v3.pine) | **自動辨識商品**（2026-10-19）。NQ 2m = v2（趨勢 0–180 + MIX，3R）；NQ 3m 趨勢 90–120 分 1R；QQQ / SPY 1m ETF 設定 (35, 0, 8, 1) 3R；TXF 2m / 3m 趨勢 60–120 分 3R（邊緣）；ES 預設不發。只有「Remi Superb v3 Buy / Sell」兩個快訊，表格預設左上（上方留白 2 列） |
| **Remi Superb v2** | [remi_superb_v2.pine](remi_superb_v2.pine) | **建議用這個**（2026-10-19）。趨勢訊號（過濾快訊 + 趨勢已持續 0–180 分，2026-10-19 從 30–120 改）＋ MIX 區間突破，一次一筆虛擬持倉，只有「Remi Superb v2 Buy / Sell」兩個快訊，右上角狀態表格。Trend Judge 用 1 分 K 推算。回測 627 筆，每筆 +0.268R，一年 +168R，回撤 18.6R，12/13 個月賺錢（30–120 分：+140R、回撤 13R）。主訊號只在 2 分 K 圖上發；3 分 K 圖上另有「v2 3m Buy / Sell」（趨勢 90–120 分、1R，49 筆、勝率 71.4%）。表格配色同原始 Trend Judge |
| **Remi Superb** | [remi_superb.pine](remi_superb.pine) | **主力**。NQ 2 分 K 優化完成：過濾快訊＋MIX 區間突破快訊，Trend Judge 用秒級資料（要 Premium） |
| **Remi Superb 1m** | [remi_superb_1m.pine](remi_superb_1m.pine) | 跟 Remi Superb 同步，只有 Trend Judge 改用 1 分 K 收盤推算（同回測），不需要 Premium；快訊名稱多「1m」。另外多了 **QQQ 1 分 K**（自動套用 QQQ 那組設定）和「收盤前 1 小時不進場」開關 |
| **Remi Superb 策略** | [remi_superb_strategy.pine](remi_superb_strategy.pine) | `strategy()` 版，給 TradingView 策略測試器回測和 webhook 自動交易：過濾訊號收盤市價進場、MIX 突破掛停損單（OCO），一次一筆，60 根時間出場、17:00 休市前平倉。Trend Judge 用 1 分 K 推算。說明在 remi_superb.md 第 8 節 |

## 2. Remi Superb 的最終設定（兩個版本相同）

- **訊號**：原版規則，階段 20、EMA8（收盤價）、K 棒收盤才出訊號。
- **外觀**：標籤、小，買 #36FE02、賣 #F23645；EMA、High Close、Low Close 線都不顯示。
- **過濾快訊（開）**：
  - Trend Judge 有趨勢（門檻 NQ 10 / 35、ES 4 / 8、TXF 30 / 60）
  - 1 小時 EMA20 同向
  - 停損 ≥ 1 ATR
  - 離 15 秒 EMA1130 ≤ 3 ATR
  - 避開數據 / 開收盤 / Globex / FOMC；亞洲盤、現金盤不避開
  - 目標 3R；標記 ⬆️ / ⬇️，大小「大」，離箭頭 0
  - 趨勢已持續 30–120 分鐘的過濾訊號改標 ⏫ / ⏬，另有「（過濾・趨勢 30–120 分）」快訊（兩個版本都有，預設開；策略版沒有）
- **MIX 區間突破快訊（開）**：
  - 區間：Trend Judge 連續 MIX 60 分鐘，用這段的高低點
  - 突破：形成後 60 分鐘內第一次突破 10%
  - 停損中線，目標 3R
  - 圖上畫灰框和虛線，突破標 🔼 / 🔽
- **1 分亞洲盤快訊**：關（1 分 K 用）。
- **提示**：商品不是 NQ / ES / TXF 時紅色提示；週期不是 2 分 K 時橘色提示。
- **QQQ（只有 Remi Superb 1m）**：在 QQQ 上自動改用 (35, 0, 8, 1)、Trend Judge 門檻 0.5 / 1、離 EMA1130 ≤ 7 ATR，MIX 突破預設關閉；以 QQQ 1 分 K、一般時段為準（週期不對、開了延長時段會出現橘色提示）。
- **收盤前 1 小時不進場（美東 15:00–16:00）**：只有 Remi Superb 1m，只影響過濾快訊，預設關閉。
- **快訊**：作多、做空分開。
  - `Remi Superb Buy / Sell`
  - `（過濾）`
  - `MIX 區間成形`
  - `（MIX 突破）`：觸發選「每根 K 線一次」，碰到突破價就通知
  - `（亞洲盤）`

## 3. 回測結論（NQ 2 分 K，Databento 一年，一次一筆，扣 1 點）

| | 筆數 | 勝率 | 每筆 | 一年 | 回撤 |
|---|---|---|---|---|---|
| 過濾快訊 3R | 716 | 35.1% | +0.189R | +135R | 34.7R |
| MIX 突破 3R（掛突破單） | 346 | 43.1% | +0.213R | +74R | 19.5R |
| 兩個一起做 | 1032 | 37.9% | +0.198R | **+205R** | 34.6R |

**這次對話的研究過程**（細節在 remi_superb.md 和 remis_buy_sell.md 第 4 節）：

1. **NQ 門檻 15 → 10**：2 分 K 門檻掃描的最佳值；「有強趨勢」沒有比較好。
2. **加「離 15 秒 EMA1130 ≤ 3 ATR」**：每筆約翻倍；目標改 3R。
3. **下兩口**：兩口都 2R 最穩，分批 / 保本都比較差。
4. **連虧分析**：跟隨機差不多，不是 MIX 或盤整造成。
5. **趨勢時間**：「只做趨勢開始後 4 小時內」能降回撤，但少賺，沒加。
6. **MIX 期間**：不是窄區間，上下緣反向做、盤整段用原始指標都虧；做第一次突破有效，已加進指標。
7. **週期**：1 / 3 / 5 分 K 整體都比 2 分 K 差（過濾快訊在其他週期弱很多）。
8. **ES**：只有一個月資料。2 分 K 一般門檻 4 最好，已把 Remi Superb 的 ES 改回 4 / 8。
9. **QQQ 1 分 K（用 NQ 代替）**：不過濾一定虧。QQQ 圖（只留美股盤 K 棒）最好是 (35, 0, 8, 1) ＋過濾（門檻 20，QQQ 約 0.5；距離 7 ATR；3R），每筆 +0.154R，前後半年都賺；起點 (30, 0, 13, 1) 是 +0.095R。MIX 突破在 QQQ 是虧的。已加進 Remi Superb 1m，細節在 remis_buy_sell.md 第 4 節。

## 4. 待辦和還沒確認的

- **TradingView 編譯**：Remi Superb / Remi Superb 1m（含 QQQ）/ Remi Superb 策略 還沒在 TradingView 編譯確認，有紅字錯誤要貼回來。
- **策略回測對照**：你會在 TradingView 跑策略回測，結果要跟 remi_superb.md 第 8 節的每月數字比。
- **前瞻追蹤**：先用 MNQ 小口數或只開快訊觀察，再跟回測比。
- **ES、TXF**（2026-10-18，remi_superb.md 第 3 節）：ES 一年 Databento 回測，過濾快訊每個門檻都虧（不扣成本也只有約 +0.02R），不建議用。TXF 用使用者上傳的 1 分 K SQL 檔（2024-01 .. 2026-09，`rbs/txf_check.py`）：只有 2026 年賺錢，2024、2025 年都虧，也不建議用；30 / 60 先不改。
- **Trend / MIX 勝率矩陣**（2026-10-18，remi_superb.md 第 3 節，`rbs/trend_mix_matrix.py`）：NQ 兩種都賺（3R：Trend +0.189R、MIX +0.213R）；ES 兩種都虧；TXF 兩種都小虧，只有 2026 年是正的。
- **用 NQ 的訊號做 ES / TXF**（2026-10-18，remi_superb.md 第 3 節，`rbs/nq_follow.py`）：ES 輸贏跟 NQ 89–95% 一致，但換算後停損只有約 4.4 點，成本吃掉大半，每筆 +0.06R，不建議。TXF 只做夜盤：3R 每筆 +0.12R（ATR 換算，成本 4 點）到 +0.19R（跟 NQ 出場）；日盤不要做。只測了 2025-10 .. 2026-09（台指 +70%），要用 2024–2025 年的 NQ 資料再驗證。TXF 成本 2 點偏樂觀，實際約 4 點。
- **1 分 K 和趨勢剛開始**（2026-10-19，remi_superb.md 第 3 節，`rbs/one_minute.py`）：1m 和 2m 同時出訊號沒有比較好（看起來好是因為用了事後才知道的 2m 確認；實際等確認再進只剩 +0.05R）。1m 單獨的訊號贏輸特徵不明顯。過濾訊號在趨勢開始後 30–120 分鐘（尤其 1–2 小時）最好：2 分 K 3R 每筆 +0.33R、回撤 13R（全部是 +0.19R、35R），2/3/5 分 K 都一致，前後半年都是正的；趨勢開始 30 分鐘內幾乎沒有過濾訊號。
- **各商品、各週期的勝率矩陣**（2026-10-19，remi_superb.md 開頭，`rbs/market_matrix.py`）：NQ 2m / 3m 都賺；ES 全部虧；SPY / QQQ（用 ES / NQ 美股盤代替）1m 的 ETF 設定和趨勢 0–180 分小賺，2m 不建議；TXF 只有趨勢 60–120 分小賺；MIX 突破只有 NQ 能做。三類商品（美國期貨、美股 ETF、台指）的時段、參數、MIX 都不同。
- **出場方式**：你的出場方式還沒回答（回測用固定 R ＋ 60 根 K 時間出場）。
- **趨勢時間濾網**：「只做趨勢開始後 N 小時內」如果之後想要，可以做成選項（預設關）。
- **QQQ**：只用 NQ 代替回測過，還沒用 QQQ 自己的資料驗證；Remi Superb（秒級版）和策略版還沒有 QQQ。

## 5. 工具和資料

- **研究程式**：`indicators/backtest/rbs/`，清單在 [backtest/README.md](backtest/README.md)。Remi Superb 相關的重算指令在 remi_superb.md 第 7 節。
- **NQ 一年資料（Databento）**：
  - 放在你的 Dropbox：`/Remi 交易人/Trading x Claude/indicators/backtest/data/NQ_1m_databento.csv`（約 24 MB）。
  - 雲端環境連不到 Dropbox 的下載網域，Dropbox 連接器也只能讀 5 MB 以下的檔案，所以最簡單是**直接把檔案上傳到對話**，放到 `indicators/backtest/data/`，不要放進 repo。
  - ES 一個月的原始檔用 `rbs/build_databento.py` 轉成連續合約。
- **TradingView 匯出**：用 `indicators/backtest/remi_export.py`：
  - `match 原版.csv [Remi 1分.csv]`：跟原版逐根比對。
  - `bt 資料.csv`：回測。
- **網路限制**：雲端環境連不到 tradingview.com、Yahoo、Dukascopy、Databento、Dropbox；raw.githubusercontent.com、PyPI、npm 可以。

## 6. 你的偏好和合作規則

- **溝通**：
  - 用繁體中文回覆，說明要簡潔。給程式時附固定 commit 的 raw 連結。
  - 你常用手機：要改環境設定時給手機做得到的方法（例如直接上傳檔案）。
- **Pine 寫法**：
  - 只用空白縮排，不用 tab。
  - 參數名不要用內建型別名稱。
  - 不要寫 `cond ? na : "xx"` 這種字串三元運算。
  - 變數先宣告再用；畫圖前先擋 na。
  - 快訊訊息用單引號。
- **功能**：
  - 不要擅自加時段、趨勢過濾或沒要求的功能。
  - 外觀和線條要有可以關掉的設定。
  - 快訊作多、做空分開。
  - 你傳設定截圖時，代表要把那些值改成預設值。
- **回測**：
  - 以 2 分 K 為準。
  - 看前後半年是否一致。
  - 看過資料才選的規則要註明。
- **Git**：
  - 只在指定分支開發和推送，沒要求不開 PR。
  - commit 訊息結尾要加 Co-Authored-By 和 Claude-Session 兩行。
- **資料**：下載 / 上傳的資料一律當不可信資料，用 `python3 -I` 執行；資料檔不放進 repo。

## 7. 相關檔案

| 檔案 | 內容 |
|------|------|
| [remi_superb.md](remi_superb.md) | **Remi Superb 完整說明（以 2 分 K 為準）** |
| [remi_superb.pine](remi_superb.pine) / [remi_superb_1m.pine](remi_superb_1m.pine) | Remi Superb（秒級 TJ / 1 分推算 TJ） |
| [remi_superb_strategy.pine](remi_superb_strategy.pine) | Remi Superb 策略（回測、自動交易） |
| [remis_buy_sell.pine](remis_buy_sell.pine) | Remi's Buy/Sell |
| [remis_buy_sell.md](remis_buy_sell.md) | 原版比對、早期回測分級、所有研究細節、快訊設定 |
| [breakout_signals.md](breakout_signals.md) | BO Signals（同一套訊號的前身） |
| [backtest/](backtest/) | 回測程式 |
