"""In a strong trend, does a shorter 「階段」 do better? QQQ / SPY 1 minute (v3's ETF setting 35 -> 30 / 25 / 20 / 15),
NQ 2 minutes (20 -> 15 / 12 / 10) as a check. The Databento year.

  cd indicators/backtest
  python3 -I rbs/strong_stage.py [qqq spy nq]

Signals = v3 on that chart. QQQ (NQ cash-session bars): (35, 0, 8, 1), Trend Judge threshold 20 NQ points (QQQ 0.5),
distance 7 ATR, NQ 2m not opposite (the previous completed 24-hour NQ 2m bar, as the indicator reads it). SPY (ES
cash-session bars): threshold 8 ES points (SPY 0.8), distance 7 ATR. NQ 2m: (20, 0, 8, 1), threshold 10, distance
3 ATR, trend 0-180 minutes, plus the MIX breakout (no MIX 16-20 New York) in the one-at-a-time runs.
「拉開」 = the Trend Judge spread on the signal's side at the signal bar, in multiples of the 強 threshold
(QQQ 40 NQ points = 1.0, SPY 16 ES points = 1.6, NQ 35).
Prints
  1. each signal on its own, by 階段 and spread band (1R / 2R / 3R win % and net R, 3R halves)
  2. the extra signals a shorter 階段 adds when the spread is wide (bars that are not a signal of the normal 階段)
  3. 「normal 階段, plus the shorter one when the spread is wide」, one position at a time, against v3
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd

import setup_study as ss

import market_matrix as mm
import mix_opt as mo

CFG = {  # key: (name, tf, threshold, strong, cost, distance, base stage, shorter stages, NQ 2m filter, window, target R)
    'qqq': ('QQQ 1 分 K（NQ 美股盤代替）', 1, 20.0, 40.0, 1.0, 7.0, 35, (30, 25, 20, 15), True, 10 ** 9, 3.0),
    'spy': ('SPY 1 分 K（ES 美股盤代替）', 1, 8.0, 16.0, 0.2, 7.0, 35, (30, 25, 20, 15), False, 10 ** 9, 3.0),
    'nq': ('NQ 2 分 K', 2, 10.0, 35.0, 1.0, 3.0, 20, (15, 12, 10), False, 180, 3.0),
}
BANDS = ((0, 1), (1, 1.5), (1.5, 2), (2, 99))
WIDE = (1.0, 1.5, 2.0)


def nq2m_dir():
    """NQ 2m Trend Judge (24-hour chart, chart-bar estimate like the indicator) and each bar's start time."""
    nq1 = mm.load_market('nq', [])
    dn = mm.chart(nq1, mm.minute_trend(nq1), 2, 10.0, 35.0)
    c = dn.close.values
    aF = 1 - (1 - 2 / 1131) ** 24; aS = 1 - (1 - 2 / 1131) ** 8
    d2 = pd.Series(c).ewm(alpha=aF, adjust=False).mean().values - pd.Series(c).ewm(alpha=aS, adjust=False).mean().values
    return np.where(d2 > 10, 1, np.where(d2 < -10, -1, 0)), pd.DatetimeIndex(dn.datetime).values.astype('datetime64[ns]').astype(np.int64)


def nq_ok(df, y, nd):
    ndir, nstart = nd
    t_open = pd.DatetimeIndex(df.last_min.values[y.i]).tz_localize('UTC').values.astype('datetime64[ns]').astype(np.int64)
    k = np.searchsorted(nstart, t_open, 'right') - 2                  # the NQ 2m bar before the one holding this bar
    return ndir[k] * y.side.values >= 0


def seq_line(t, cost, years, split):
    if len(t) == 0: return '   0'
    n = t.r3.values - cost / t.risk.values; eq = np.cumsum(n); dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
    mo_ = pd.Series(n).groupby(t.month.values).sum(); a = t.date.values < split
    return (f'{len(t) / years:5.0f} 筆/年  勝率 {100 * (t.r3 > 0).mean():4.1f}%  每筆 {n.mean():+.3f}R  每年 {n.sum() / years:+6.1f}R'
            f'  回撤 {dd:5.1f}R  賺錢月份 {(mo_ > 0).sum()}/{len(mo_)}  前/後 {n[a].mean():+.3f}/{n[~a].mean():+.3f}')


