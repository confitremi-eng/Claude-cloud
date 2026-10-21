"""Are v3 longs better when SPX is in long gamma (SPX above its ZeroGEX gamma flip)? 2026-06-29 onward.

  cd indicators/backtest
  python3 -I rbs/zerogex_fetch.py "../../ZEROGEX API.txt" range hourly syms=SPX
  python3 -I rbs/spx_gamma.py

Regime at entry: during the cash session from the SPX minute data (the minute before the signal bar closes, <= 5 min old),
otherwise from the hourly data (snapshot spot vs flip, used from the end of its hour, <= 4 hours old).
Trades: v3 NQ 2m as now (3R, one at a time, trend + MIX), each v3 2m trend signal on its own (1R / 3R hit), and NQ RTH
1m (QQQ setting, 3R; junk time not applied). Buys and sells by SPX long / short gamma.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import gex_qqq as gq
import v3_kline as vk
import daily_sma5 as d5

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START = '2026-06-29'


def regime(ts_close):
    """ts_close: tz-aware close times of the entry bars -> +1 long gamma, -1 short, nan unknown."""
    mn = gq.zg_minute('SPX')
    known = gq.NS(ts_close - pd.Timedelta(minutes=1))
    fl = gq.lookup(known, mn, lambda x: x.gamma_flip, 5); px = gq.lookup(known, mn, lambda x: x.close, 5)
    out = np.where(np.isnan(fl), np.nan, np.sign(px - fl))
    hr = pd.read_csv(os.path.join(HERE, 'data', 'zerogex', 'SPX_hourly.csv')).dropna(subset=['gamma_flip', 'spot'])
    hr['known'] = pd.to_datetime(hr.ts, utc=True) + pd.Timedelta(hours=1); hr = hr.sort_values('known')
    m = pd.merge_asof(pd.DataFrame({'t': ts_close}).reset_index(), hr[['known', 'spot', 'gamma_flip']], left_on='t', right_on='known', direction='backward')
    old = (m.t - m.known).dt.total_seconds() > 4 * 3600
    hv = np.where(old | m.gamma_flip.isna(), np.nan, np.sign(m.spot - m.gamma_flip))
    return np.where(np.isnan(out), hv, out)


def cell(z, col='net'):
    return f'{len(z):4d} 筆 勝 {100 * (z[col] > 0).mean():3.0f}% {z[col].mean():+.2f}R' if len(z) else '   0 筆'


def table(t, title, col='net'):
    print(f'\n{title}')
    print(f'   {"":<6}{"SPX long gamma":>24}{"SPX short gamma":>24}')
    for lab, k in (('買', 1), ('賣', -1)):
        z = t[t.side == k]
        print(f'   {lab:<6}{cell(z[z.reg == 1], col):>24}{cell(z[z.reg == -1], col):>24}')


def main():
    one = oc.load(); M = oc.Market(one); D = d5.daily(one)
    C = M.ctx(2); df = C.df; th = df.thr.values; c = df.close.values
    dt = pd.DatetimeIndex(df.datetime); dt = dt.tz_localize('UTC') if dt.tz is None else dt
    ny = (dt + pd.Timedelta(minutes=2)).tz_convert(ss.NY); m = np.asarray(ny.hour * 60 + ny.minute)
    skip = ((m >= 720) & (m <= 785)) | ((m >= 945) & (m < 1110))
    s = mm.trend_signals(df, M.H, 2, 20, 8)
    T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < 400) & ~s.date.isin(ss.FOMC) & ~skip[s.i]]
    mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not skip[x[0]]]
    t = vk.trades(C, T, mix, 3.0); t = t[t.date >= START].copy()
    t['reg'] = regime(dt[t.i.values] + pd.Timedelta(minutes=2))
    cash = ((m[t.i.values] > 570) & (m[t.i.values] <= 960))
    table(t, f'NQ 2m v3 實際做的單（3R），{START} 起')
    table(t[cash], '   只看美股盤進場'); table(t[~cash], '   只看夜盤進场')
    Ts = T[T.date >= START].copy(); Ts['reg'] = regime(dt[Ts.i.values] + pd.Timedelta(minutes=2))
    Ts['n1'] = Ts.r1 - oc.COST / Ts.risk; Ts['n3'] = Ts.r3 - oc.COST / Ts.risk
    table(Ts, 'NQ 2m 趨勢訊號單獨進場（1R）', 'n1'); table(Ts, 'NQ 2m 趨勢訊號單獨進場（3R）', 'n3')
    dr, tr = oc.nq_rth(one, detail=True); tr = tr[tr.date >= START].copy()
    dtr = pd.DatetimeIndex(dr.datetime); dtr = dtr.tz_localize('UTC') if dtr.tz is None else dtr
    tr['reg'] = regime(dtr[tr.i.values] + pd.Timedelta(minutes=1)); tr['net'] = tr.r3 - oc.COST / tr.risk; tr['n1'] = tr.r1 - oc.COST / tr.risk
    table(tr, 'NQ RTH 1m（QQQ 做法，3R）'); table(tr, 'NQ RTH 1m（1R）', 'n1')


if __name__ == '__main__':
    main()
