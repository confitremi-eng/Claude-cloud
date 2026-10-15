# Trend Judge 指標 — 交接文件

TradingView Pine Script 趨勢判讀指標，給期貨盤中交易使用（NQ / ES / TXF）。
本文件整理至 2026-10-16 為止的需求、設計決策與未完成事項，供另一個對話接手。完整程式碼附在文末「附錄」。

---

## 1. 檔案

| 檔案 | 狀態 | 說明 |
|---|---|---|
| `Trend_Judge_EMA_v2.pine` | **主檔，唯一在用** | 趨勢判讀 + 開盤區間 + 交易矩陣 + 快訊條件 |
| `NQ_Trend_EMA1130.pine` | 舊版，勿改 | 最早期版本，已被主檔取代 |
| `OpeningRange_only.pine` | 參考用 | LuxAlgo OR 精簡版（v6），已移植併入主檔 |
| `Openrange.rtf` | 原始來源 | LuxAlgo "Opening Range with Breakouts & Targets" 原碼 |

- Pine 版本：`//@version=5`（主檔）。OR 原碼是 v6，已改寫成 v5 相容。
- 沒有本地編譯器。修改後由使用者貼到 TradingView 編譯，有紅字錯誤會回貼。
- 主檔放在 repo `confitremi-eng/Claude-cloud` 的 `trend-judge/`。使用者複製程式時請用 GitHub 的「Copy raw file」或下載後用文字編輯器開；從預覽畫面複製曾經被截斷，編譯時出現「could not be translated」或「must contain at least one plot」這類奇怪錯誤。

## 2. 使用情境

- 使用者看 **2 分鐘以上**的圖表，常用分割窗格（一頁多窗格，例如六宮格）。
- 趨勢判斷需要**秒級** EMA 才穩定，所以用 `request.security_lower_tf` 從高週期圖表抓 5S / 15S intrabar 資料（需 TradingView Premium）。
- 指標要和其他「買賣訊號」指標搭配：在 TradingView 快訊的「新增條件」裡，把本指標當**過濾條件**。

## 3. 功能規格

### Part 1 — 趨勢判讀

- 快線：5 秒 EMA 1130；慢線：15 秒 EMA 1130。
- 取每根圖表 K 棒內 intrabar 陣列的最後一個值（`array.last`）作為當下秒級 EMA。
- **每 2 分鐘鎖定一次**差值：`newWindow = ta.change(time("2")) != 0`
- 差值 = 5s EMA − 15s EMA。
- 標的自動偵測（`syminfo.root` 用 `str.contains`）：NQ/MNQ、ES/MES、TXF/MXF。其他標的顯示「不支援此標的」。

| 標的 | 趨勢門檻 | 強勢門檻 |
|---|---|---|
| NQ | 20 | 40 |
| ES | 4 | 8 |
| TXF | 40 | 80 |

五級狀態：

| 差值 | 狀態 | 底色 |
|---|---|---|
| > 強勢門檻 | 強UP | lime |
| > 趨勢門檻 | UP | green |
| 中間 | MIX | orange |
| < −趨勢門檻 | DOWN | red |
| < −強勢門檻 | 強Down | maroon |

另有「自動偵測標的門檻」開關，關閉時改用手動門檻 / 手動強勢門檻。

### Part 2 — 開盤區間（Opening Range）

- 改作自 LuxAlgo，**CC BY-NC-SA 4.0**，程式中的署名與授權標頭必須保留。
- 只保留 OR 本體：ORH / ORL / ORM（虛線）+ 區間框、歷史顯示、方向填色、自訂 session。
- 已移除：突破箭頭、目標價、Session MA、Daily Bias 訊號。
- 區間長度預設 **5 分鐘**（`orTF = "5"`）。
- **計算與繪圖分離**：區間判定永遠執行，`showOR` 只控制畫不畫（否則關掉繪圖會讓建議欄卡在「區間形成中」）。

### Part 3 — 交易矩陣（表格「建議」欄）

趨勢 5 級併成 3 向（強UP/UP → UP，強Down/DOWN → DOWN）× 價格相對 OR 位置（`close` 比 `orh`/`orl`）：

