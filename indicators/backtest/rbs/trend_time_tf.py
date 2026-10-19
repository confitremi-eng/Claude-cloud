"""Which trend time gives the best filtered alerts on 3 and 5 minutes (2 minutes for reference)?

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/trend_time_tf.py

Trend time = the indicator's 「趨勢已持續（分鐘）」 on that chart: chart bars since Trend Judge (threshold 10) entered
the current UP / DOWN run, reset by MIX or a turn, times the bar length. Signals = Remi Superb filtered alerts on
that chart (one_minute.signals), each chart's own trade (two-bar stop, fixed R, 60-bar time exit), 1 point cost,
counted on their own. 前 / 後 = before / after 2026-06-01.
Prints
  1. win rate and net R by 30-minute (then wider) buckets of trend time
  2. a scan of windows [lo, hi) in 30-minute steps: the ones with enough signals and both halves positive at 3R,
     ranked by 3R net R and by 1R win rate
  3. the best windows one position at a time (3R, 2R) against all signals
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import one_minute as om

TH = 10.0
BINS = [0, 30, 60, 90, 120, 180, 240, 360, 10 ** 6]
LABELS = ['0–30', '30–60', '60–90', '90–120', '120–180', '180–240', '240–360', '360 以上']
MIN_N = {2: 40, 3: 30, 5: 20}


def with_trend_time(tf):
    s = om.signals(tf)
    df = rbs.prepared('NQ', tf)
    d = df.tj_diff.values
    tdir = np.where(np.isnan(d), 0, np.where(d > TH, 1, np.where(d < -TH, -1, 0)))
    tb = np.zeros(len(d), int)
    for j in range(len(d)):
        tb[j] = (tb[j - 1] + 1) if (j and tdir[j] != 0 and tdir[j] == tdir[j - 1]) else (1 if tdir[j] != 0 else 0)
    f = s[s.filt].copy()
    f['tm'] = tb[f.i.values] * tf
    return f.sort_values('i').reset_index(drop=True)


def cells(y, Rs=(1.0, 2.0, 3.0)):
    if len(y) == 0: return '   0 筆'
    a = y.date.values < ss.SPLIT; out = []
    for R in Rs:
        r = y[f'r{R:g}'].values; nn = r - ss.COST / y.risk.values
        out.append(f'{R:g}R {100 * (r > 0).mean():4.1f}% {nn.mean():+.3f}（{nn[a].mean():+.2f}/{nn[~a].mean():+.2f}）')
    return f'{len(y):4d} 筆  ' + '  '.join(out)


def stat(y, R):
    r = y[f'r{R:g}'].values; nn = r - ss.COST / y.risk.values; a = y.date.values < ss.SPLIT
    return (r > 0).mean(), nn.mean(), nn[a].mean() if a.any() else np.nan, nn[~a].mean() if (~a).any() else np.nan


def seq_line(y, R):
    t = ss.seq(y, R); nn = t[f'r{R:g}'].values - ss.COST / t.risk.values; a = t.date.values < ss.SPLIT
    eq = np.cumsum(nn); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)) if len(eq) else 0.0
    mo = pd.Series(nn).groupby(t.month.values).sum()
    return (f'{len(t):4d} 筆  勝率 {100 * (t[f"r{R:g}"] > 0).mean():4.1f}%  每筆 {nn.mean():+.3f}R（前 {nn[a].sum():+5.1f}R 後 {nn[~a].sum():+5.1f}R）'
            f'  一年 {nn.sum():+6.1f}R  回撤 {dd:4.1f}R  賺錢月份 {(mo > 0).sum()}/{len(mo)}')


def main():
    for tf in (3, 5, 2):
        f = with_trend_time(tf)
        print(f'\n######## {tf} 分 K（過濾訊號 {len(f)} 個）{"，參考" if tf == 2 else ""}')
        print('  ## 1. 依趨勢已持續（分鐘）：勝率 % / 每筆淨 R（前 / 後）')
        lab = pd.cut(f.tm, BINS, right=False, labels=LABELS)
        for l in LABELS:
            print(f'   {l:<8} ' + cells(f[lab == l]))
        print(f'   全部     ' + cells(f))

        rows = []
        for lo in range(0, 361, 30):
            for hi in range(lo + 30, min(lo + 241, 481), 30):
                y = f[(f.tm >= lo) & (f.tm < hi)]
                if len(y) < MIN_N[tf]: continue
                w1, n1, _, _ = stat(y, 1.0)
                w3, n3, a3, b3 = stat(y, 3.0)
                rows.append(dict(lo=lo, hi=hi, n=len(y), win1=w1, net1=n1, win3=w3, net3=n3, a3=a3, b3=b3))
        G = pd.DataFrame(rows)
        ok = G[(G.a3 > 0) & (G.b3 > 0)]
        print(f'\n  ## 2. 掃描範圍（至少 {MIN_N[tf]} 筆、3R 前後半年都賺的 {len(ok)} / {len(G)} 個）')
        print('   3R 每筆最高：')
        for _, x in ok.sort_values('net3', ascending=False).head(5).iterrows():
            print(f'    {x.lo:>3.0f}–{x.hi:<3.0f} 分 {x.n:4.0f} 筆  3R 勝率 {100 * x.win3:4.1f}% 每筆 {x.net3:+.3f}（{x.a3:+.2f}/{x.b3:+.2f}）  1R 勝率 {100 * x.win1:4.1f}%')
        print('   1R 勝率最高：')
        for _, x in ok.sort_values('win1', ascending=False).head(5).iterrows():
            print(f'    {x.lo:>3.0f}–{x.hi:<3.0f} 分 {x.n:4.0f} 筆  1R 勝率 {100 * x.win1:4.1f}% 每筆 {x.net1:+.3f}  3R 每筆 {x.net3:+.3f}（{x.a3:+.2f}/{x.b3:+.2f}）')

        print('\n  ## 3. 一次一筆')
        best = ok.sort_values('net3', ascending=False).head(1)
        cands = [('全部', 0, 10 ** 6), ('30–120 分', 30, 120), ('0–180 分', 0, 180)]
        if len(best):
            b = best.iloc[0]; cands.append((f'3R 最好的 {b.lo:.0f}–{b.hi:.0f} 分', b.lo, b.hi))
        for R in (3.0, 2.0):
            for nm, lo, hi in cands:
                print(f'   {R:g}R {nm:<18} ' + seq_line(f[(f.tm >= lo) & (f.tm < hi)], R))


if __name__ == '__main__':
    main()
