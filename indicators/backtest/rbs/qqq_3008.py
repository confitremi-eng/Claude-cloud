"""QQQ 1-minute original triangles (30, 0, 8, 1): take the trend signals whenever NQ 2 minutes is not against them.

  cd indicators/backtest
  python3 -I rbs/qqq_3008.py

Remi's rule: a buy triangle while QQQ's Trend Judge is UP / 強UP (a trend buy), taken when NQ 2m is UP or MIX (not
DOWN); sells the mirror image. No other filter. QQQ = NQ cash-session bars for the Databento year (threshold 20 NQ
points = QQQ 0.5, 強 40), and ZeroGEX's real QQQ candles (2026-07 .. 10, threshold 0.5) as a check. NQ 2m = the
24-hour NQ chart, the previous completed 2-minute bar, Trend Judge from chart bars (as v3 reads it).
Signal close entry, two-bar stop, 60-bar time exit or the session end; 1 NQ point / 2.4 cents cost.
Each signal on its own by NQ 2m state and with v3's other filters added one at a time; then one position at a time
against v3's QQQ setting (35, 0, 8, 1) + ETF filter + NQ 2m not opposite.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import strong_stage as sg
import gex_qqq as gq


def nq_rel(df, s, nd):
    """NQ 2m Trend Judge against each signal: 1 same side, 0 MIX, -1 against."""
    ndir, nstart = nd
    t_open = pd.DatetimeIndex(df.last_min.values[s.i]).tz_localize('UTC').values.astype('datetime64[ns]').astype(np.int64)
    k = np.searchsorted(nstart, t_open, 'right') - 2
    return ndir[k] * s.side.values


def seq_line(y, R, cost, years, split):
    t = ss.seq(y.sort_values('i'), R)
    if len(t) == 0: return '   0'
    n = t[f'r{R:g}'].values - cost / t.risk.values; eq = np.cumsum(n)
    dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
    mo = pd.Series(n).groupby(t.date.str[:7].values).sum(); a = t.date.values < split
    return (f'{len(t) / years:4.0f} 筆/年  勝率 {100 * (n > 0).mean():4.1f}%  每筆 {n.mean():+.3f}R  每年 {n.sum() / years:+6.1f}R'
            f'  回撤 {dd:5.1f}R  賺錢月 {(mo > 0).sum()}/{len(mo)}  前/後 {n[a].mean():+.3f}/{n[~a].mean():+.3f}')


def run(name, one, cost, th, st, nd, start, end):
    tdm = mm.minute_trend(one); H = mm.hourly(one, True)
    df = mm.chart(one, tdm, 1, th, st)
    years = max((pd.Timestamp(end) - pd.Timestamp(start)).days, 1) / 365.25
    out = {}
    for stage in (30, 35):
        s = mm.trend_signals(df, H, 1, stage, 8)
        s = s[(s.date >= start) & (s.date <= end)].copy()
        s['qtj'] = np.sign(s.dir.values) * s.side.values          # QQQ Trend Judge on the signal's side
        s['nq'] = nq_rel(df, s, nd)
        s['h1ok'] = s.side == s.h1
        s['riskok'] = s.risk_atr >= 1.0
        s['evtok'] = ~ss.EVT(s)
        s['distok'] = s.slow < 7.0
        out[stage] = s
    s = out[30]
    d = sorted(s.date.unique()); split = d[len(d) // 2]
    R = lambda y, nm: print(f'   {nm:<30} ' + mm.row_ind(y, cost, split))
    print(f'\n################ {name}：{d[0]} .. {d[-1]}（{len(d)} 天），每筆扣 {cost:g}；前 / 後 = 前後各半的日期')
    print(f'{"":<33}   筆數   1R 勝率 每筆   2R 勝率 每筆   3R 勝率 每筆')
    rule = (s.qtj > 0) & (s.nq >= 0)
    for side, nm in ((1, '買'), (-1, '賣')):
        z = s[s.side == side]; tr = z.qtj > 0
        print(f'\n  ## (30, 0, 8, 1) {nm}')
        R(z, f'原版全部{nm}')
        R(z[tr], f'QQQ 順勢{nm}（Trend Judge 同向）')
        R(z[tr & (z.nq > 0)], f'　NQ 2m 同向')
        R(z[tr & (z.nq == 0)], f'　NQ 2m MIX')
        R(z[tr & (z.nq < 0)], f'　NQ 2m 逆勢（排除）')
        m = tr & (z.nq >= 0)
        R(z[m], f'★ 順勢 + NQ 不逆勢')
        R(z[m & z.h1ok], '　+ 1 小時 EMA 同向')
        R(z[m & z.riskok], '　+ 停損 ≥ 1 ATR')
        R(z[m & z.evtok], '　+ 避開事件時段')
        R(z[m & z.distok], '　+ 離慢線 ≤ 7 ATR')
        R(z[m & z.h1ok & z.riskok & z.evtok & z.distok], '　+ 全部 v3 條件')
        for lo, hi in ((0, 60), (60, 180), (180, 10 ** 6)):
            R(z[m & (z.tm >= lo) & (z.tm < hi)], f'　趨勢 {lo}–{hi if hi < 10 ** 6 else "以上"} 分')
    print('\n  ## 買賣合起來')
    R(s[rule], '★ 順勢 + NQ 不逆勢（買 + 賣）')
    print('\n  ## 一次一筆')
    v = out[35]
    v3 = v[(v.qtj > 0) & (v.spread > th) & v.h1ok & v.riskok & v.evtok & v.distok & (v.nq >= 0)]
    rows = [('★ 只做買', s[rule & (s.side == 1)]), ('★ 買 + 賣', s[rule]),
            ('★ 買 + 全部 v3 條件', s[rule & (s.side == 1) & s.h1ok & s.riskok & s.evtok & s.distok]),
            ('對照：v3 的 QQQ（35, 0, 8, 1）', v3)]
    for Rr in (1.0, 2.0, 3.0):
        for nm, y in rows:
            print(f'   {format(Rr, "g") + "R " + nm:<34} ' + seq_line(y, Rr, cost, years, split))


def main():
    nd = sg.nq2m_dir()
    run('QQQ 1 分 K（NQ 美股盤代替）', mm.load_market('qqq', []), 1.0, 20.0, 40.0, nd, '2025-10-20', '2026-10-14')
    one = gq.real_qqq(); days = sorted(set(one.index.tz_convert(ss.NY).date))
    run('QQQ 1 分 K（ZeroGEX 的 QQQ 實際 K 棒）', one, 0.024, 0.5, 1.0, nd, str(days[3]), '2026-10-14')


if __name__ == '__main__':
    main()