| 趨勢 ＼ 位置 | 站上 ORH | 區間內 | 跌破 ORL |
|---|---|---|---|
| UP | 只做多（green） | 偏多待突破（green 半透明） | 觀望 |
| MIX | 突破待確認（orange） | 觀望 | 跌破待確認（orange） |
| DOWN | 觀望 | 偏空待跌破（red 半透明） | 只做空（red） |

- 「觀望」底色：`color.new(#F9A825, 10)`（金黃，使用者選定）。
- 例外狀態（灰底，刻意和「觀望」區分）：
  - 趨勢未算出 → 「計算中...」
  - OR 區間時段尚未結束 → 「區間形成中」（`orReady` 必須包含 `not or_sesh`）
- 背離格（UP+跌破ORL、DOWN+站上ORH）一律觀望，這是使用者確認過的。

### 表格

列順序（動態排列，有開才佔列，剩餘列清空）：
頂部留白列 → 趨勢 → 建議 → 位置 → 差值 → 強勢（可選）→ 更新於（可選）

### 快訊條件（給其他買賣指標的「新增條件」當過濾用）

數值是**持續狀態**，不是一次性事件。

隱藏 plot（`display=display.data_window`）：
- `趨勢強度`：0=MIX、1=一般、2=強（不分多空）
- `趨勢方向`：2=強UP、1=UP、0=MIX、-1=DOWN、-2=強Down
- `趨勢差值`：鎖定的差值

alertcondition：
- 有趨勢（強度 ≥ 1）、有強趨勢（強度 ≥ 2）
- 多方趨勢 (UP+強UP)、強多 (強UP)、空方趨勢 (DOWN+強Down)、強空 (強Down)
- 多方趨勢+綠K (BUY用)、空方趨勢+紅K (SELL用)：`dirCode >= 1 and close > open` / `dirCode <= -1 and close < open`。給 BUY/SELL 合併成同一條件的訊號指標用，十字線兩邊都不成立
- 強多+綠K (BUY用)、強空+紅K (SELL用)：同上邏輯，門檻改成 `dirCode >= 2` / `dirCode <= -2`（使用者用在 1 分圖快訊）

建議快訊設定：BUY 主條件 + 多方條件、SELL 主條件 + 空方條件，觸發選「每根K棒收盤時一次」。

目前做法（買賣訊號指標只有合併的 `BUY SELL` 條件）：開兩個快訊，`BUY SELL` 以及 `多方趨勢+綠K` → Buy；`BUY SELL` 以及 `空方趨勢+紅K` → Sell。限制：多方趨勢中出現在綠K上的 SELL 訊號仍會觸發 Buy 快訊；出現在紅K上的 BUY 訊號會被濾掉。

## 4. 目前預設值

| 設定 | 預設 |
|---|---|
| Table 位置 | 左上 |
| 字型大小 | 極小 |
| 頂部留白列 | 2 |
| 顯示操作建議 | 開 |
| 顯示強勢門檻欄位 | 關 |
| 顯示更新時間 | 關 |
| 在圖上畫出兩條均線 | 關 |
| 開盤區間長度 | 5 分 |
| 顯示開盤區間 / 歷史區間 / 方向填色 | 開 |

## 5. 設計決策與被否決的方案

- **等效換算模式（免秒級，用時間跨度換算 EMA 長度）**：做過，使用者決定拿掉，不要再加回。
- **跨標的顯示（在 NQ 圖上顯示 ES 趨勢）**：做過一版，使用者回報有問題後刪除，回到單標的版本。未找出具體問題，若要重做先問清楚。
- **ATR 低波動調整門檻**：只有討論（比例縮放、日線 ATR vs OR 寬度），使用者說「不要管」，沒有寫進程式。
- **Table 左下在分割窗格會飄到中間**：Pine 先天限制。overlay 指標的 table 錨定在價格窗格，不是整張圖。最後改成左上 + 頂部留白列 2 避開指標狀態列。
- **快訊**：先做了「進入狀態時觸發一次」→ 使用者說不對；改成「每 2 分鐘回報當下狀態」→ 使用者說是要給其他指標當過濾條件；最後改成持續狀態值 + 分多空的 alertcondition（現行版本）。

