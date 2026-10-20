"""v3 NQ 2m: minimum stop distance in ATR — raise the bar, or widen the stop instead of skipping? (five years)

  cd indicators/backtest
  python3 -I rbs/risk_atr.py

v3 as now (trend time 0-400 for 2m, FOMC days off, one at a time, MIX unchanged). Trend signals with every other v3
filter, then:
  min X     take the signal only if the two-bar stop is >= X ATR (v3: X = 1.0)
  widen X   take every signal; if the two-bar stop is closer than X ATR, put the stop at X ATR from the entry
ATR = ATR14 of the bar before the signal (as v3). 3R target. Also the last 3 months.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import stop_target as stt


def main():
    one = oc.load(); M = oc.Market(one); C = M.ctx(2); df = C.df; th = df.thr.values
    s = mm.trend_signals(df, M.H, 2, 20, 8)
    base = (s.side == s.h1) & ~ss.EVT(s) & (s.slow < 3.0) & (s.spread > th[s.i]) & (s.tm < 400) & ~s.date.isin(ss.FOMC)
    mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC]
    _, atr = ss.bar_context(df, 2)
    own = lambda j, k, e, o: o
    print('NQ 2m v3（趨勢 0–400 分，3R；每年 R：Y1 Y2 Y3 Y4 IS）')
    for X in (0.8, 1.0, 1.2, 1.5):
        T = s[base & (s.risk_atr >= X)]
        t = stt.sim(C, T, mix, 3.0, own, False)
        oc.one_line(f'停損 ≥ {X:g} ATR 才做{"（v3）" if X == 1.0 else ""}（{len(T)}）', t)
        r = t[t.date >= '2026-07-19']; print(f'      最近 3 個月 {len(r)} 筆 {r.net.sum():+.1f}R')
    T = s[base]
    for X in (1.0, 1.2, 1.5):
        f = (lambda X: lambda j, k, e, o: o if abs(e - o) >= X * atr[j - 1] else e - k * X * atr[j - 1])(X)
        t = stt.sim(C, T, mix, 3.0, f, False)
        oc.one_line(f'不到 {X:g} ATR 就把停損放大到 {X:g} ATR（{len(T)}）', t)
        r = t[t.date >= '2026-07-19']; print(f'      最近 3 個月 {len(r)} 筆 {r.net.sum():+.1f}R')
    is_ = lambda t: t[t.date > oc.YEARS[3][2]]
    for lab, T, f in (('v3', s[base & (s.risk_atr >= 1.0)], own),
                      ('放大到 1.2', s[base], lambda j, k, e, o: o if abs(e - o) >= 1.2 * atr[j - 1] else e - k * 1.2 * atr[j - 1]),
                      ('≥ 1.2 才做', s[base & (s.risk_atr >= 1.2)], own)):
        y = oc.year_stats(is_(stt.sim(C, T, mix, 3.0, f, False)))
        print(f'   v3 那年 {lab}：{y["n"]} 筆 勝 {y["win"]:.0f}% 每筆 {y["per"]:+.3f} 合計 {y["tot"]:+.0f} 回撤 {y["dd"]:.0f} 連虧 {y["streak"]} 賺錢月 {y["months"]}')


if __name__ == '__main__':
    main()
