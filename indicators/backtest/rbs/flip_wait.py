"""A new trend in the opposite direction: wait before taking its trend signals (v3, NQ 2m / 5m, five years).

  cd indicators/backtest
  python3 -I rbs/flip_wait.py

Remi's case: Trend Judge was DOWN, the bounce turns it (through MIX) into UP, and the first buy right away fails.
For each v3 trend signal: run age = minutes since the current Trend Judge run began (chart bars, trading time);
previous run = the side Trend Judge was on before this run (skipping MIX). A "reversal run" is one whose previous run
was the opposite side; a "continuation run" came back to the same side after MIX.
Rule tested: in a reversal run, skip trend signals until the run is >= W minutes old (continuation runs unchanged;
optionally only when the previous opposite run ended less than G minutes before). MIX breakouts unchanged.
v3 otherwise frozen (FOMC days off), one at a time.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import oos_check as oc


def run_info(df):
    """per bar: side of the previous non-MIX run, and bars since that run's last bar."""
    d = np.sign(df.tj_dir.values).astype(int); n = len(d)
    prev = np.zeros(n, int); gap = np.full(n, 10 ** 9)
    cur = 0; last_side = 0; last_end = -10 ** 9; p = 0; g = 10 ** 9
    for j in range(n):
        if d[j] != 0 and d[j] != cur:            # a new run begins
            p = last_side; g = j - last_end
        if d[j] != 0:
            last_side, last_end = d[j], j
        cur = d[j] if d[j] != 0 else 0
        prev[j] = p; gap[j] = g
    return prev, gap


def main():
    one = oc.load(); M = oc.Market(one)
    for tf, R in ((2, 3.0), (5, 2.0)):
        C = M.ctx(tf); df = C.df
        T = oc.trend_set(df, M.H, tf, 20, df.thr.values, 3.0, 0, 180)
        T = T[~T.date.isin(ss.FOMC)]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC]
        prev, gap = run_info(df)
        rev = prev[T.i.values] == -T.side.values; gp = gap[T.i.values] * tf; tm = T.tm.values
        base = oc.sim(C, T, mix, R, R)
        print(f'\nNQ {tf}m（v3 含 FOMC 整天不做；每年 R：Y1 Y2 Y3 Y4 IS）  趨勢訊號 {len(T)}，反向轉來的 {rev.sum()}')
        # how do the trend signals themselves do, by group
        tt = base[base.kind == '趨勢'] if 'kind' in base else None
        oc.one_line('v3 現在', base)
        for W in (10, 20, 30, 45, 60):
            for G, lab in ((10 ** 9, ''), (60, '，反向趨勢 60 分內結束')):
                keep = ~(rev & (tm < W) & (gp <= G))
                oc.one_line(f'反向新趨勢 < {W} 分不做{lab}', oc.sim(C, T[keep], mix, R, R))
                print(f'      擋掉 {(~keep).sum()} 個趨勢訊號')


if __name__ == "__main__" and len(sys.argv) == 1:
    main()


def each(C, T, R):
    """each trend signal on its own (no one-at-a-time), net R."""
    h, l, c = C.h, C.l, C.c; out = []
    for i, k in zip(T.i.values, T.side.values):
        st = min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i]); e = c[i]; tg = e + R * (e - st); risk = abs(e - st)
        px = c[min(i + 60, len(c) - 1)]
        for j in range(i + 1, min(i + 61, len(c))):
            if (l[j] <= st) if k == 1 else (h[j] >= st): px = st; break
            if (h[j] >= tg) if k == 1 else (l[j] <= tg): px = tg; break
            if C.halt[j]: px = c[j]; break
        out.append((e - px) * -k / risk - oc.COST / risk if False else (px - e) * k / risk - oc.COST / risk)
    return np.array(out)


def flips(df, hours, tf):
    """number of Trend Judge side changes (MIX skipped) in the last `hours`."""
    d = np.sign(df.tj_dir.values).astype(int); n = len(d); ch = np.zeros(n, int); last = 0
    for j in range(n):
        if d[j] != 0:
            if last != 0 and d[j] != last: ch[j] = 1
            last = d[j]
    cs = np.cumsum(ch); w = int(hours * 60 / tf)
    return cs - np.r_[np.zeros(w, int), cs[:-w]]


def groups():
    one = oc.load(); M = oc.Market(one)
    for tf, R in ((2, 3.0), (5, 2.0)):
        C = M.ctx(tf); df = C.df
        T = oc.trend_set(df, M.H, tf, 20, df.thr.values, 3.0, 0, 180); T = T[~T.date.isin(ss.FOMC)]
        net = each(C, T, R); prev, gap = run_info(df)
        rev = prev[T.i.values] == -T.side.values; tm = T.tm.values
        oos = (T.date <= oc.YEARS[3][2]).values; ins = ~oos
        def row(lab, m):
            a, b = net[m & oos], net[m & ins]
            print(f'   {lab:<28} 樣本外 {len(a):4d} 筆 勝 {100 * (a > 0).mean() if len(a) else 0:3.0f}% 每筆 {a.mean() if len(a) else 0:+.2f}R'
                  f'   v3 那年 {len(b):3d} 筆 勝 {100 * (b > 0).mean() if len(b) else 0:3.0f}% 每筆 {b.mean() if len(b) else 0:+.2f}R')
        print(f'\nNQ {tf}m 每個趨勢訊號單獨進場（{R:g}R）')
        row('全部', np.ones(len(T), bool))
        row('同向延續（MIX 後回原方向）', ~rev); row('反向轉來', rev)
        for a, b in ((0, 30), (30, 60), (60, 120), (120, 999)):
            row(f'反向轉來，趨勢 {a}–{b} 分', rev & (tm >= a) & (tm < b))
        for hrs in (2, 4):
            f = flips(df, hrs, tf)[T.i.values]
            for k in (0, 1, 2, 3):
                row(f'過去 {hrs} 小時翻 {k}{"+" if k == 3 else ""} 次', (f >= k) if k == 3 else (f == k))


if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == 'groups':
    groups()
