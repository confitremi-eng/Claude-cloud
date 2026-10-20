"""Which 1-hour EMA for v3's same-side filter? (NQ 2m / 5m, five years)

  cd indicators/backtest
  python3 -I rbs/h1_span.py

v3 = 1h EMA20 (last closed hour's close vs its EMA). Other spans 5-200, and no filter. MIX unchanged, FOMC days off,
one at a time; also each trend signal on its own (flip_wait.each).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import flip_wait as fw
import m30_ema as m30

SPANS = (5, 10, 15, 20, 30, 50, 89, 100, 200)


def main():
    one = oc.load(); M = oc.Market(one)
    Hs = {n: m30.htf(one, 60, n) for n in SPANS}
    for tf, R in ((2, 3.0), (5, 2.0)):
        C = M.ctx(tf); df = C.df; th = df.thr.values
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC]
        print(f'\nNQ {tf}m（FOMC 整天不做；每年 R：Y1 Y2 Y3 Y4 IS）')
        for n in (0,) + SPANS:
            s = mm.trend_signals(df, Hs[n if n else 20], tf, 20, 8)
            m = (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.slow < 3.0) & (s.spread > th[s.i]) & (s.tm < 180) & ~s.date.isin(ss.FOMC)
            if n: m &= s.side == s.h1
            T = s[m]
            oc.one_line(f'{"不過濾" if not n else f"1h EMA{n}"}{"（v3）" if n == 20 else ""}（{len(T)}）', oc.sim(C, T, mix, R, R))
            e = fw.each(C, T, R); oos = (T.date <= oc.YEARS[3][2]).values
            print(f'      單獨進場：樣本外 每筆 {e[oos].mean():+.2f}R；v3 那年 {(~oos).sum()} 筆 勝 {100 * (e[~oos] > 0).mean():.0f}% 每筆 {e[~oos].mean():+.2f}R')


if __name__ == '__main__':
    main()
