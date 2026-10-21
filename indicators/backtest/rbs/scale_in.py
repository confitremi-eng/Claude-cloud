"""Scale in on a pullback: one contract at the signal, the second on a limit order X R back toward the stop
(NQ 2m / 5m, five years).

  cd indicators/backtest
  python3 -I rbs/scale_in.py

v3 as now (2m trend 0-400, 5m 0-180 + daily SMA5 / 0.25% rule, stop >= 0.95 ATR, FOMC days off, junk time and New York
15:45-18:30 off, one at a time; trend + MIX; no re-entry). Two contracts per trade, the same stop and the same target
price as v3 (3R / 2R of the original risk), 60-bar / halt exits for both.
  both now   : both contracts at the signal (= v3 with 2 contracts)
  pullback X : one at the signal, one on a limit X R back toward the stop (X = 0.25 / 0.5 / 0.75), working until the trade
               ends. Within a bar the limit fills before the stop or target (conservative for a bar that also hits the stop).
  only pullback X : only the limit contract (skip the trade if it never fills), both contracts there
Points for both contracts together, 1 point cost per filled contract. Trade-level win rate (net > 0).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import daily_sma5 as d5


def sim(C, trend, mix, R, X, mode):
    """mode: 'now' (2 at signal), 'scale' (1 now + 1 limit), 'limit' (2 on the limit only)."""
    df = C.df; h, l, c = C.h, C.l, C.c
    holeb = np.r_[False, (df.datetime.diff() > pd.Timedelta(minutes=30)).values[1:]]
    trad = df.tradable.values
    tr = {int(i): int(k) for i, k in zip(trend.i, trend.side)}
    mx = {j: (k, px, st) for j, k, px, st, _ in mix}
    out = []; pos = 0
    for j in range(len(c)):
        if pos != 0 and j > vb:
            if lots_lim and not filled and ((l[j] <= lim) if pos == 1 else (h[j] >= lim)):
                filled = True
            hs = (l[j] <= vs) if pos == 1 else (h[j] >= vs)
            ht = (h[j] >= vt) if pos == 1 else (l[j] <= vt)
            if hs or ht or j - vb >= 60 or C.halt[j] or holeb[j]:
                px = vs if hs else vt if ht else (c[j - 1] if holeb[j] else c[j])
                pts = lots_now * ((px - ve) * pos - oc.COST) + (lots_lim * ((px - lim) * pos - oc.COST) if filled else 0)
                if lots_now or filled: out.append((d0, kind, pts, filled))
                pos = 0
        if not trad[j] or C.halt[j] or C.late[j]: continue
        for src in ('mix', 'tr'):
            if pos != 0: break
            if src == 'mix' and j in mx:
                k, px, st = mx[j]; ve = px; kind = 'MIX'
            elif src == 'tr' and j in tr:
                k = tr[j]; st = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j]); ve = c[j]; kind = '趨勢'
            else:
                continue
            risk = abs(ve - st)
            pos, vs, vt, vb, d0 = k, st, ve + k * R * risk, j, C.date[j]
            lots_now, lots_lim = {'now': (2, 0), 'scale': (1, 1), 'limit': (0, 2)}[mode]
            lim = ve - k * X * risk; filled = False
            if src == 'mix' and ((k == 1 and l[j] <= vs) or (k == -1 and h[j] >= vs)):     # stop order filled and stopped in the same bar
                if lots_lim and ((l[j] <= lim) if k == 1 else (h[j] >= lim)): filled = True
                pts = lots_now * ((vs - ve) * k - oc.COST) + (lots_lim * ((vs - lim) * k - oc.COST) if filled else 0)
                if lots_now or filled: out.append((d0, kind, pts, filled))
                pos = 0
    return pd.DataFrame(out, columns=['date', 'kind', 'pts', 'filled'])


def main():
    one = oc.load(); M = oc.Market(one); D = d5.daily(one)
    for tf, R, cap in ((2, 3.0, 400), (5, 2.0, 180)):
        C = M.ctx(tf); df = C.df; th = df.thr.values; c = df.close.values
        dt = pd.DatetimeIndex(df.datetime); dt = dt.tz_localize('UTC') if dt.tz is None else dt
        ny = (dt + pd.Timedelta(minutes=tf)).tz_convert(ss.NY); m = np.asarray(ny.hour * 60 + ny.minute)
        skip = ((m >= 720) & (m <= 785)) | ((m >= 945) & (m < 1110))
        sma = D.sma.reindex((dt.tz_convert(ss.NY) + pd.Timedelta(hours=6)).normalize()).values
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < cap) & ~s.date.isin(ss.FOMC) & ~skip[s.i]]
        ok5 = lambda j, k, px: (px - sma[j]) * k > 0 and abs(px - sma[j]) / px * 100 >= 0.25
        if tf == 5: T = T[np.sign(c[T.i.values] - sma[T.i.values]) == T.side.values]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not skip[x[0]] and (tf != 5 or ok5(x[0], x[1], x[2]))]
        print(f'\nNQ {tf}m（2 口，目標 {R:g}R 的原價位）每年：賺錢的筆數 / 點數（兩口合計）')
        print(f'   {"":<22}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>16}' for nm, a, b in oc.YEARS) + '   v3 那年：回撤、第二口成交率')
        for lab, X, mode in (('兩口都馬上進（v3）', 0, 'now'), ('第二口回檔 0.25R', 0.25, 'scale'), ('第二口回檔 0.5R', 0.5, 'scale'),
                             ('第二口回檔 0.75R', 0.75, 'scale'), ('兩口都等回檔 0.5R', 0.5, 'limit')):
            t = sim(C, T, mix, R, X, mode)
            y = t[t.date > oc.YEARS[3][2]]; eq = np.cumsum(y.pts.values); dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
            print(f'   {lab:<22}' + ''.join(f'{100 * (z.pts > 0).mean():5.0f}% {z.pts.sum():+8.0f}' for z in (t[(t.date >= a) & (t.date <= b)] for nm, a, b in oc.YEARS))
                  + f'   {dd:5.0f} 點、{100 * y.filled.mean() if mode != "now" else 100:3.0f}%')


if __name__ == '__main__':
    main()
