"""v3 trend signals by where the close is against the 5 s EMA1130 (Trend Judge's fast line) at the signal.

  cd indicators/backtest
  python3 -I rbs/fastline.py [2 | 5]          # default 2

Remi's observation (2026-10-20): a trend sell came while price was already back above the fast line, and such
signals win much less. Side of the fast line = (close - 5 s EMA1130) on the trade's side: + = buy above / sell below
the fast line (with the trend), - = buy below / sell above (price has crossed back). Also the distance in ATR.
v3 frozen rules (rbs/oos_check.py), NQ 2m (or 5m), five years; periods: the v3 year (2025-10 .. 2026-10), 2025-01 ..
2025-10, and the four earlier years. Each signal on its own, then v3 one at a time with the extra condition.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import market_matrix as mm
import oos_check as oc

PERIODS = (('v3 那一年 25/10–26/10', '2025-10-15', '2026-10-18'), ('2025/01–25/10', '2025-01-01', '2025-10-14'),
           ('樣本外 4 年 21/10–25/10', '2021-10-15', '2025-10-14'))


def main(tf=2):
    R_main = 3.0 if tf == 2 else 2.0
    one = oc.load(); M = oc.Market(one); C = M.ctx(tf)
    df = C.df
    s = oc.trend_set(df, M.H, tf, 20, df.thr.values, 3.0, 0, 180)
    lm = pd.DatetimeIndex(df.last_min)
    fast = M.tdm['emaF'].reindex(lm).values
    _, atr = mm.ss.bar_context(df, tf)
    s = s.copy()
    s['fast'] = (df.close.values[s.i] - fast[s.i]) * s.side.values / atr[s.i]
    print(f'NQ {tf} 分 K，v3 的趨勢訊號（凍結規則），每筆扣 1 點；「快線那邊」= 收盤在 5 秒 EMA1130 的哪一邊（+ 順著交易方向）')
    for nm, a, b in PERIODS:
        z = s[(s.date >= a) & (s.date <= b)]
        d = sorted(z.date.unique()); split = d[len(d) // 2]
        R = lambda y, lab: print(f'   {lab:<24} ' + mm.row_ind(y, 1.0, split))
        print(f'\n  ## {nm}')
        print(f'   {"":<24}   筆數   1R 勝率 每筆   2R 勝率 每筆   3R 勝率 每筆')
        R(z, '全部')
        R(z[z.fast > 0], '在快線順向那邊（正常）')
        R(z[z.fast <= 0], '已經回到快線另一邊')
        for lo, hi in ((-99, -0.5), (-0.5, 0), (0, 0.5), (0.5, 1), (1, 99)):
            R(z[(z.fast >= lo) & (z.fast < hi)], f'　離快線 {"" if lo == -99 else format(lo, "+g")}～{"" if hi == 99 else format(hi, "+g")} ATR')
    print(f'\n## 放回 v3（趨勢 + MIX，一次一筆，{R_main:g}R）：趨勢訊號只做在快線順向那邊的；每段的合計 R / 回撤')
    mix = oc.mix_list(C)
    for lab, T in (('v3 現在', s), ('加條件：快線順向', s[s.fast > 0])):
        t = oc.sim(C, T, mix, R_main, R_main)
        parts = []
        for nm, a, b in PERIODS:
            r = oc.year_stats(t[(t.date >= a) & (t.date <= b)])
            parts.append(f'{nm[:10]} {r["tot"]:+6.1f}R / {r["dd"]:4.1f}（{r["n"]} 筆，{r["per"]:+.3f}）')
        print(f'   {lab:<14} ' + '   '.join(parts))


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2)
