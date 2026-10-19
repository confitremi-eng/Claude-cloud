"""Remi's Buy/Sell (30, 0, 13, 1) -- the setting Remi uses on one-sided days -- with the trend: worth trading?
QQQ 1 minute (NQ cash-session bars), SPY 1 minute (ES cash-session bars) as a check. The Databento year.

  cd indicators/backtest
  python3 -I rbs/oneside_3013.py [qqq spy]

「單邊日」 has to be known at the time: Trend Judge 強 with the trend already long, NQ 2m also 強 the same way, or
the day already moved 0.5 / 1 / 1.5% from the cash open on the signal's side.

Each signal on its own (signal close entry, two-bar stop, 60-bar time exit or the session end, 1 NQ point / 0.2 ES
point cost), split by Trend Judge against the signal (threshold 20 NQ points = QQQ 0.5, 強 40 = QQQ 1.0; SPY 8 / 16
ES points), the indicator's trend minutes, the spread, NQ 2m, and v3's ETF filter (1-hour EMA20 side, stop >= 1 ATR,
distance to the 15 s EMA1130 <= 7 ATR, event windows, NQ 2m not opposite for QQQ). Then the neighbouring settings,
and one position at a time against v3's (35, 0, 8, 1).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import strong_stage as sg

CFG = {'qqq': ('QQQ 1 分 K（NQ 美股盤代替）', 20.0, 40.0, 1.0, True), 'spy': ('SPY 1 分 K（ES 美股盤代替）', 8.0, 16.0, 0.2, False)}


def nq2m_strong():
    """NQ 2m Trend Judge spread (24-hour chart, chart-bar estimate) and each bar's start time."""
    nq1 = mm.load_market('nq', [])
    dn = mm.chart(nq1, mm.minute_trend(nq1), 2, 10.0, 35.0)
    c = dn.close.values
    aF = 1 - (1 - 2 / 1131) ** 24; aS = 1 - (1 - 2 / 1131) ** 8
    d2 = pd.Series(c).ewm(alpha=aF, adjust=False).mean().values - pd.Series(c).ewm(alpha=aS, adjust=False).mean().values
    return d2, pd.DatetimeIndex(dn.datetime).values.astype('datetime64[ns]').astype(np.int64)


def day_move(df, y):
    """Move from the session's first open to the signal close, on the signal's side, in %."""
    day = df.datetime.dt.tz_convert(ss.NY).dt.date.values
    first = pd.Series(df.open.values).groupby(day).transform('first').values
    return (df.close.values[y.i] - first[y.i]) / first[y.i] * 100 * y.side.values


def build(df, H, stage, ema, th, nd):
    s = mm.trend_signals(df, H, 1, stage, ema)
    s['rel'] = np.sign(s.dir.values) * s.side.values            # Trend Judge against the signal: 1 same, 0 MIX, -1 opposite
    s['nq'] = sg.nq_ok(df, s, nd) if nd is not None else True
    s['v3'] = mm.filt(s, th, 7.0) & s.nq
    return s


