# Options Positions

> 來源：某位交易高手的公開操作紀錄（非本人持倉）。偏好分析見 [analysis.md](analysis.md)。

Expiry notation in the source notes is `YY/M` (e.g. `27/6` = June 2027). Dates below assume standard monthly expiration (third Friday).

批次：B1 = 2026-10-09；B2 = 日期未提供（暫記 2026-10-09）；B3 = 2026-10-12；B4 = 2026-10-15。

## Open — 買方（long calls / call spreads）

| Ticker | Action | Strategy | Expiry | Strike(s) | Qty | Entry Price | Opened | Notes |
|--------|--------|----------|--------|-----------|-----|-------------|--------|-------|
| INIO | BTO | Long call | 2027-06-18 | $20 C | | | 2026-10-09 | B1 |
| INTC | BTO | Bull call spread | 2028-01-21 | Long $90 C / Short $125 C | | | 2026-10-09 | B1，Width $35 |
| MXL | BTO | Bull call spread | 2027-06-18 | Long $80 C / Short $130 C | | | 2026-10-09 | B1，Width $50 |
| MXL | BTO | Bull call spread | 2028-01-21 | Long $60 C / Short $150 C | | | 2026-10-09 | B1，Width $90；B3 平 $150 cc，可能已拆成單買 call |
| QCOM | BTO | Bull call spread | 2027-06-18 | Long $170 C / Short $250 C | | | 2026-10-09 | B1，Width $80 |
| VICR | BTO | Bull call spread | 2027-04-16 | Long $260 C / Short $380 C | | | 2026-10-09 | B1，Width $120 |
| VST | BTO | Bull call spread | 2027-06-18 | Long $145 C / Short $220 C | | | 2026-10-09 | B1，Width $75 |
| SPCX | BTO | Bull call spread | 2027-06-18 | Long $150 C / Short $225 C | | | 2026-10-09 | B1，Width $75 |
| PENG | BTO | Bull call spread | 2028-01-21 | Long $60 C / Short $100 C | | | 2026-10-09 | B1，Width $40 |
| GOOGL | (持有) | Long call | 2027-01-15 | $340 C | 剩 1/2 | | | B2 平掉一半 |
| MU | BTO | Bull call spread | 2027-06-18 | Long $950 C / Short $1150 C | | | 2026-10-12 | B3，Width $200 |
| BE | BTO | Bull call spread | 2027-06-18 | Long $250 C / Short $350 C | | | 2026-10-12 | B3，Width $100；B4 平 $350 cc，可能已拆成單買 call |
| NBIS | BTO | Bull call spread | 2027-06-18 | Long $200 C / Short $300 C | | | 2026-10-12 | B3，Width $100 |
| VICR | BTO | Bull call spread | 2027-04-16 | Long $260 C / Short $380 C | | | 2026-10-12 | B3 加碼，同 B1；B4 平 $380 cc，可能已拆成單買 call |
| AAOI | BTO | Bull call spread | 2027-06-18 | Long $90 C / Short $150 C | | | 2026-10-12 | B3，Width $60 |
| NVDA | BTO | Bull call spread | 2027-06-18 | Long $200 C / Short $250 C | | | 2026-10-12 | B3，Width $50；B4 平 $250 cc，可能已拆成單買 call |
| HPE | BTO | Bull call spread | 2028-01-21 | Long $40 C / Short $75 C | | | 2026-10-15 | B4，Width $35 |

## Open — 賣方：Covered calls（Hedge）

| Ticker | Action | Strategy | Expiry | Strike | Qty | Credit | Opened | Notes |
|--------|--------|----------|--------|--------|-----|--------|--------|-------|
| TSLA | STO | Covered call | 2026-11-20 | $420 C | | $10.60 | 2026-10-09 | B1 |
| AMZN | STO | Covered call | 2026-11-20 | $285 C | | $5.40 | 2026-10-09 | B2 |
| CEG | STO | Covered call | 2026-11-20 | $330 C | | $8.80 | 2026-10-09 | B2 |

## Open — 賣方：Short puts

| Ticker | Action | Strategy | Expiry | Strike | Qty | Credit | Credit ÷ Strike | Opened | Notes |
|--------|--------|----------|--------|--------|-----|--------|-----------------|--------|-------|
| SOXL | STO | Short put | 2026-11-20 | $120 P | | $13.50 | 11.3% | 2026-10-12 | B3，3 倍半導體 ETF |
| LITX | STO | Short put | 2026-11-20 | $35 P | | $5.00 | 14.3% | 2026-10-12 | B3 |
| LITX | STO | Short put | 2026-12-18 | $30 P | | $4.87 | 16.2% | 2026-10-12 | B3 |
| NEBX | STO | Short put | 2026-12-18 | $20 P | | $4.45 | 22.3% | 2026-10-12 | B3，推測為 NBIS 槓桿 ETF |
| BEX | STO | Short put | 2026-12-18 | $30 P | | $5.70 | 19.0% | 2026-10-12 | B3，推測為 BE 槓桿 ETF |
| SOXL | STO | Short put | 2026-12-18 | $90 P | | $14.45 | 16.1% | 2026-10-15 | B4 |
| AMDL | STO | Short put | 2026-11-20 | $55 P | | $6.00 | 10.9% | 2026-10-15 | B4，2 倍 AMD ETF |
| CRWL | STO | Short put | 2026-11-20 | $80 P | | $8.20 | 10.3% | 2026-10-15 | B4，推測為 CRWD 槓桿 ETF |
| ZCSH | STO | Short put | 2026-12-18 | $25 P | | $3.00 | 12.0% | 2026-10-15 | B4，代號不確定 |
| LITX | STO | Short put | 2026-12-18 | $20 P | | $3.50 | 17.5% | 2026-10-15 | B4 |
| TEMT | STO | Short put | 2026-12-18 | $20 P | | $3.50 | 17.5% | 2026-10-15 | B4，推測為 TEM 槓桿 ETF |

