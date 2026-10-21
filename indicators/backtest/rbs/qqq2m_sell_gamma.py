"""QQQ 2m (20, 0, 11, 1) sell signals while QQQ is in short gamma (price below the ZeroGEX gamma flip).
NQ cash-session 2m bars stand in for QQQ; flip from ZeroGEX minute data (2026-06-29 onward).

  cd indicators/backtest
  python3 -I rbs/qqq2m_sell_gamma.py

Raw original sell signals (new 20-bar high, then a close below that bar's low and below the EMA11), cash session
09:30-16:00. Gamma regime at the minute before the signal bar closes: short = QQQ close < flip. Each signal on its own:
entry at the signal close, stop at the two-bar high, targets 1 / 1.5 / 2 / 3R within 60 bars or 16:00, 1 point cost.
Also with Trend Judge (cash data, 20 points) on the sell side, and compared with long gamma and with all sells.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import gex_qqq as gq

START, END = '2026-06-29', '2026-10-16'


def main():
    one = oc.load()
    cash = mm.cash_only(one); tdm = mm.minute_trend(cash); H = mm.hourly(cash, True)
    df = oc.chart(cash, tdm, 2, 20.0, 40.0)
    s = mm.trend_signals(df, H, 2, 20, 11)
    s = s[(s.side == -1) & (s.date >= START) & (s.date <= END)].copy()
    zg = gq.zg_minute('QQQ')
    known = gq.NS(pd.DatetimeIndex(df.last_min.values[s.i]).tz_localize('UTC') if pd.DatetimeIndex(df.last_min.values).tz is None else pd.DatetimeIndex(df.last_min.values[s.i]))
    fl = gq.lookup(known, zg, lambda x: x.gamma_flip, 5); qc = gq.lookup(known, zg, lambda x: x.close, 5)
    s['short'] = np.where(np.isnan(fl), np.nan, (qc < fl).astype(float))
    s['tj'] = s.spread > 20                     # spread is already on the trade's side
    s['net3'] = s.r3 - oc.COST / s.risk
    def row(lab, z):
        if not len(z): print(f'   {lab:<34}    0 筆'); return
        print(f'   {lab:<34}{len(z):4d} 筆  1R {100 * (z.r1 > 0).mean():3.0f}%  1.5R {100 * (z["r1.5"] >= 1.5).mean():3.0f}%  2R {100 * (z.r2 >= 2).mean():3.0f}%  3R {100 * (z.r3 >= 3).mean():3.0f}%'
              f'  每筆 1R {(z.r1 - oc.COST / z.risk).mean():+.2f} 2R {(z.r2 - oc.COST / z.risk).mean():+.2f} 3R {z.net3.mean():+.2f}  停損中位 {z.risk.median():.0f} 點')
    print(f'QQQ 2m (20, 0, 11, 1) 賣訊（NQ 美股盤代替），{START} .. {END}，每個訊號單獨算')
    row('全部賣訊', s)
    row('Short gamma（QQQ 在 flip 下）', s[s.short == 1])
    row('Long gamma（QQQ 在 flip 上）', s[s.short == 0])
    row('Short gamma + Trend Judge 空方', s[(s.short == 1) & s.tj])
    row('Short gamma + 1h EMA20 空方', s[(s.short == 1) & (s.h1 == -1)])
    row('Short gamma + TJ 空 + 1h 空', s[(s.short == 1) & s.tj & (s.h1 == -1)])
    z = s[s.short == 1]
    print('   Short gamma 每月：' + '  '.join(f'{k[5:7]}月 {len(g)} 筆 1R {100 * (g.r1 > 0).mean():.0f}%' for k, g in z.groupby(z.date.str[:7])))


if __name__ == '__main__':
    main()
