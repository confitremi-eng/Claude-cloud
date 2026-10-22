"""Big gap down, trade the gap fill with raw 1m RTH buy signals (no filters). NQ cash-session bars stand in for QQQ.

  cd indicators/backtest
  python3 -I rbs/gapfill_1m.py [data.csv]           # default: data/NQ_1m_databento.csv; works on NQ_1m_5y.csv

Chart = weekday 09:30-16:00 ET bars only (as a QQQ chart); signals = the original rule (N, 0, E, 1) / EMA off on that
chart, buys only. Day = gap <= G (09:30 open vs the previous session's 15:59 close). A buy counts while the gap is
still open (close below the previous close) and inside the entry window; one position at a time, and no new entry
after the gap has filled that day.
Exit: target = the previous close (gap fill), or 1R / 2R; stop = the signal's two-bar low or the day's low so far
(1 tick below); flat at 16:00; 1 point cost. The fill target's R is whatever the distance gives (reported).
Prints
  1. how often the gap fills, by gap size
  2. parameters x stop x target for gap <= -0.75% (entries 09:31-16:00 and 09:45-12:00)
  3. the best few by halves (1-year file) or by year (5-year file), and gap <= -0.5% / -1%
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import itertools
import numpy as np
import pandas as pd
import gapdown_long as gl

COST = 1.0
PARAMS = ((20, 8), (35, 8), (35, 13), (20, 0), (35, 0))          # (stage, EMA); EMA 0 = Ema enable off
STOPS = ('兩根低點', '當天低點')
TARGETS = ('補缺口', '1R', '2R')
WINDOWS = (('全天', 571, 960), ('09:45–12:00', 585, 720))


def raw_buys(h, l, c, stage, ema):
    lo = pd.Series(l).rolling(stage).min().shift().values
    e = pd.Series(c).ewm(span=max(ema, 1), adjust=False).mean().values
    buy = np.zeros(len(c), bool); arm = False; ref = np.nan
    for i in range(stage, len(c)):
        trig = arm and c[i] > ref
        if trig and (ema == 0 or c[i] > e[i]): buy[i] = True
        if trig: arm = False
        elif l[i] < lo[i]: arm = True; ref = h[i]
    return buy


def run(one, days, stage, ema, gmax, stop_kind, tgt_kind, win):
    h, l, c, mins = one.high.values, one.low.values, one.close.values, one['min'].values
    buy = raw_buys(h, l, c, stage, ema)
    out = []
    for d, (a, b, pc, gap) in days.items():
        if gap > gmax: continue
        busy = a; filled = False
        lod = np.minimum.accumulate(l[a:b])
        for i in range(a + 1, b - 1):
            if h[i] >= pc: filled = True
            if filled: break
            if i < busy or not buy[i] or not (win[1] <= mins[i] + 1 < win[2]) or c[i] >= pc: continue
            stop = (min(l[i - 1], l[i]) if stop_kind == '兩根低點' else lod[i - a]) - 0.25
            risk = c[i] - stop
            if risk <= 0: continue
            tgt = pc if tgt_kind == '補缺口' else c[i] + (1 if tgt_kind == '1R' else 2) * risk
            r = None; ex = b - 1
            for q in range(i + 1, b):
                if l[q] <= stop: r = -1.0; ex = q; break
                if h[q] >= tgt: r = (tgt - c[i]) / risk; ex = q; break
            if r is None: r = (c[b - 1] - c[i]) / risk
            out.append(dict(date=d, gap=gap, risk=risk, r=r, net=r - COST / risk, fill_R=(pc - c[i]) / risk, emin=mins[i] + 1))
            busy = ex + 1
    return pd.DataFrame(out)


def summ(t):
    if len(t) < 3: return f'{len(t):4d} 筆'
    eq = np.cumsum(t.net.values); dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
    return (f'{len(t):4d} 筆（{t.date.nunique():2d} 天） 勝 {100 * (t.net > 0).mean():3.0f}%  每筆 {t.net.mean():+.2f}R  一年 {t.net.sum():+6.1f}R'
            f'  回撤 {dd:4.1f}R  停損中位 {t.risk.median():4.0f} 點  補缺口距離中位 {t.fill_R.median():4.1f}R')


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'NQ_1m_databento.csv')
    one = gl.load(path).reset_index()
    days = {}; prev = None
    for d, g in one.groupby('day', sort=True):
        a, b = g.index[0], g.index[-1] + 1
        if prev is not None:
            days[d] = (a, b, prev, 100 * (one.open.values[a] / prev - 1))
        prev = one.close.values[b - 1]
    h = one.high.values
    years = len(days) / 250
    print(f'{os.path.basename(path)}：{len(days)} 天，約 {years:.1f} 年；「一年」欄是整段的總和')

    print('\n######## 1. 低開當天回補昨收的比例')
    for gm in (-0.5, -0.75, -1.0, -1.5):
        x = [(h[a:b].max() >= pc) for d, (a, b, pc, gap) in days.items() if gap <= gm]
        print(f'  缺口 ≤ {gm:5g}%：{len(x):3d} 天，回補 {100 * np.mean(x):3.0f}%')

    res = {}
    for win in WINDOWS:
        print(f'\n######## 2. 缺口 ≤ −0.75%，進場 {win[0]}（訊號在缺口還沒補之前）')
        for (stage, ema), sk, tk in itertools.product(PARAMS, STOPS, TARGETS):
            t = run(one, days, stage, ema, -0.75, sk, tk, win)
            res[(win[0], stage, ema, sk, tk)] = t
            lab = f'({stage}, 0, {ema if ema else "-"}, {1 if ema else 0}) {sk} {tk}'
            print(f'  {lab:<26}{summ(t)}')

    print('\n######## 3. 最好的 6 組：前後半 / 各年，缺口大小')
    key = sorted(res, key=lambda k: res[k].net.sum() if len(res[k]) else -99, reverse=True)[:6]
    dl = sorted(days); split = years < 2; mid = dl[len(dl) // 2]
    for k in key:
        t = res[k]
        parts = [('前', t[t.date < mid]), ('後', t[t.date >= mid])] if split else [(y, t[t.date.str[:4] == y]) for y in sorted({d[:4] for d in dl})]
        print(f'  {k[0]} ({k[1]}, 0, {k[2] if k[2] else "-"}, {1 if k[2] else 0}) {k[3]} {k[4]}：' +
              '  '.join(f'{nm} {len(p)} 筆 勝 {100 * (p.net > 0).mean() if len(p) else 0:3.0f}% {p.net.sum():+5.1f}R' for nm, p in parts))
        win = [w for w in WINDOWS if w[0] == k[0]][0]
        for gm in (-0.5, -1.0):
            print(f'      缺口 ≤ {gm:g}%  {summ(run(one, days, k[1], k[2], gm, k[3], k[4], win))}')


if __name__ == '__main__':
    main()
