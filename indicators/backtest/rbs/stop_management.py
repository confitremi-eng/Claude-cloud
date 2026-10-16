"""Stop management for Remi's Buy/Sell: is a with-trend trade better off with a looser or close-based stop?

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/stop_management.py

Same entries and the same target (entry +/- R x the original stop distance); only the stop rule changes.
R is always measured in the original stop distance (extreme of the signal bar and the one before), so a stop
that waits for the close can lose more than 1R. A touch stop fills at the stop, or at the open when the bar
opens beyond it. In one bar: stops before the target, the target before a close-based stop. Stop moves
(break-even, trailing) start on the next bar. 60-bar time exit, flat before a hole longer than 30 minutes.
Needs data/setup_signals.pkl from setup_study.py.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import warnings; warnings.simplefilter('ignore', FutureWarning)
import numpy as np
import pandas as pd
from rbs import prepared
from setup_study import CACHE, SPLIT, COST, HORIZON, bar_context, RULE, build

METHODS = {
    'M0': '觸價停損（現在）',
    'M1': '觸價，停損外 0.25 ATR',
    'M2': '觸價，停損外 0.5 ATR',
    'M3': '收線停損，沒有硬停損',
    'M4': '收線停損 + 硬停損外 0.5 ATR',
    'M5': '收線停損 + 硬停損外 1 ATR',
    'M6': '連 2 根收線 + 硬停損外 1 ATR',
    'M7': '前 3 根只用硬停損外 1 ATR，之後觸價',
    'M8': '到 +1R 後停損移到進場價',
    'M9': '到 +1R 後用兩根極值移動停損，不設目標',
    'M10': '觸價停損後 10 根內收回進場價，再進一次',
}


class Bars:
    def __init__(self, tf):
        df = prepared('NQ', tf)
        self.o, self.h, self.l, self.c = df.open.values, df.high.values, df.low.values, df.close.values
        self.nxt, self.atr = bar_context(df, tf)


def sim(b, i, k, risk0, method, R, start=None, entry=None, stop0=None):
    """Returns (gross R in units of risk0, exit bar, reason)."""
    o, h, l, c = b.o, b.h, b.l, b.c
    i0 = i if start is None else start
    e = c[i0] if entry is None else entry
    s0 = e - k * risk0 if stop0 is None else stop0
    end = min(i0 + HORIZON, b.nxt[i0])
    A = b.atr[i0 - 1]
    tgt = None if method == 'M9' else e + k * R * risk0
    touch = hard = closelvl = None; ncl = 0; grace = 0; be = trail = False
    if method in ('M0', 'M8', 'M9', 'M10'): touch = s0
    elif method == 'M1': touch = s0 - k * 0.25 * A
    elif method == 'M2': touch = s0 - k * 0.5 * A
    elif method == 'M3': closelvl, ncl = s0, 1
    elif method == 'M4': closelvl, ncl, hard = s0, 1, s0 - k * 0.5 * A
    elif method == 'M5': closelvl, ncl, hard = s0, 1, s0 - k * 1.0 * A
    elif method == 'M6': closelvl, ncl, hard = s0, 2, s0 - k * 1.0 * A
    elif method == 'M7': touch, grace, hard = s0, 3, s0 - k * 1.0 * A
    be = method == 'M8'; trail = method == 'M9'
    hit = lambda j, lvl: (l[j] <= lvl) if k == 1 else (h[j] >= lvl)
    fill = lambda j, lvl: min(lvl, o[j]) if k == 1 else max(lvl, o[j])
    cnt = 0; moved = False
    for j in range(i0 + 1, end + 1):
        if hard is not None and hit(j, hard):
            return (fill(j, hard) - e) * k / risk0, j, 'stop'
        if touch is not None and j - i0 > grace and hit(j, touch):
            return (fill(j, touch) - e) * k / risk0, j, ('stop' if not moved else 'moved')
        if tgt is not None and ((h[j] >= tgt) if k == 1 else (l[j] <= tgt)):
            return R, j, 'target'
        if closelvl is not None:
            if (c[j] < closelvl) if k == 1 else (c[j] > closelvl):
                cnt += 1
                if cnt >= ncl:
                    return (c[j] - e) * k / risk0, j, 'stop'
            else:
                cnt = 0
        fav = (h[j] - e) if k == 1 else (e - l[j])
        if (be or trail) and not moved and fav >= risk0:
            moved = True
            if be: touch = max(touch, e) if k == 1 else min(touch, e)
        if trail and moved:
            new = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j])
            touch = max(touch, new) if k == 1 else min(touch, new)
    return (c[end] - e) * k / risk0, end, 'time'


def sim_reentry(b, i, k, risk0, R, window=10):
    """M0, and after a stop-out one more entry when a close gets back past the first entry within `window` bars."""
    r1, x1, why = sim(b, i, k, risk0, 'M0', R)
    if why != 'stop':
        return r1, x1, 1
    c, h, l = b.c, b.h, b.l
    e0 = c[i]
    for m in range(x1, min(x1 + window, b.nxt[x1]) + 1):
        if (c[m] > e0) if k == 1 else (c[m] < e0):
            s_new = min(l[m - 1], l[m]) if k == 1 else max(h[m - 1], h[m])
            risk_new = (c[m] - s_new) * k
            if not risk_new > 0 or min(m + HORIZON, b.nxt[m]) <= m:
                break
            r2, x2, _ = sim(b, m, k, risk_new, 'M0', R)
            return r1 + r2 * risk_new / risk0, x2, 2
    return r1, x1, 1


def run(b, sel, method, R):
    out = []
    for i, k, risk0 in zip(sel.i.values, sel.side.values, sel.risk.values):
        if method == 'M10':
            r, x, n = sim_reentry(b, i, k, risk0, R)
        else:
            r, x, _ = sim(b, i, k, risk0, method, R); n = 1
        out.append((r, x, n))
    t = sel[['i', 'side', 'risk', 'date', 'month']].copy()
    t['r'], t['x'], t['ntr'] = [v[0] for v in out], [v[1] for v in out], [v[2] for v in out]
    t['net'] = t.r - t.ntr * COST / t.risk
    return t


def seq(t):
    take = []; busy = -1
    for q, (i, x) in enumerate(zip(t.i.values, t.x.values)):
        if i >= busy: take.append(q); busy = x
    return t.iloc[take]


def line(t):
    net = t.net.values; a = t.date.values < SPLIT
    eq = np.cumsum(net); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq))
    losses = net[net < 0]
    return (f'{len(t):5d} 筆  勝率 {100 * (t.r > 0).mean():4.1f}%  淨 {net.mean():+.3f}R（前 {net[a].mean():+.3f} 後 {net[~a].mean():+.3f}）'
            f'  合計 {net.sum():+6.1f}R  PF {net[net > 0].sum() / -losses.sum():.2f}  回撤 {dd:5.1f}R'
            f'  平均虧損 {losses.mean():+.2f}R  最大虧損 {net.min():+.2f}R')


if __name__ == '__main__':
    s = pd.read_pickle(CACHE) if os.path.exists(CACHE) else build()
    bars = {tf: Bars(tf) for tf in (1, 2, 3, 5)}

    print('######## 1. 推薦規則的同一批 2 分訊號（= 過濾快訊），一次一筆')
    x = s[s.tf == 2].sort_values('i'); sel = x[RULE(x)]
    base = {}
    for R in (2.0, 1.0, 3.0):
        print(f'\n  目標 {R:g}R')
        for m, name in METHODS.items():
            if m == 'M9' and R != 2.0: continue
            t = run(bars[2], sel, m, R)
            if R == 2.0: base[m] = t
            print(f'  {m:<4} {name:<24} {line(seq(t))}')

    print('\n######## 2. 收線停損實際做了什麼（推薦規則訊號，2R，各自獨立）')
    t0, t3, t5 = base['M0'], base['M3'], base['M5']
    stopped = t0.r <= -0.999
    print(f'  觸價停損會出場的 {stopped.sum()} 筆裡：')
    for nm, t in (('收線停損', t3), ('收線 + 硬停損 1 ATR', t5)):
        st = t[stopped.values]
        print(f'    {nm}：之後達標 {(st.r >= 1.999).mean() * 100:4.1f}%，時間出場 {((st.r > -0.999) & (st.r < 1.999)).mean() * 100:4.1f}%，'
              f'還是停損 {(st.r <= -0.999).mean() * 100:4.1f}%（平均 {st.r[st.r <= -0.999].mean():+.2f}R）；這批平均 {st.r.mean():+.3f}R，原本 -1R')
        ok = t[~stopped.values]
        print(f'    {nm}：觸價沒停損的 {len(ok)} 筆，平均 {ok.r.mean():+.3f}R（原本 {t0.r[~stopped].mean():+.3f}R）')

    print('\n######## 3. 順勢 vs 非順勢：每個方法比觸價停損多多少（每筆淨 R，訊號各自獨立，2R）')
    groups = {'順勢（TJ 順勢 + 1h 同向，全天）': lambda x: (x.side * x.dir >= 1) & (x.side == x.h1),
              '非順勢（TJ MIX 或逆勢）': lambda x: x.side * x.dir <= 0}
    for tf in (1, 2, 3, 5):
        x = s[s.tf == tf].sort_values('i')
        for gname, f in groups.items():
            sel = x[f(x)]
            t0 = run(bars[tf], sel, 'M0', 2.0)
            print(f'\n  {tf}m {gname}  {len(sel)} 筆，觸價停損每筆 {t0.net.mean():+.3f}R')
            for m in [k for k in METHODS if k != 'M0']:
                t = run(bars[tf], sel, m, 2.0)
                d = t.net.values - t0.net.values; a = sel.date.values < SPLIT
                print(f'    {m:<4} {METHODS[m]:<24} 差 {d.mean():+.3f} ±{d.std(ddof=1) / np.sqrt(len(d)):.3f}R'
                      f'（前 {d[a].mean():+.3f} 後 {d[~a].mean():+.3f}）  每筆 {t.net.mean():+.3f}R')