## 6. 未完成 / 待確認

1. **買賣訊號指標拆 BUY / SELL**：使用者的另一支指標「買賣訊號 (25, 0, 8, 1)」只有合併的 `BUY SELL` 條件，使用者沒有原始碼。暫以「趨勢+K棒顏色」alertcondition 代替（見 §3 快訊條件）。尚未確認：該指標在快訊條件下拉選單是否有個別的 BUY / SELL plot 可選，有的話可以真正分開。
2. **使用者的快訊設定**：觸發已改為「每根K線收盤時觸發一次」（快訊在 1 分圖）。右上角的橘色驚嘆號，內容待確認。
3. **位置判斷的更新節奏**：趨勢每 2 分鐘鎖定，但 OR 位置用即時 `close`，價格在 ORH/ORL 附近時建議欄會閃動。提過「位置也改成每 2 分鐘鎖定」，使用者尚未決定。
4. **更多矩陣組合**：使用者說「還有很多種組合稍後討論」，尚未展開（例如假突破反手、OR 過窄/過寬時降級）。
5. 強UP 與 UP 在建議欄目前完全等價，強勢分級沒有影響建議輸出（已告知使用者，未要求修改）。
6. **差值在即時 K 棒上沒有真正鎖住**（已告知，使用者未決定）：即時 K 棒上 `ta.change(time("2")) != 0` 整根都成立，`lockedDiff` 每個 tick 跟著變、收盤才定；表格的趨勢/差值盤中會閃。歷史 K 棒用收盤值不重繪，快訊用「每根K線收盤時」不受影響。圖表週期 > 2 分時實際是每根 K 棒更新。可選修法：條件加 `barstate.isconfirmed`，可和第 3 項一起做。
7. **OR 起點**（已告知，待使用者確認圖表設定）：預設用 `session.isfirstbar`，CME 期貨若圖表是完整電子盤時段，起點是美東 18:00 而非 09:30。自訂區間的 `UTC-5` 在夏令時間對應美東 10:30；預設 0930–0945 是 15 分不是 5 分。

## 7. 已知限制

- `security_lower_tf` 有 intrabar 總量上限，5S 只能回溯約一兩個交易日；早期歷史 K 棒顯示「計算中」。
- EMA 1130 需要暖機，且從 intrabar 起點開始算，和使用者在秒級圖上看的官方 EMA 可能有小偏差。
- 標的偵測用 `str.contains`，掛在名稱含 "ES"/"NQ" 的其他商品可能誤判。目前只用這三個標的，沒問題。

## 8. 程式慣例（修改時遵守）

- 縮排只用空白，不用 tab。
- 不要用 `label` 等內建型別名當函式參數名（已踩過，改成 `lbl`）。
- 字串變數不要用 `cond ? na : "xx"` 這種三元式，先宣告 `string x = ""` 再用 if 賦值。
- 變數必須先宣告才能用：表格繪製放在檔尾，因為它要讀 OR 的 `orh`/`orl`/`or_token`。
- 變數宣告順序：Part 1 趨勢 → Part 2 OR → Part 3 矩陣、快訊條件、表格。
- 繪圖物件操作前要防 `na`（`not na(or_bx)`、`not na(h_ln.ln)`）。
- alertcondition 訊息用單引號字串，裡面的 `{{plot("...")}}` 才不用跳脫。
- 修改後至少做靜態檢查：括號配對、無 tab、表格列數上限與 `while r < totalRows` 一致。

## 9. 與使用者合作的方式

- 回覆用**繁體中文**。
- 使用者交易經驗豐富，不需要解釋基本交易概念。
- 只改被要求的部分，其他預設值不要動。小修改直接改、直接給檔案，簡短說明即可。
- 使用者要求「回到某版本」時照做，不要追問理由。
- 有設計上的取捨或風險時，簡短提出讓使用者決定，不要自行加功能。

---

## 附錄：完整程式碼 `Trend_Judge_EMA_v2.pine`

編譯成功的版本（390 行，含 10 個 alertcondition）。

