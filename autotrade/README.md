# Remi's Autotrade

TradingView 的 Remi Superb v3 策略發出快訊後，用 webhook 送到自己電腦上的程式，再由程式透過 TWS / IB Gateway 在 IBKR 下單。商品是 **MNQ，一次 2 口**。

```
TradingView 策略快訊（webhook）
  → 通道（ngrok / Cloudflare，給一個 https 網址）
  → 本機 main.py（127.0.0.1:8080）
  → TWS / IB Gateway API（模擬 7497）
  → IBKR
```

- **進場**：市價買 / 賣 2 口，同時在 IBKR 掛停損和目標。這兩張是一組，一邊成交另一邊就取消。停損、目標用快訊給的價格，以 0.25 為單位四捨五入。
- **出場快訊**：取消自動下單的掛單，剩下的部位用市價平掉。如果 IBKR 上已經被停損或目標出掉，就什麼都不做。
- **一次一筆**：IBKR 上已經有 MNQ 部位或自動下單的掛單時，不會再進場。
- 合約月份跟 TradingView 圖上 NQ1! 當下對應的合約相同（快訊裡的 `contract`）。快訊沒給月份時，用離到期還有 8 天以上的近月合約。

## 安全網

TradingView 的快訊不保證每次都送到。所以下面這些由程式自己檢查，不靠 TradingView：

| 設定（config.json） | 預設 | 作用 |
|---|---|---|
| `allow_live` | false | 帳號不是 DU 開頭（模擬帳戶）就拒絕連線 |
| `qty` | 2 | 口數，以這裡為準，不看快訊裡的 qty |
| `max_entry_delay_sec` | 15 | 收到快訊後超過 15 秒還沒輪到處理（例如 IBKR 斷線），就不進場 |
| `max_alert_age_sec` | 30 | 快訊觸發後超過 30 秒才送到，就不進場 |
| `max_stop_points` | 120 | 停損距離超過 120 點不進場（擋掉錯誤的訊息） |
| `max_trades_per_day` | 20 | 每個交易日最多幾筆 |
| `max_daily_loss_usd` | 600 | 當日損益（IBKR 回報）到 −600 美元：平倉，停到下一個交易日（美東 18:00） |
| `max_hold_minutes` | 125 | 持有超過 125 分鐘就平倉（v3 是 60 根 2 分 K） |
| `flat_time_et` / `reopen_time_et` | 16:58 / 18:00 | 美東 16:58–18:00 不進場，有部位就平倉（17:00 休市） |
| `tradingview_ips_only` | false | 打開後只收 TradingView 官方 IP 送來的快訊 |

另外，webhook 網址裡有一段密碼（`webhook_secret`），密碼不對一律回 404。

## 第一次設定

1. **Python 環境**：已經建好在 `~/.venvs/remi-autotrade`（ib_insync、aiohttp）。
2. **config.json**：已經從 `config.example.json` 產生，`webhook_secret` 是隨機產生的密碼。這個檔案不進 git，**不要給別人看**。
3. **TWS（或 IB Gateway）用模擬帳戶登入**，然後到「設定 → API → 設定」：
   - 勾「Enable ActiveX and Socket Clients」
   - 取消勾選「Read-Only API」
   - Socket port 設 `7497`（模擬帳戶的預設值）
   - Trusted IPs 加 `127.0.0.1`
4. **開通道**，讓 TradingView 連得到你的電腦。只把 **8080** 接出去，**8081（管理用）不要接**：
   - ngrok（免費帳號有一個固定網址）：`ngrok http --url=你的網址.ngrok-free.app 8080`
   - 或 Cloudflare：`cloudflared tunnel --url http://localhost:8080`。這個網址每次重開都會變，變了就要改 TradingView 快訊的網址。
5. **TradingView**：
   - 用 [remi_superb_v3_strategy.pine](../indicators/remi_superb_v3_strategy.pine) 這支**策略**（不是指標），加到 **NQ1! 2 分 K**。
   - 建立快訊：條件選這支策略，選「只有訂單成交」。
   - 訊息只放一行：`{{strategy.order.alert_message}}`。
   - 通知分頁勾 Webhook URL：`https://你的通道網址/hook/<config.json 的 webhook_secret>`。
   - TradingView 的 webhook 要付費方案，帳號也要開兩步驟驗證。
   - **只接一張圖。** 如果 2 分 K 和 5 分 K 都接進來，其中一張的出場快訊會把另一張的部位平掉。

## 雲端主機（Vultr VPS）

2026-10-19 建好，Mac 不用開著：

| 項目 | 內容 |
|---|---|
| 主機 | Vultr New Jersey，Shared CPU 2 vCPU / 4GB，Ubuntu 24.04，每月 20 美元 |
| IP | 64.176.198.47。只能用 SSH key 登入（`~/.ssh/remi_vultr`），密碼登入已經關閉 |
| 時區 | 美東（America/New_York） |
| 防火牆 | 只開 22（SSH）、80 / 443（https）；8080、8081、4002 外面連不到 |
| IB Gateway | 10.50，用 IBC 自動登入**模擬帳戶**，API port 4002；每天美東 17:15（CME 休市時）自動重啟。服務名稱 `ibgateway` |
| autotrade | `/home/trader/autotrade`，Python 3.12 + ib_async。服務名稱 `autotrade`，開機自動啟動、當掉自動重啟 |
| https | Caddy + Let's Encrypt，網址 `https://64-176-198-47.sslip.io/hook/<webhook_secret>`，只把 `/hook/` 轉給 autotrade |
| 來源限制 | `tradingview_ips_only` 開著，只收 TradingView 官方 IP；來源 IP 看 Caddy 設的 `X-Forwarded-For` |

登入主機：

