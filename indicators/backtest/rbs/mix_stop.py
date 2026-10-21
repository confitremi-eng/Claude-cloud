"""Is the MIX breakout stop (box middle) too wide? Other stops for the MIX breakouts (NQ 2m / 5m, five years).

  cd indicators/backtest
  python3 -I rbs/mix_stop.py

v3 as now (2m trend 0-400, 5m 0-180 + daily SMA5, stop >= 0.95 ATR for trend, FOMC days off, junk time off, one at a
time; trend signals unchanged). Breakout price = box edge + 10% of the box height H; v3 stop = box middle (0.6 H away).
Stops tried, as a distance from the breakout price: 0.6 H (v3), 0.4 H, 0.3 H (= just inside the box edge + 0.2 H),
1 ATR, 1.5 ATR. (The breakout bar's own extreme is not usable: that bar has already traded there, so the stop is hit at once.) Targets: v3's R multiple of the new stop ('R') or the same price as
v3's target ('same target'). Points per contract (1 point cost) and win rate, MIX trades only, per year.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import daily_sma5 as d5


def sim(C, trend, mix, R, stopf, same_target):
    df = C.df; h, l, c = C.h, C.l, C.c
    holeb = np.r_[False, (df.datetime.diff() > pd.Timedelta(minutes=30)).values[1:]]
    trad = df.tradable.values
    tr = {int(i): int(k) for i, k in zip(trend.i, trend.side)}
    mx = {j: (k, px, st) for j, k, px, st, _ in mix}
    out = []; pos = 0
    for j in range(len(c)):
        if pos != 0 and j > vb:
            hs = (l[j] <= vs) if pos == 1 else (h[j] >= vs)
            ht = (h[j] >= vt) if pos == 1 else (l[j] <= vt)
            if hs or ht or j - vb >= 60 or C.halt[j] or holeb[j]:
                px = vs if hs else vt if ht else (c[j - 1] if holeb[j] else c[j])
                out.append((d0, kind, (px - ve) * pos - oc.COST, abs(ve - vs))); pos = 0
        if not trad[j] or C.halt[j] or C.late[j]: continue
        if pos == 0 and j in mx:
            k, px, st0 = mx[j]
            st = stopf(j, k, px, st0)
            tgt = px + R * (px - st0) if same_target else px + R * (px - st)
            pos, ve, vs, vt, vb, d0, kind = k, px, st, tgt, j, C.date[j], 'MIX'
            if (pos == 1 and l[j] <= vs) or (pos == -1 and h[j] >= vs):
                out.append((d0, kind, (vs - ve) * pos - oc.COST, abs(ve - vs))); pos = 0
        if pos == 0 and j in tr:
            k = tr[j]; st = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j])
            pos, ve, vs, vt, vb, d0, kind = k, c[j], st, c[j] + R * (c[j] - st), j, C.date[j], '趨勢'
    return pd.DataFrame(out, columns=['date', 'kind', 'pts', 'risk'])


def main():
    one = oc.load(); M = oc.Market(one); D = d5.daily(one)
    for tf, R, cap in ((2, 3.0, 400), (5, 2.0, 180)):
        C = M.ctx(tf); df = C.df; th = df.thr.values; c = df.close.values; h, l = C.h, C.l
        dt = pd.DatetimeIndex(df.datetime); dt = dt.tz_localize('UTC') if dt.tz is None else dt
        ny = (dt + pd.Timedelta(minutes=tf)).tz_convert(ss.NY); m = np.asarray(ny.hour * 60 + ny.minute); junk = (m >= 720) & (m <= 785)
        sma = D.sma.reindex((dt.tz_convert(ss.NY) + pd.Timedelta(hours=6)).normalize()).values
        _, atr = ss.bar_context(df, tf)
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < cap) & ~s.date.isin(ss.FOMC) & ~junk[s.i]]
        if tf == 5: T = T[np.sign(c[T.i.values] - sma[T.i.values]) == T.side.values]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not junk[x[0]] and (tf != 5 or (x[2] - sma[x[0]]) * x[1] > 0)]
        hb = lambda px, st0: abs(px - st0) / 0.6                     # box height H from the v3 stop distance
        stops = {
            '中線 0.6H（v3）': lambda j, k, px, st0: st0,
            '0.4H': lambda j, k, px, st0: px - k * 0.4 * hb(px, st0),
            '0.3H（區間邊緣內 0.2H）': lambda j, k, px, st0: px - k * 0.3 * hb(px, st0),
            '1 ATR': lambda j, k, px, st0: px - k * atr[j - 1],
            '1.5 ATR': lambda j, k, px, st0: px - k * 1.5 * atr[j - 1],
        }
        med = np.median([abs(x[2] - x[3]) for x in mix if C.date[x[0]] > oc.YEARS[3][2]])
        print(f'\nNQ {tf}m（MIX 單；v3 那年 MIX 停損中位數 {med:.0f} 點，趨勢單 {T[T.date > oc.YEARS[3][2]].risk.median():.0f} 點）每年：勝率 / 點數')
        print(f'   {"":<30}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>16}' for nm, a, b in oc.YEARS) + '   v3 那年：停損中位 / 全部（趨勢 + MIX）點數')
        for same in (False, True):
            for lab, f in stops.items():
                t = sim(C, T, mix, R, f, same); z = t[t.kind == 'MIX']
                y = t[t.date > oc.YEARS[3][2]]
                print(f'   {lab + ("、同目標價" if same else ""):<30}' + ''.join(f'{100 * (q.pts > 0).mean():5.0f}% {q.pts.sum():+7.0f}' for q in (z[(z.date >= a) & (z.date <= b)] for nm, a, b in oc.YEARS))
                      + f'   {z[z.date > oc.YEARS[3][2]].risk.median():4.0f} 點 / {y.pts.sum():+6.0f}')


if __name__ == '__main__':
    main()