```pine
//@version=5
indicator("Trend Judge — 5s/15s EMA Spread + Opening Range", overlay=true, max_lines_count=500, max_labels_count=500, max_boxes_count=500)

// =====================================================================
//  Part 1 — Trend Judge (5s/15s EMA Spread)
// =====================================================================

// ========= 計算參數 =========
emaLen   = input.int(1130, "EMA 長度", group="計算")
fastSec  = input.int(5,  "快線秒數", group="計算")
slowSec  = input.int(15, "慢線秒數", group="計算")
autoMode = input.bool(true, "自動偵測標的門檻", group="計算")

// ---- 趨勢門檻 ----
thNQ  = input.float(20.0, "NQ 門檻 (點)",  group="趨勢門檻")
thES  = input.float(4.0,  "ES 門檻 (點)",  group="趨勢門檻")
thTXF = input.float(40.0, "TXF 門檻 (點)", group="趨勢門檻")
thMan = input.float(20.0, "手動門檻 (關閉自動時使用)", group="趨勢門檻")

// ---- 強勢門檻 (手動輸入) ----
stNQ  = input.float(40.0, "NQ 強勢門檻 (點)",  group="強勢門檻")
stES  = input.float(8.0,  "ES 強勢門檻 (點)",  group="強勢門檻")
stTXF = input.float(80.0, "TXF 強勢門檻 (點)", group="強勢門檻")
stMan = input.float(40.0, "手動強勢門檻 (關閉自動時使用)", group="強勢門檻")

// ---- 顯示 ----
tablePos  = input.string("左上", "Table 位置", options=["右上","右下","左上","左下"], group="顯示")
fontSize  = input.string("極小", "字型大小", options=["極小","小","普通","大","極大","自動"], group="顯示")
showStr   = input.bool(false, "顯示強勢門檻欄位", group="顯示")
showTime  = input.bool(false, "顯示更新時間", group="顯示")
showAdv   = input.bool(true,  "顯示操作建議", group="顯示")
topPad    = input.int(2, "頂部留白列 (避開指標名稱,左上時用)", minval=0, maxval=5, group="顯示")
plotLines = input.bool(false, "在圖上畫出兩條均線", group="顯示")

// ========= 標的自動偵測 =========
root  = syminfo.root != "" ? syminfo.root : syminfo.ticker
isNQ  = str.contains(root, "NQ")
isES  = str.contains(root, "ES")
isTXF = str.contains(root, "TXF") or str.contains(root, "MXF")
supported = isNQ or isES or isTXF

autoTh    = isNQ ? thNQ : isES ? thES : isTXF ? thTXF : na
threshold = autoMode ? autoTh : thMan

autoSt    = isNQ ? stNQ : isES ? stES : isTXF ? stTXF : na
strongTh  = autoMode ? autoSt : stMan

// ========= 秒級 EMA =========
// 圖表可掛在 2 分鐘以上,以 security_lower_tf 取得秒級 intrabar 的 EMA
fArr = request.security_lower_tf(syminfo.tickerid, str.tostring(fastSec) + "S", ta.ema(close, emaLen))
sArr = request.security_lower_tf(syminfo.tickerid, str.tostring(slowSec) + "S", ta.ema(close, emaLen))

var float maFast = na
var float maSlow = na
if array.size(fArr) > 0
    maFast := array.last(fArr)
if array.size(sArr) > 0
    maSlow := array.last(sArr)

// ========= 每 2 分鐘更新一次差值 =========
var float lockedDiff   = na
var int   lastCalcTime = na

newWindow = ta.change(time("2")) != 0
if newWindow and supported and not na(maFast) and not na(maSlow)
    lockedDiff   := maFast - maSlow      // 快 − 慢 = 5s EMA − 15s EMA
    lastCalcTime := time

// ========= 判斷狀態 =========
// 分級: 強勢 > 一般 > MIX
//   diff >  強勢門檻   -> 強UP
//   diff >  趨勢門檻   -> UP
//   |diff| <= 趨勢門檻 -> MIX
//   diff < -趨勢門檻   -> DOWN
//   diff < -強勢門檻   -> 強Down
string state = na
color  bgCol = color.gray
if not na(lockedDiff) and not na(threshold)
    hasStrong = not na(strongTh)
    if hasStrong and lockedDiff > strongTh
        state := "強UP"
        bgCol := color.new(color.lime, 0)
    else if lockedDiff > threshold
        state := "UP"
        bgCol := color.new(color.green, 0)
    else if hasStrong and lockedDiff < -strongTh
        state := "強Down"
        bgCol := color.new(color.maroon, 0)
    else if lockedDiff < -threshold
        state := "DOWN"
        bgCol := color.new(color.red, 0)
    else
        state := "MIX"
        bgCol := color.new(color.orange, 0)

// ========= 畫線 (可選) =========
plot(plotLines ? maFast : na, "快線", color=color.aqua, linewidth=1)
plot(plotLines ? maSlow : na, "慢線", color=color.orange, linewidth=1)

// (表格顯示已移至檔案結尾,以便同時取用 OR 的 orh/orl/or_token)


// =====================================================================
//  Part 2 — Opening Range
//  改作自 "Opening Range with Breakouts & Targets [LuxAlgo]"
//  © LuxAlgo — CC BY-NC-SA 4.0
//  https://creativecommons.org/licenses/by-nc-sa/4.0/
//  僅保留 OR 本體(ORH/ORL/ORM + 區間框),已移植為 v5 相容。
// =====================================================================

// ========= OR 參數 =========
showOR   = input.bool(true, "顯示開盤區間", group="開盤區間")
showHist = input.bool(true, "顯示歷史區間", group="開盤區間", tooltip="顯示過去每個 session 的開盤區間")
orTF     = input.timeframe("5", "區間長度", group="開盤區間", tooltip="決定開盤區間的時間長度,預設 5 分")
biasTog  = input.bool(true, "區間方向填色", group="開盤區間", tooltip="依當前 OR 中線是否高於/低於前一 session 中線,填綠/紅")

// 自訂區間
crTog  = input.bool(false, "", inline="Custom", group="自訂區間")
crSesh = input.session("0930-0945", "", inline="Custom", group="自訂區間")
orTz   = input.string("UTC-5", "", inline="Custom", group="自訂區間", options=["UTC-10","UTC-8","UTC-7","UTC-6","UTC-5","UTC-4","UTC-3","UTC+0","UTC+1","UTC+2","UTC+3","UTC+3:30","UTC+4","UTC+5","UTC+5:30","UTC+5:45","UTC+6","UTC+6:30","UTC+7","UTC+8","UTC+9","UTC+9:30","UTC+10","UTC+11","UTC+12","UTC+12:45","UTC+13"])

// OR 樣式
orColor     = input.color(#787b86, "   區間線顏色", group="開盤區間樣式", inline="Range")
orFillColor = input.color(color.new(color.gray,60), "區間框顏色", group="開盤區間樣式", inline="Range")
orGreenFill = input.color(color.new(#089981,80), " 多方填色", group="開盤區間樣式", inline="Bull")
orRedFill   = input.color(color.new(#f23645,80), "空方填色", group="開盤區間樣式", inline="Bear")
orTxtSizeIn = str.lower(input.string("Small", "區間文字大小", options=["Tiny","Small","Normal","Large","Huge"], group="開盤區間樣式"))

orInvis = color.rgb(0,0,0,100)

// ========= OR 型別 =========
type orLevel
    line ln
    label lab

// ========= OR 變數 =========
var bool  or_sesh  = false
var bool  or_token = false
var float orh      = na
var float orl      = na
var float prev_orm = na
var box   or_bx    = na
var int   day_dir  = 0

var orLevel h_ln = orLevel.new(na, na)
var orLevel l_ln = orLevel.new(na, na)
var line    m_ln = na

// ========= OR 計算 =========
orm = math.avg(orh, orl)

// 註:區間判定「永遠」執行,不受 showOR 影響,
//     showOR 只控制是否繪製;否則關閉繪圖會導致建議欄永遠停在「區間形成中」。
new_or_tf = ta.change(time(orTF)) != 0
if crTog
    or_sesh := not na(time(timeframe.period, crSesh, orTz))
else
    if session.isfirstbar
        or_sesh := true
    else if not session.isfirstbar and new_or_tf
        or_sesh := false

or_start = or_sesh and not or_sesh[1]
or_end   = or_sesh[1] and not or_sesh

// session 開始
if or_start
    if not showHist
        box.delete(or_bx)
        line.delete(h_ln.ln)
        line.delete(l_ln.ln)
        line.delete(m_ln)
    label.delete(h_ln.lab)
    label.delete(l_ln.lab)

    orh := high
    orl := low
    prev_orm := orm[1]
    or_token := false

    if showOR
        or_bx := box.new(bar_index, high, bar_index, low, bgcolor=orFillColor, border_width=0)

// session 進行中
if or_sesh
    if high > orh
        orh := high
    if low < orl
        orl := low
    if showOR and not na(or_bx)
        box.set_top(or_bx, orh)
        box.set_bottom(or_bx, orl)
        box.set_right(or_bx, bar_index)
    if orh != orl
        or_token := true

// session 結束 — 畫出 ORH/ORL/ORM
if or_end and or_token and showOR
    h_ln := orLevel.new(line.new(bar_index, orh, bar_index, orh, color=orColor), label.new(bar_index, orh, text="ORH", tooltip=str.tostring(orh, format.mintick), style=label.style_label_left, color=orInvis, textcolor=color.new(orColor,0), size=orTxtSizeIn))
    l_ln := orLevel.new(line.new(bar_index, orl, bar_index, orl, color=orColor), label.new(bar_index, orl, text="ORL", tooltip=str.tostring(orl, format.mintick), style=label.style_label_left, color=orInvis, textcolor=color.new(orColor,0), size=orTxtSizeIn))
    m_ln := line.new(bar_index, orm, bar_index, orm, style=line.style_dashed, color=orColor)

    day_dir := orm > prev_orm ? 1 : orm < prev_orm ? -1 : 0
    linefill.new(h_ln.ln, l_ln.ln, biasTog ? (day_dir == 1 ? orGreenFill : day_dir == -1 ? orRedFill : orInvis) : orInvis)

// session 外 — 往右延伸
if not or_sesh and or_token and showOR and not na(h_ln.ln)
    line.set_x2(h_ln.ln, bar_index)
    line.set_x2(l_ln.ln, bar_index)
    label.set_x(h_ln.lab, bar_index)
    label.set_x(l_ln.lab, bar_index)
    line.set_x2(m_ln, bar_index)


// =====================================================================
//  Part 3 — 綜合判斷表格 (Trend × OpenRange 位置 → 操作建議)
// =====================================================================

// ---- 價格相對 OR 位置 ----
// OR 必須「區間時段已結束」才算成形 (not or_sesh),
// 否則在 5 分鐘形成期間內價格必然落在區間內,會給出誤導性的位置判斷。
orReady = or_token and not or_sesh and not na(orh) and not na(orl)
string orPos = na
if orReady
    if close > orh
        orPos := "站上ORH"
    else if close < orl
        orPos := "跌破ORL"
    else
        orPos := "區間內"

// ---- 趨勢方向 (5級併為3向) ----
// 強UP/UP → 多方 ; 強Down/DOWN → 空方 ; MIX → 中性
// 註:以 "" 代表未定,避免 ternary 混用 na 造成型別推斷失敗
string trendDir = ""
if not na(state)
    trendDir := (state == "強UP" or state == "UP") ? "UP" : (state == "強Down" or state == "DOWN") ? "DOWN" : "MIX"

// ---- 供「快訊 → 新增條件」過濾用的狀態值 ----
// 搭配其他買賣指標的快訊:主條件為買賣訊號,新增條件選本指標的下列數值
// 數值是「持續」的狀態,不是一次性事件,只要當下狀態符合就成立
//
//   趨勢強度 : 0=MIX  1=一般趨勢  2=強趨勢 (不分多空)
//       有趨勢   → 趨勢強度 大於 0.5
//       有強趨勢 → 趨勢強度 大於 1.5
//   趨勢方向 : 2=強UP  1=UP  0=MIX  -1=DOWN  -2=強Down
//       多方趨勢 → 趨勢方向 大於 0.5     強多 → 大於 1.5
//       空方趨勢 → 趨勢方向 小於 -0.5    強空 → 小於 -1.5
string stateStr = na(state) ? "" : state
dirCode  = not supported ? 0 : stateStr == "強UP" ? 2 : stateStr == "UP" ? 1 : stateStr == "DOWN" ? -1 : stateStr == "強Down" ? -2 : 0
strength = math.abs(dirCode)

plot(strength,   "趨勢強度", display=display.data_window)
plot(dirCode,    "趨勢方向", display=display.data_window)
plot(lockedDiff, "趨勢差值", display=display.data_window)

// 同樣邏輯的 alertcondition,在條件清單中也可直接選用
alertcondition(strength >= 1, "有趨勢",   '{{ticker}} 有趨勢｜方向 {{plot("趨勢方向")}}｜差值 {{plot("趨勢差值")}}')
alertcondition(strength >= 2, "有強趨勢", '{{ticker}} 有強趨勢｜方向 {{plot("趨勢方向")}}｜差值 {{plot("趨勢差值")}}')

// 分多空:BUY 快訊搭配多方條件,SELL 快訊搭配空方條件
alertcondition(dirCode >= 1,  "多方趨勢 (UP+強UP)",     '{{ticker}} 多方趨勢｜方向 {{plot("趨勢方向")}}｜差值 {{plot("趨勢差值")}}')
alertcondition(dirCode >= 2,  "強多 (強UP)",            '{{ticker}} 強多｜方向 {{plot("趨勢方向")}}｜差值 {{plot("趨勢差值")}}')
alertcondition(dirCode <= -1, "空方趨勢 (DOWN+強Down)", '{{ticker}} 空方趨勢｜方向 {{plot("趨勢方向")}}｜差值 {{plot("趨勢差值")}}')
alertcondition(dirCode <= -2, "強空 (強Down)",          '{{ticker}} 強空｜方向 {{plot("趨勢方向")}}｜差值 {{plot("趨勢差值")}}')

// 趨勢 + K 棒顏色:給 BUY/SELL 合併成同一條件的訊號指標用
// 多方只在綠K成立 (當作 BUY)、空方只在紅K成立 (當作 SELL),十字線 (close == open) 兩邊都不成立
// 快訊1:BUY SELL 以及 多方趨勢+綠K → Buy ; 快訊2:BUY SELL 以及 空方趨勢+紅K → Sell
isGreen = close > open
isRed   = close < open
alertcondition(dirCode >= 1 and isGreen, "多方趨勢+綠K (BUY用)", '{{ticker}} 多方趨勢+綠K｜方向 {{plot("趨勢方向")}}｜差值 {{plot("趨勢差值")}}')
alertcondition(dirCode <= -1 and isRed,  "空方趨勢+紅K (SELL用)", '{{ticker}} 空方趨勢+紅K｜方向 {{plot("趨勢方向")}}｜差值 {{plot("趨勢差值")}}')

// 強趨勢版:只在 強UP / 強Down 成立
alertcondition(dirCode >= 2 and isGreen,  "強多+綠K (BUY用)",  '{{ticker}} 強多+綠K｜方向 {{plot("趨勢方向")}}｜差值 {{plot("趨勢差值")}}')
alertcondition(dirCode <= -2 and isRed,   "強空+紅K (SELL用)", '{{ticker}} 強空+紅K｜方向 {{plot("趨勢方向")}}｜差值 {{plot("趨勢差值")}}')

// ---- 建議矩陣 (3×3) ----
// UP   : 站上ORH=只做多 | 區間內=偏多待突破 | 跌破ORL=觀望
// MIX  : 站上ORH=突破待確認 | 區間內=觀望 | 跌破ORL=跌破待確認
// DOWN : 站上ORH=觀望 | 區間內=偏空待跌破 | 跌破ORL=只做空
string advice = na
color  advBg  = color.new(color.gray, 30)
if trendDir == ""
    advice := "計算中..."
    advBg  := color.new(color.gray, 50)
else if not orReady
    advice := "區間形成中"
    advBg  := color.new(color.gray, 50)
else
    if trendDir == "UP"
        if orPos == "站上ORH"
            advice := "只做多"
            advBg  := color.new(color.green, 0)
        else if orPos == "區間內"
            advice := "偏多待突破"
            advBg  := color.new(color.green, 45)
        else
            advice := "觀望"
            advBg  := color.new(#F9A825, 10)
    else if trendDir == "DOWN"
        if orPos == "跌破ORL"
            advice := "只做空"
            advBg  := color.new(color.red, 0)
        else if orPos == "區間內"
            advice := "偏空待跌破"
            advBg  := color.new(color.red, 45)
        else
            advice := "觀望"
            advBg  := color.new(#F9A825, 10)
    else  // MIX
        if orPos == "站上ORH"
            advice := "突破待確認"
            advBg  := color.new(color.orange, 20)
        else if orPos == "跌破ORL"
            advice := "跌破待確認"
            advBg  := color.new(color.orange, 20)
        else
            advice := "觀望"
            advBg  := color.new(#F9A825, 10)

// ---- 顯示對應 ----
getPos(p) => p == "右上" ? position.top_right : p == "右下" ? position.bottom_right : p == "左上" ? position.top_left : position.bottom_left
getSize(s) => s == "極小" ? size.tiny : s == "小" ? size.small : s == "普通" ? size.normal : s == "大" ? size.large : s == "極大" ? size.huge : size.auto

txtSize = getSize(fontSize)
hdrBg   = color.new(color.black, 20)
blank   = color.new(color.black, 100)

// 內容最多 6 列 + 頂部留白列
totalRows = 6 + topPad
var table t = table.new(getPos(tablePos), 2, totalRows, border_width=1)

fillRow(int r, string lbl, string val, color valBg) =>
    table.cell(t, 0, r, lbl, text_color=color.white, bgcolor=hdrBg, text_size=txtSize)
    table.cell(t, 1, r, val, text_color=color.white, bgcolor=valBg, text_size=txtSize)

clearRow(int r) =>
    table.cell(t, 0, r, "", bgcolor=blank)
    table.cell(t, 1, r, "", bgcolor=blank)

// 頂部留白列:透明底、以空白字元撐出行高,把內容往下推離狀態列
padRow(int r) =>
    table.cell(t, 0, r, " ", text_color=blank, bgcolor=blank, text_size=txtSize)
    table.cell(t, 1, r, " ", text_color=blank, bgcolor=blank, text_size=txtSize)

if barstate.islast
    if not supported
        rr = 0
        while rr < topPad
            padRow(rr)
            rr += 1
        table.cell(t, 0, rr, "不支援此標的", text_color=color.white, bgcolor=color.new(color.red, 20), text_size=txtSize)
        rr += 1
        while rr < totalRows
            clearRow(rr)
            rr += 1
    else
        r = 0
        // 頂部留白 (避開左上指標名稱)
        while r < topPad
            padRow(r)
            r += 1
        // 趨勢
        fillRow(r, "趨勢", na(state) ? "計算中..." : state, bgCol)
        r += 1
        // 建議 (可選)
        if showAdv
            fillRow(r, "建議", na(advice) ? "—" : advice, advBg)
            r += 1
        // 位置 (OR 成形後顯示;可選,跟隨建議開關)
        if showAdv
            fillRow(r, "位置", orReady ? orPos : "—", hdrBg)
            r += 1
        // 差值
        fillRow(r, "差值", na(lockedDiff) ? "—" : str.tostring(lockedDiff, "#.##") + " 點", hdrBg)
        r += 1
        // 強勢門檻 (可選)
        if showStr
            fillRow(r, "強勢", na(strongTh) ? "—" : "±" + str.tostring(strongTh, "#.##"), hdrBg)
            r += 1
        // 更新時間 (可選)
        if showTime
            fillRow(r, "更新於", na(lastCalcTime) ? "—" : str.format_time(lastCalcTime, "HH:mm:ss", syminfo.timezone), hdrBg)
            r += 1
        // 清空剩餘列,避免殘留框線
        while r < totalRows
            clearRow(r)
            r += 1
```