def run(key, nd):
    name, th, st, cost, nqf = CFG[key]
    one = mm.load_market(key, []); tdm = mm.minute_trend(one); H = mm.hourly(one, True)
    years = (one.index[-1] - one.index[0]).days / 365.25
    df = mm.chart(one, tdm, 1, th, st)
    nd_ = nd if nqf else None
    s = build(df, H, 30, 13, th, nd_)
    d = sorted(s.date.unique()); split = d[len(d) // 2]
    R = lambda y, nm: print(f'   {nm:<30} ' + mm.row_ind(y, cost, split))
    print(f'\n################ {name}：{one.index[0]:%Y-%m-%d} .. {one.index[-1]:%Y-%m-%d}，每筆扣 {cost:g} 點')
    print(f'{"":<32}   筆數   1R 勝率 每筆   2R 勝率 每筆   3R 勝率 每筆')
    print('\n######## 1. (30, 0, 13, 1) 各自獨立')
    same = s.rel > 0; strong = same & (s.spread > st)
    R(s, '全部（原版）')
    R(s[s.rel < 0], 'Trend Judge 反向'); R(s[s.rel == 0], 'Trend Judge MIX')
    R(s[same & ~strong], '順勢（一般）'); R(s[strong], '順勢（強）')
    print('  順勢，依趨勢已持續')
    for lo, hi in ((0, 60), (60, 120), (120, 180), (180, 300), (300, 10 ** 6)):
        R(s[same & (s.tm >= lo) & (s.tm < hi)], f'趨勢 {lo}–{hi if hi < 10 ** 6 else "以上"} 分')
    print('  順勢，依拉開程度（差值 / 強門檻）')
    for lo, hi in ((0, 1), (1, 1.5), (1.5, 2), (2, 99)):
        R(s[same & (s.spread / st >= lo) & (s.spread / st < hi)], f'{lo:g}–{hi if hi < 99 else "以上"} 倍')
    print('  順勢，單邊日的樣子（強、趨勢已持續夠久）')
    for m_ in (60, 120, 180):
        R(s[strong & (s.tm >= m_)], f'強，趨勢 ≥ {m_} 分')
    if nqf:
        R(s[same & s.nq], '順勢 + NQ 2m 不反向')
        R(s[same & ~s.nq], '順勢，NQ 2m 反向')
    mv = day_move(df, s)
    for x in (0.5, 1.0, 1.5):
        R(s[same & (mv >= x)], f'順勢，當天已走 ≥ {x:g}%')
        R(s[s.v3 & (mv >= x)], f'v3 過濾，當天已走 ≥ {x:g}%')
    if nqf:
        d2, nst = NQS
        t_open = pd.DatetimeIndex(df.last_min.values[s.i]).tz_localize('UTC').values.astype('datetime64[ns]').astype(np.int64)
        nq_sp = d2[np.searchsorted(nst, t_open, 'right') - 2] * s.side.values
        R(s[strong & (nq_sp > 35)], '強 + NQ 2m 也強同向')
        R(s[strong & (nq_sp > 35) & (s.tm >= 120)], '強 + NQ 2m 強同向 + 趨勢 ≥ 120 分')
        R(s[strong & (nq_sp > 35) & (mv >= 1.0)], '強 + NQ 2m 強同向 + 當天已走 ≥ 1%')
    R(s[same & (s.side == s.h1)], '順勢 + 1 小時 EMA 同向')
    R(s[s.v3], 'v3 的 ETF 過濾')
    R(s[s.v3 & (s.spread > st)], 'v3 過濾 + 強')
    for side, nm in ((1, '作多'), (-1, '做空')):
        R(s[s.v3 & (s.side == side)], f'v3 過濾，{nm}')

    print('\n######## 2. 附近的參數（v3 的 ETF 過濾）')
    sets = {}
    for stage in (20, 25, 30, 35, 40):
        for ema in (8, 13, 21):
            z = build(df, H, stage, ema, th, nd_); sets[(stage, ema)] = z
            R(z[z.v3], f'({stage}, 0, {ema}, 1)')

    print('\n######## 3. 一次一筆（3R / 2R）')
    v3 = sets[(35, 8)]; base = v3[v3.v3]
    keys = set(zip(base.i, base.side))
    def line(y, Rr):
        t = ss.seq(y.sort_values('i'), Rr)
        n = t[f'r{Rr:g}'].values - cost / t.risk.values; eq = np.cumsum(n)
        dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq) if len(eq) else 0
        mo_ = pd.Series(n).groupby(t.month.values).sum(); a = t.date.values < split
        return (f'{len(t) / years:4.0f} 筆/年  勝率 {100 * (n > 0).mean():4.1f}%  每筆 {n.mean():+.3f}R  每年 {n.sum() / years:+6.1f}R'
                f'  回撤 {dd:5.1f}R  賺錢月份 {(mo_ > 0).sum()}/{len(mo_)}  前/後 {n[a].mean():+.3f}/{n[~a].mean():+.3f}')
    extra = s[s.v3 & np.array([(i, k) not in keys for i, k in zip(s.i, s.side)])]
    rows = [('v3（35, 0, 8, 1）', base), ('(30, 0, 13, 1) + v3 過濾', s[s.v3]), ('(30, 0, 13, 1) 只要順勢', s[same]),
            ('(30, 0, 13, 1) 順勢 + 強', s[strong]), ('v3 + (30, 0, 13, 1) 多出來的', pd.concat([base, extra]).drop_duplicates('i')),
            ('v3 + 多出來的（只在強）', pd.concat([base, extra[extra.spread > st]]).drop_duplicates('i'))]
    for Rr in (3.0, 2.0):
        for nm, y in rows:
            print(f'   {format(Rr, "g") + "R " + nm:<34} ' + line(y, Rr))
    print(f'   v3 + (30, 0, 13, 1) 多出來的：一年 {len(extra) / years:.0f} 個  ' + mm.row_ind(extra, cost, split))


def main():
    keys = [a for a in sys.argv[1:] if a in CFG] or ['qqq', 'spy']
    global NQS
    nd = sg.nq2m_dir() if 'qqq' in keys else None
    NQS = nq2m_strong() if 'qqq' in keys else None
    for k in keys:
        run(k, nd)


if __name__ == '__main__':
    main()