```bash
ssh -i ~/.ssh/remi_vultr root@64.176.198.47
```

在主機上常用的指令：

- 填 / 改 IBKR 登入資料，並啟動 Gateway：`remi-set-ibkr`。要填**模擬帳戶專屬的使用者名稱**（DUR282640 是 `remibmoney`），不是主帳號；主帳號底下有多個模擬使用者時，IBKR 會拒絕用主帳號登入模擬。帳密只存在主機的 `/home/trader/ibc/config.ini`。
- 填 / 改 Discord 通知網址：`remi-set-discord`（重啟 autotrade，頻道會收到「🚀 autotrade 啟動」）。
- 看狀態：`systemctl status ibgateway autotrade`
- 看即時記錄：`journalctl -u autotrade -f`
- 看今天的快訊和下單：`tail /home/trader/autotrade/logs/events-$(date +%F).jsonl`
- 管理介面（在主機上執行）：`curl -s 127.0.0.1:8081/status`，`curl -s -X POST 127.0.0.1:8081/flatten`

從 Mac 更新程式（不會蓋掉主機上的 config.json）：

```bash
rsync -a -e "ssh -i ~/.ssh/remi_vultr" --exclude logs --exclude __pycache__ --exclude config.json ./ root@64.176.198.47:/home/trader/autotrade/ && ssh -i ~/.ssh/remi_vultr root@64.176.198.47 'chown -R trader:trader /home/trader/autotrade && systemctl restart autotrade'
```

注意：

- **同一個 IBKR 使用者同時只能登入一處。** Gateway 設成搶先登入（`ExistingSessionDetectedAction=primary`），你在 Mac 上用同一個帳號登入模擬 TWS 時，其中一邊會被踢掉。建議在帳戶管理開一個子使用者專門給主機用。
- 轉真倉時，改 `/home/trader/ibc/config.ini` 的 `TradingMode=live`、`gatewaystart.sh` 的 `TRADING_MODE=live`、autotrade config 的 `ib_port: 4001` 和 `allow_live: true`。真倉每週要在手機上做一次兩步驟驗證。

## 每天開盤前（Mac 本機跑的時候）

```bash
cd "/Users/remilin/Library/CloudStorage/Dropbox/Remi 交易人/Trading x Claude/autotrade"
```

```bash
caffeinate -i ~/.venvs/remi-autotrade/bin/python main.py
```

`caffeinate` 讓 Mac 不會睡著。TWS 斷線或每天自動重啟時，程式每 10 秒會重連一次。

不連 IBKR、只看快訊有沒有送到：

```bash
~/.venvs/remi-autotrade/bin/python main.py --dry-run
```

## 管理（在本機另開一個終端機）

```bash
curl -s http://127.0.0.1:8081/status
```

```bash
curl -s -X POST http://127.0.0.1:8081/pause
```

```bash
curl -s -X POST http://127.0.0.1:8081/resume
```

```bash
curl -s -X POST http://127.0.0.1:8081/flatten
```

- `pause`：不再進場，但出場快訊照做。
- `flatten`：馬上取消掛單，部位市價平掉。

## 記錄和延遲

- `logs/日期.log`：程式訊息。
- `logs/events-日期.jsonl`：每一筆快訊、進場、出場、拒絕的原因。
- 進場記錄裡的 `tv_delay_sec` 是「快訊觸發 → 程式收到」的秒數。TradingView 的 `{{timenow}}` 只到秒，所以誤差大約 ±1 秒。
- `fill` 是 IBKR 的成交價，可以跟 `price`（策略預期的進場價）比，看滑價多少。

## Discord 通知

config 的 `discord_webhook_url` 有填就會送（[notify.py](notify.py)），送不出去只記 log，不影響下單：

- 🟢 / 🔴 進場：方向、口數、合約、成交價、停損 / 目標距離、滑價（跟策略價比）、快訊延遲
- ✅ / ❌ 出場（停損、目標、市價）：出場價、這筆點數和美元（未扣手續費）、今天累計。損益用 IBKR 的成交回報算；程式重開時有部位，就用 IBKR 的平均成本接著算
- ⛔ 沒下單的快訊和原因；⚠️ 安全網平倉；🛑 當日虧損上限
- ⚠️ IBKR 斷線超過 `disconnect_alert_min`（5）分鐘，恢復時再通知一次
- 📊 平日美東 `summary_time_et`（17:00）盤後總結：筆數、勝敗、點數、美元
- 🚀 程式啟動（每天 Gateway 重啟不會觸發；autotrade 本身重開才會）

## 測試

```bash
~/.venvs/remi-autotrade/bin/python -m unittest test_autotrade -v
```

## 已知限制

- **MIX 觸價進場**：TradingView 碰到突破價、發出快訊之後，程式才送市價單，所以會比回測的掛單多一點滑價。之後可以改成：區間成形時就先在 IBKR 掛好停損進場單。
- **策略和 IBKR 可能不同步**：例如進場單被拒絕時，TradingView 還是當作有部位。程式只看 IBKR 的實際部位：有部位就不再進場，出場快訊一律平倉。
- **同一個帳戶不要手動做 MNQ**：程式平倉時，會把帳戶裡所有 MNQ 部位一起平掉。
- 管理介面只聽 127.0.0.1，沒有密碼。不要把 8081 接到通道上。

## 轉真倉前

1. 模擬帳戶至少跑 1–2 週，把 events 記錄裡每一筆的進出場、成交價跟 TradingView 策略測試器的清單對一次。
2. 確認 `tv_delay_sec` 和滑價可以接受。
3. 由你自己改 config.json：`ib_port` 改 7496（TWS 真倉）或 4001（Gateway 真倉），`allow_live` 改 true，`account` 填真倉帳號。
