# Options Positions

> 來源：某位交易高手的公開操作紀錄（非本人持倉）。偏好分析見 [analysis.md](analysis.md)。

Expiry notation in the source notes is `YY/M` (e.g. `27/6` = June 2027). Dates below assume standard monthly expiration (third Friday).

## Open

| Ticker | Action | Strategy | Expiry | Strike(s) | Qty | Entry Price | Opened | Notes |
|--------|--------|----------|--------|-----------|-----|-------------|--------|-------|
| INIO | BTO | Long call | 2027-06-18 | $20 C | | | 2026-10-09 | |
| INTC | BTO | Bull call spread | 2028-01-21 | Long $90 C / Short $125 C | | | 2026-10-09 | Width $35 |
| MXL | BTO | Bull call spread | 2027-06-18 | Long $80 C / Short $130 C | | | 2026-10-09 | Width $50 |
| MXL | BTO | Bull call spread | 2028-01-21 | Long $60 C / Short $150 C | | | 2026-10-09 | Width $90 |
| QCOM | BTO | Bull call spread | 2027-06-18 | Long $170 C / Short $250 C | | | 2026-10-09 | Width $80 |
| VICR | BTO | Bull call spread | 2027-04-16 | Long $260 C / Short $380 C | | | 2026-10-09 | Width $120 |
| VST | BTO | Bull call spread | 2027-06-18 | Long $145 C / Short $220 C | | | 2026-10-09 | Width $75 |
| SPCX | BTO | Bull call spread | 2027-06-18 | Long $150 C / Short $225 C | | | 2026-10-09 | Width $75 |
| PENG | BTO | Bull call spread | 2028-01-21 | Long $60 C / Short $100 C | | | 2026-10-09 | Width $40 |

## Hedges (short calls)

| Ticker | Action | Strategy | Expiry | Strike | Qty | Credit | Opened | Notes |
|--------|--------|----------|--------|--------|-----|--------|--------|-------|
| TSLA | STO | Covered call | 2026-11-20 | $420 C | | $10.60 | 2026-10-09 | |
| LITE | STO | Covered call | 2026-11-20 | $1200 C | | $82.00 | 2026-10-09 | |
| AMZN | STO | Covered call | 2026-11-20 | $285 C | | $5.40 | 2026-10-09 | |
| CRCL | STO | Covered call | 2026-11-20 | $100 C | | $4.30 | 2026-10-09 | |
| CEG | STO | Covered call | 2026-11-20 | $330 C | | $8.80 | 2026-10-09 | |

## Stock / ETF trades

| Ticker | Action | Qty | Price | Date | Notes |
|--------|--------|-----|-------|------|-------|
| LITX | Sell | | | 2026-10-09 | 槓桿 ETF（LITE 相關） |
| CEGX | Sell | | | 2026-10-09 | 槓桿 ETF（CEG 相關） |
| GGLL | Sell | | | 2026-10-09 | 2 倍做多 GOOGL ETF |

## Closed

| Ticker | Strategy | Expiry | Strike(s) | Qty | Entry | Exit | Opened | Closed | P/L |
|--------|----------|--------|-----------|-----|-------|------|--------|--------|-----|
| SPCX | Covered call (short) | 2027-01-15 | $200 C | | | | | 2026-10-09 | |
| QCOM | Covered call (short) | 2027-06-18 | $200 C | | | | | 2026-10-09 | |
| COHR | Covered call (short) | 2028-01-21 | $400 C | | | | | 2026-10-09 | |
| NVDA | Covered call (short) | 2026-11-20 | $250 C | | | | | 2026-10-09 | |
| GOOGL | Long call (STC 1/2) | 2027-01-15 | $340 C | 1/2 | | | | 2026-10-09 | 賣出一半部位，剩一半仍持有 |