## Stock / ETF trades

| Ticker | Action | Qty | Price | Date | Notes |
|--------|--------|-----|-------|------|-------|
| LITX | Sell | | | 2026-10-09 | B2，槓桿 ETF（LITE 相關） |
| CEGX | Sell | | | 2026-10-09 | B2，槓桿 ETF（CEG 相關） |
| GGLL | Sell | | | 2026-10-09 | B2，2 倍做多 GOOGL ETF |
| USD | Buy | | | 2026-10-12 | B3，2 倍半導體 ETF |
| SNXX | Buy | | | 2026-10-12 | B3，推測為 SNDK 槓桿 ETF |
| MUU | Buy | | | 2026-10-12 | B3，2 倍 MU ETF |
| MXL | Buy | | | 2026-10-12 | B3，正股 |
| SOXL | Buy | | | 2026-10-15 | B4，3 倍半導體 ETF |
| TQQQ | Buy | | | 2026-10-15 | B4，3 倍那斯達克 100 ETF |
| USD | Buy | | | 2026-10-15 | B4，加碼 |
| QLD | Buy | | | 2026-10-15 | B4，2 倍那斯達克 100 ETF |
| ETHU | Buy | | | 2026-10-15 | B4，2 倍以太幣 ETF |
| PUR | Buy | | | 2026-10-15 | B4，代號不確定 |
| CRWD | Buy | | | 2026-10-15 | B4，正股 |
| HPE | Buy | | | 2026-10-15 | B4，正股 |

## Closed

| Ticker | Strategy | Expiry | Strike(s) | Qty | Entry | Exit | Opened | Closed | P/L |
|--------|----------|--------|-----------|-----|-------|------|--------|--------|-----|
| SPCX | Covered call (short) | 2027-01-15 | $200 C | | | | | 2026-10-09 | |
| QCOM | Covered call (short) | 2027-06-18 | $200 C | | | | | 2026-10-09 | |
| COHR | Covered call (short) | 2028-01-21 | $400 C | | | | | 2026-10-09 | |
| NVDA | Covered call (short) | 2026-11-20 | $250 C | | | | | 2026-10-09 | |
| GOOGL | Long call (STC 1/2) | 2027-01-15 | $340 C | 1/2 | | | | 2026-10-09 | |
| PENG | Long call (STC) | 2027-01-15 | $90 C | | | | | 2026-10-12 | |
| LITE | Covered call (short) | 2026-11-20 | $1200 C | | $82.00 | | 2026-10-09 | 2026-10-12 | 開倉 3 天就平 |
| NBIS | Covered call (short) | 2027-06-18 | $300 C | | | | | 2026-10-12 | |
| AAOI | Covered call (short) | 2027-01-15 | $160 C | | | | | 2026-10-12 | |
| AAOI | Covered call (short) | 2027-06-18 | $220 C | | | | | 2026-10-12 | |
| CRCL | Covered call (short) | 2026-11-20 | $100 C | | $4.30 | | 2026-10-09 | 2026-10-12 | 開倉 3 天就平 |
| CRCL | Covered call (short) | 2027-06-18 | $150 C | | | | | 2026-10-12 | |
| MU | Covered call (short) | 2027-06-18 | $1150 C | | | | | 2026-10-12 | |
| SKHY | Covered call (short) | 2027-06-18 | $200 C | | | | | 2026-10-12 | 推測為 SK hynix 相關 |
| VICR | Covered call (short) | 2028-01-21 | $380 C | | | | | 2026-10-12 | |
| MXL | Covered call (short) | 2028-01-21 | $150 C | | | | | 2026-10-12 | |
| VICR | Covered call (short) | 2027-04-16 | $380 C | | | | | 2026-10-15 | 對應 VICR 價差的賣出腳 |
| NBIS | Covered call (short) | 2028-01-21 | $300 C | | | | | 2026-10-15 | |
| MXL | Covered call (short) | 2028-01-21 | $135 C | | | | | 2026-10-15 | |
| BE | Covered call (short) | 2027-06-18 | $350 C | | | | | 2026-10-15 | 對應 BE 價差的賣出腳 |
| CRDO | Covered call (short) | 2028-01-21 | $300 C | | | | | 2026-10-15 | |
| SPCX | Covered call (short) | 2027-06-18 | $220 C | | | | | 2026-10-15 | |
| SPCX | Covered call (short) | 2028-01-21 | $250 C | | | | | 2026-10-15 | |
| NVDA | Covered call (short) | 2027-06-18 | $250 C | | | | | 2026-10-15 | 對應 NVDA 價差的賣出腳 |
| SKHY | Covered call (short) | 2028-01-21 | $200 C | | | | | 2026-10-15 | |
| PENG | Covered call (short) | 2027-01-15 | $80 C | | | | | 2026-10-15 | |
