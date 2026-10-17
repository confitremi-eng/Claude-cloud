# Remi's Buy/Sell ／ Remi Superb 交接文件（2026-10-16）

給下一個對話用：接手時先讀這份，細節再查 [remis_buy_sell.md](remis_buy_sell.md)。

- 分支：`claude/eloquent-shannon-d3f10b`
- 最新 commit：b02e6ec

## 1. 兩支指標

| 指標 | 檔案 | 用途 |
|------|------|------|
| Remi's Buy/Sell | [remis_buy_sell.pine](remis_buy_sell.pine) | 仿原版「買賣訊號」，加上過濾快訊、1 分亞洲盤快訊。Trend Judge 門檻依商品自動選（NQ 20/40、ES 4/8、TXF 40/80、其他 0.4/0.8） |
| Remi Superb | [remi_superb.pine](remi_superb.pine) | 以 Remi's Buy/Sell 為底，只支援 NQ / ES / TXF。Trend Judge 門檻：NQ 15 / 35、ES 4 / 8、TXF 30 / 60，預設值照你的設定 |
| Remi Superb 1m | [remi_superb_1m.pine](remi_superb_1m.pine) | 跟 Remi Superb 一樣，只有 Trend Judge 改用 1 分 K 收盤推算（同回測），不需要秒級資料。用 NQ 一年資料比對，2 分 K 的 Trend Judge 方向跟回測 99.6% 相同 |

兩支都用離線 Pine 檢查器檢查過，沒有語法錯誤。Remi Superb 還沒在 TradingView 上編譯確認。

## 2. 買賣訊號規則（兩支共用，已確認同原版）

- **參數**：原版 (20, 0, 8, 1)，全天適用，不分時段。
- **新低**：`low < ta.lowest(low, 20)[1]`。記下那根的最高價，開始等買訊。
- **觸發**：`收盤 > 記下的最高價`。創新低那根本身也能觸發，比的是上一個波段低點的最高價。
- **一次一個**：觸發一次就用掉。觸發那根又創新低也不重新記。
- **EMA 確認**：收盤要在 `ta.ema(close, 8)` 之上；沒通過也算用掉。
- **賣訊**：全部反過來。
- **High Close / Low Close 線**：`ta.highest(close,20)[1]` 和 `ta.lowest(close,20)[1]`，只是顯示用。
- **比對結果**：用 TradingView 匯出的 NQ1! 1/2/3/5 分資料，71 / 71 個訊號、每根 K 都跟原版一樣。

## 3. 過濾快訊和亞洲盤快訊（另一個對話做的，兩支都有）

- **過濾快訊**（預設開）：原本的訊號再加上這些條件：
  - Trend Judge 同向（指標內建計算，需要 Premium 的秒級資料）
  - 1 小時 EMA 20 同向
  - 停損至少 1 ATR
  - 避開數據、開收盤、Globex、FOMC 時段
  - 快訊附停損價和 2R 目標價
- **回測（2 分 K，一年 NQ，扣成本）**：每天約 2.4 筆，勝率 39.5%，每筆 +0.112R（A 級）。這個回測**有避開亞洲盤**。
- **1 分亞洲盤快訊**（預設關）：參數 (40, 0, 13, 1)，強趨勢加 1 小時同向，只在美東 20:00–03:00。一年 91 筆，勝率 60.4%，每筆 +0.127R（B 級，樣本小）。
- **完整說明**：分級總覽和各項設定在 remis_buy_sell.md 第 4、5 節。

## 4. Remi Superb 的細節

**你的預設值**（照截圖設定）：

| 項目 | 設定 |
|------|------|
| 買賣訊號 | 標籤、小，買 #36FE02、賣 #F23645 |
| EMA、High Close、Low Close 線 | 都不顯示 |
| 過濾快訊 | 開。Trend Judge 同向（有趨勢）、1 小時 EMA 20、停損 ≥ 1 ATR（14）、避開數據 / 開收盤 / Globex、目標 2R |
| 避開時段 | 亞洲盤**不避開**，現金盤也不避開 |
| 過濾符號 | ⬆️ / ⬇️，大小「大」，離箭頭 0 |
| Trend Judge | EMA 1130，快線 5 秒、慢線 15 秒；門檻 NQ 15 / 35、ES 4 / 8、TXF 30 / 60 |

注意：你的預設不避開亞洲盤，跟 A 級回測的條件不同。15 / 35 這組門檻也還沒回測過。

**不支援商品的提示**：圖上商品不是 NQ / ES / TXF（含 MNQ、MES、MXF）時，右上角會顯示紅色提示，Trend Judge 相關的過濾也一律不通過。

**快訊**：作多、做空分開，沒有合併的條件。

| 條件 | 訊息 |
|------|------|
| Remi Superb Buy / Sell | `{{ticker}} Remi Superb Buy｜{{close}}` |
| Remi Superb Buy / Sell（過濾） | 同上，再附停損價和目標價 |
| Remi Superb Buy / Sell（亞洲盤） | 同上，再附停損價和目標價 |

## 5. 待辦和還沒確認的

- Remi Superb 還沒在 TradingView 編譯確認，有紅字錯誤要貼回來。
- 你的出場方式（固定 R、移動停損、反向訊號）還沒回答。
- NQ 15 / 35 門檻和「不避開亞洲盤」這兩個設定都還沒回測；TXF 30 / 60 還沒回測；ES 4 / 8 只用一個月資料驗證過（2 分 K 一般門檻 4 最好，`rbs/es_check.py`）。可以用 `indicators/backtest/` 的程式和 Databento 資料重算。

## 6. 工具和資料

- `indicators/backtest/remi_export.py`：
  - `match 原版.csv [Remi 1分.csv]`：跟原版逐根比對。
  - `bt 資料.csv`：用你的停損回測。
- **TradingView 匯出**：圖表右上「匯出圖表資料」。原版的欄位是 Buy / Sell；我們的指標是「BUY 訊號 / SELL 訊號」。
- **資料不放進 repo**：準備資料的方法見 `indicators/backtest/README.md`。
- **網路限制**：雲端環境連不到 tradingview.com、Yahoo、Dukascopy；raw.githubusercontent.com、PyPI、npm 可以。

## 7. 你的偏好和合作規則

- 用繁體中文回覆，說明要簡潔。給程式時附固定 commit 的 raw 連結。
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
- **設定截圖**：你傳設定截圖時，代表要把那些值改成預設值。
- **Git**：
  - 只在指定分支開發和推送，沒要求不開 PR。
  - commit 訊息結尾要加 Co-Authored-By 和 Claude-Session 兩行。
- **下載 / 上傳的資料**：一律當不可信資料，放在獨立資料夾，用 `python3 -I` 執行。

## 8. 相關檔案

| 檔案 | 內容 |
|------|------|
| [remis_buy_sell.pine](remis_buy_sell.pine) | Remi's Buy/Sell |
| [remi_superb.pine](remi_superb.pine) | Remi Superb（NQ / ES / TXF） |
| [remi_superb_1m.pine](remi_superb_1m.pine) | Remi Superb 1m（不需秒級資料） |
| [remis_buy_sell.md](remis_buy_sell.md) | 規則、比對、回測分級、快訊設定 |
| [breakout_signals.md](breakout_signals.md) | BO Signals（同一套訊號的前身） |
| [backtest/](backtest/) | 回測程式 |