def run(key, nd):
    name, tf, th, st, cost, dist, base, alts, nqf, hi, R = CFG[key]
    one = mm.load_market(key, []); tdm = mm.minute_trend(one); H = mm.hourly(one, mm.MARKETS[key][5])
    years = (one.index[-1] - one.index[0]).days / 365.25
    df = mm.chart(one, tdm, tf, th, st)
    sets = {}
    for stage in (base,) + alts:
        s = mm.trend_signals(df, H, tf, stage, 8)
        F = s[mm.filt(s, th, dist) & (s.tm < hi)].copy()
        if nqf: F = F[nq_ok(df, F, nd)]
        F['wide'] = F.spread / st
        sets[stage] = F
    d = sorted(sets[base].date.unique()); split = d[len(d) // 2]
    print(f'\n################ {name}：{one.index[0]:%Y-%m-%d} .. {one.index[-1]:%Y-%m-%d}，強 = 差值 {st:g}，每筆扣 {cost:g} 點')
    print(f'{"":<30}   筆數   1R 勝率 每筆   2R 勝率 每筆   3R 勝率 每筆')
    print('\n######## 1. 各自獨立：階段 × 拉開程度（差值 / 強門檻）')
    for lo, up in BANDS:
        for stage in (base,) + alts:
            F = sets[stage]; m = (F.wide >= lo) & (F.wide < up)
            lab = f'{"一般" if lo == 0 else "拉開 " + format(lo, "g") + "–" + (format(up, "g") if up < 99 else "以上") + " 倍"}  階段 {stage}'
            print(f'   {lab:<28} ' + mm.row_ind(F[m], cost, split))
        print()
    print(f'######## 2. 拉開時，短階段多出來的訊號（同一根 K 不是階段 {base} 的訊號）')
    keys = set(zip(sets[base].i, sets[base].side))
    extra = {}
    for stage in alts:
        F = sets[stage]; new = np.array([(i, k) not in keys for i, k in zip(F.i, F.side)])
        for x in WIDE:
            E = F[new & (F.wide >= x)]; extra[(stage, x)] = E
            print(f'   {"階段 " + str(stage) + "，拉開 ≥ " + format(x, "g") + " 倍":<28} ' + mm.row_ind(E, cost, split))
        print(f'   {"階段 " + str(stage) + "，沒拉開（對照）":<28} ' + mm.row_ind(F[new & (F.wide < 1)], cost, split))
    print(f'\n######## 3. 階段 {base}，拉開時再加短階段的訊號（一次一筆，{R:g}R）')
    if key == 'nq':
        C = mo.Ctx(tf, one, tdm, H)
        mix = [x for x in mo.breaks(C, mo.boxes(C)) if x[4]['sess'] != '收盤後 16-20']
        h, l = C.h, C.l
        def combo(F):
            C.trend = {int(i): (int(k), (min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])), '趨勢') for i, k in zip(F.i, F.side)}
            return mo.seq(C, mix, R)
        print(f'   {"v3（階段 " + str(base) + "，含 MIX）":<28} ' + combo(sets[base]))
    else:
        def combo(F):
            return seq_line(ss.seq(F.sort_values('i'), R), cost, years, split)
        print(f'   {"v3（階段 " + str(base) + "）":<28} ' + combo(sets[base]))
    for stage in alts:
        print(f'   {"全部改成階段 " + str(stage):<28} ' + combo(sets[stage]))
        for x in WIDE:
            U = pd.concat([sets[base], extra[(stage, x)]]).sort_values('i').drop_duplicates('i')
            print(f'   {"+ 階段 " + str(stage) + "（拉開 ≥ " + format(x, "g") + " 倍）":<28} ' + combo(U))


def main():
    keys = [a for a in sys.argv[1:] if a in CFG] or ['qqq', 'spy', 'nq']
    nd = nq2m_dir() if 'qqq' in keys else None
    for k in keys:
        run(k, nd)


if __name__ == '__main__':
    main()
