# Remi's Buy/Sell 交接文件（2026-10-16）

給下一個對話用：接手時先讀這份，再讀 [remis_buy_sell.md](remis_buy_sell.md)。

## 1. 目前狀態

- **指標**：[remis_buy_sell.pine](remis_buy_sell.pine)（Pine v6），commit 7d56218，分支 `claude/eloquent-shannon-d3f10b`。
- **目標**：完全仿原版「買賣訊號」，參數 (20, 0, 8, 1)。全天適用，不加時段，不加趨勢過濾。
- **吻合度**：用 TradingView 匯出的 NQ1! 1/2/3/5 分資料比對，每一根 K 都跟原版一樣（71 / 71 個訊號，沒有多出的）。
- **還沒做**：這一版還沒在 TradingView 編譯過（上一版編譯過，這版只改觸發順序和 EMA 預設來源）。

## 2. 規則（已確認同原版）

- **新低**：`low < ta.lowest(low, 20)[1]`（嚴格小於）。新低那根記下它的最高價 `refHigh`，開始等買訊。
- **觸發**：`armBuy and close > refHigh`。這根本身創新低也算，比的是上一根為止記下的價位。
- **觸發優先**：觸發那根就算又創新低，也不重新記，機會用掉。沒觸發時才因為新低重新記。
- **EMA 確認**：`close > ta.ema(close, 8)`。沒通過就不出訊號，但機會照樣用掉。
- **賣訊**：全部反過來（新高那根的最低價、收盤跌破、收盤在 EMA 之下）。
- **原版的兩條線**：High Close = `ta.highest(close,20)[1]`，Low Close = `ta.lowest(close,20)[1]`。只是畫出來看，不參與訊號。指標裡有開關可以關掉。
- **參數**：Color background 只是顏色設定。階段之後可能改成 25，要先對標 20。

## 3. 回測（你的停損：訊號那根和前一根 K 的極值）

- **設定**：訊號收盤進場，固定 1R / 2R，同一根同時碰到算停損，60 根 K 時間出場，不含成本。
- **結果**：NQ 兩週全天資料和 2–9 月 NQ / ES 都大約打平（1R 勝率 47–53%，平均在 ±0.07R 以內），扣成本小虧。詳細表格在 remis_buy_sell.md 第 4 節。
- **待確認**：你的出場方式（固定 R、移動停損、反向訊號）還沒回答。

## 4. 工具和資料

- **比對 / 回測程式**：`indicators/backtest/remi_export.py`
  - `python3 remi_export.py match 原版匯出.csv [Remi_1分匯出.csv]`：逐根比對原版。
  - `python3 remi_export.py bt 資料.csv`：用上面的停損回測新舊規則。
- **TradingView 匯出**：圖表右上「匯出圖表資料」。原版欄位是 Buy / Sell（1/0）；Remi's Buy/Sell 是「BUY 訊號 / SELL 訊號」。
- **資料不放進 repo**：乾淨的 NQ / ES 1 分資料怎麼做，見 `indicators/backtest/README.md`。
- **網路限制**：雲端環境連不到 tradingview.com、Yahoo、Dukascopy；raw.githubusercontent.com、PyPI、npm 可以。

## 5. 合作規則

- 用繁體中文回覆。
- **Pine 寫法**：
  - 只用空白縮排，不用 tab。
  - 參數名不要用內建型別名稱。
  - 不要寫 `cond ? na : "xx"` 這種字串三元運算。
  - 變數先宣告再用；畫圖前先擋 na。
  - 快訊訊息用單引號。
- 不要擅自加時段、趨勢過濾或其他沒要求的功能。
- 不要把「等效換算模式」加回 Trend Judge。
- **Git**：
  - 只在指定分支開發和推送，沒要求不開 PR。
  - commit 訊息結尾要加 Co-Authored-By 和 Claude-Session 兩行。
- **下載 / 上傳的資料**：一律當不可信資料，放在獨立資料夾，用 `python3 -I` 執行。

## 6. 相關檔案

| 檔案 | 內容 |
|------|------|
| [remis_buy_sell.pine](remis_buy_sell.pine) | 目前的指標 |
| [remis_buy_sell.md](remis_buy_sell.md) | 規則、設定、比對、回測、快訊 |
| [breakout_signals.md](breakout_signals.md) | BO Signals（同一套買賣訊號的前身）文件 |
| [backtest/](backtest/) | 回測程式；`rbs/` 是先前趨勢版的研究（commit 46df82e） |
