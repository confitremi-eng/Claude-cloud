"""After a Trend Judge trend has lasted 200 minutes, is a big reversal more likely? (NQ 2m, five years)

  cd indicators/backtest
  python3 -I rbs/trend_old.py

Trend age = v3's 趨勢時間 (minutes the current Trend Judge run has lasted; any MIX bar resets it). For every run that
reaches age A (A = 30 ... 400 minutes), at the bar it gets there, look ahead (within the same session, stop at gaps):
  - the run ends (Trend Judge leaves its side) within the next 60 minutes
  - Trend Judge turns to the opposite side within 120 / 240 minutes
  - price move in the trend direction after 60 / 120 / 240 minutes, in ATR (2m ATR14)
  - big reversal: price goes 5 ATR against the trend before 5 ATR with it (within 240 minutes)
Out of sample (2021-10 .. 2025-10) and the v3 year shown apart.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import oos_check as oc

AGES = (30, 60, 120, 180, 200, 240, 300, 400)


def main():
    one = oc.load(); M = oc.Market(one); C = M.ctx(2); df = C.df; tf = 2
    h, l, c = C.h, C.l, C.c; n = len(c)
    nxt, atr = ss.bar_context(df, tf)
    d = np.sign(df.tj_dir.values).astype(int); tm = df.tmin.values
    date = np.array(C.date); is_ = date > oc.YEARS[3][2]; ok = (date >= oc.YEARS[0][1]) & (date <= oc.YEARS[4][2])
    rows = []
    for A in AGES:
        for j in np.where((tm == A) & ok)[0]:
            k = d[j]; a = atr[j]; e = nxt[j]
            if a <= 0 or np.isnan(a): continue
            def ahead(m): return min(j + m // tf, e)
            seg = d[j + 1:ahead(60) + 1]; end60 = (seg != k).any()
            opp = [(d[j + 1:ahead(m) + 1] == -k).any() for m in (120, 240)]
            mv = [(c[ahead(m)] - c[j]) * k / a if ahead(m) - j >= m // tf * 0.8 else np.nan for m in (60, 120, 240)]
            big = np.nan; e4 = ahead(240)
            for i in range(j + 1, e4 + 1):
                adv = (c[j] - l[i]) if k == 1 else (h[i] - c[j]); fav = (h[i] - c[j]) if k == 1 else (c[j] - l[i])
                if adv >= 5 * a: big = 1; break
                if fav >= 5 * a: big = 0; break
            rows.append((A, is_[j], end60, *opp, *mv, big))
    r = pd.DataFrame(rows, columns=['A', 'is', 'end60', 'opp120', 'opp240', 'm60', 'm120', 'm240', 'big'])
    for lab, z in (('樣本外 2021/10–2025/10', r[~r['is']]), ('v3 那年 2025/10–2026/10', r[r['is']])):
        print(f'\n{lab}（NQ 2m；移動以 ATR 計，正 = 順著原趨勢）')
        print(f'   {"趨勢已持續":<8} {"次數":>5} {"60 分內結束":>9} {"120 分內轉反向":>11} {"240 分內轉反向":>11} {"之後 60 分":>8} {"120 分":>7} {"240 分":>7} {"先逆 5 ATR":>9}')
        for A in AGES:
            y = z[z.A == A]
            print(f'   {A:>5} 分   {len(y):5d} {100 * y.end60.mean():9.0f}% {100 * y.opp120.mean():12.0f}% {100 * y.opp240.mean():12.0f}%'
                  f' {y.m60.mean():+9.2f} {y.m120.mean():+7.2f} {y.m240.mean():+7.2f} {100 * y.big.mean():9.0f}%')


if __name__ == '__main__':
    main()
