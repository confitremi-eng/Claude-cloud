"""Were the stops too tight in the earlier years? v3 (NQ 2m) with other stops and targets, year by year.

  cd indicators/backtest
  python3 -I rbs/stop_target.py [stop ...]      # stops: bar (v3: two-bar extreme), 15 20 30 40 60 (points), a1.5 a2 (x ATR)

Same v3 signals (frozen); only the stop and the target change. The stop is applied to the trend signals and, as a
second row, to the MIX breakouts too (otherwise MIX keeps its box-middle stop). Targets 1 / 1.5 / 2 / 3R. One at a
time, 60-bar exit, 17:00 halt, Friday cut-off, 1 point cost. Prints R per year (Y1-Y4 out of sample, IS = the v3 year).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import market_matrix as mm
import oos_check as oc


def sim(C, trend, mix, R, dist, mix_too):
    """dist(j, side, entry, own_stop) -> stop price."""
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
                risk = abs(ve - vs); out.append((d0, (px - ve) * pos / risk - oc.COST / risk, (px - ve) * pos / risk)); pos = 0
        if not trad[j] or C.halt[j] or C.late[j]: continue
        if pos == 0 and j in mx:
            k, px, st = mx[j]
            if mix_too: st = dist(j, k, px, st)
            pos, ve, vs, vt, vb, d0 = k, px, st, px + R * (px - st), j, C.date[j]
            if (pos == 1 and l[j] <= vs) or (pos == -1 and h[j] >= vs):
                risk = abs(ve - vs); out.append((d0, -1.0 - oc.COST / risk, -1.0)); pos = 0
        if pos == 0 and j in tr:
            k = tr[j]; own = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j])
            st = dist(j, k, c[j], own)
            pos, ve, vs, vt, vb, d0 = k, c[j], st, c[j] + R * (c[j] - st), j, C.date[j]
    return pd.DataFrame(out, columns=['date', 'net', 'R'])


def main():
    names = [a for a in sys.argv[1:]] or ['bar', '15', '20', '30', '40', '60', 'a1.5', 'a2']
    one = oc.load(); M = oc.Market(one); C = M.ctx(2)
    T = oc.trend_set(C.df, M.H, 2, 20, C.df.thr.values, 3.0, 0, 180); mix = oc.mix_list(C)
    _, atr = mm.ss.bar_context(C.df, 2)
    for nm in names:
        if nm == 'bar':
            f = lambda j, k, e, own: own; lab = '兩根 K 極值（v3）'
        elif nm.startswith('a'):
            m = float(nm[1:]); f = (lambda m: lambda j, k, e, own: e - k * m * atr[j - 1])(m); lab = f'{m:g} ATR'
        else:
            p = float(nm); f = (lambda p: lambda j, k, e, own: e - k * p)(p); lab = f'固定 {p:g} 點'
        print(f'\n## 停損：{lab}（每年 R：' + ' '.join(n[:2] for n, a, b in oc.YEARS) + '）')
        for mix_too in ((False, True) if nm != 'bar' else (False,)):
            for R in (1.0, 1.5, 2.0, 3.0):
                t = sim(C, T, mix, R, f, mix_too)
                oc.one_line(f'{"MIX 也用" if mix_too else "只換趨勢"}，{R:g}R', t)


if __name__ == '__main__':
    main()
