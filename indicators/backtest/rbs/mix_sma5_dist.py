"""5m MIX breakouts by how far the breakout price is from the daily SMA5 (on the SMA5's side, as v3 trades them).

  cd indicators/backtest
  python3 -I rbs/mix_sma5_dist.py

Each breakout on its own (stop = box middle, 60 bars, halt, 1 point cost): 1R and 2R hit rate and R per trade at 2R,
by distance |breakout price - SMA5| as % of price; the v3 year and the four years before. Also the opposite side
(against the SMA5), which v3 now skips.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import oos_check as oc
import daily_sma5 as d5


def main():
    one = oc.load(); M = oc.Market(one); D = d5.daily(one)
    C = M.ctx(5); df = C.df; h, l, c = C.h, C.l, C.c
    dt = pd.DatetimeIndex(df.datetime); dt = dt.tz_localize('UTC') if dt.tz is None else dt
    ny = (dt + pd.Timedelta(minutes=5)).tz_convert(ss.NY); m = np.asarray(ny.hour * 60 + ny.minute)
    skip = ((m >= 720) & (m <= 785)) | ((m >= 945) & (m < 1110))
    sma = D.sma.reindex((dt.tz_convert(ss.NY) + pd.Timedelta(hours=6)).normalize()).values
    rows = []
    for j, k, px, st, _ in oc.mix_list(C):
        if C.date[j] in ss.FOMC or skip[j] or np.isnan(sma[j]): continue
        risk = abs(px - st); out = {}
        for R in (1, 2):
            tg = px + k * R * risk; r = None
            if (l[j] <= st) if k == 1 else (h[j] >= st): r = -1
            else:
                for q in range(j + 1, min(j + 61, len(c))):
                    if (l[q] <= st) if k == 1 else (h[q] >= st): r = -1; break
                    if (h[q] >= tg) if k == 1 else (l[q] <= tg): r = R; break
                    if C.halt[q]: r = (c[q] - px) * k / risk; break
                if r is None: r = (c[min(j + 60, len(c) - 1)] - px) * k / risk
            out[R] = r
        rows.append(dict(date=C.date[j], with_=(px - sma[j]) * k > 0, dist=abs(px - sma[j]) / px * 100, r1=out[1], r2=out[2], n2=out[2] - 1 / risk))
    t = pd.DataFrame(rows)
    split = oc.YEARS[3][2]
    bins = [0, 0.25, 0.5, 1.0, 2.0, 99]
    for lab, z0 in (('順日線（v3 做的）', t[t.with_]), ('逆日線（v3 不做）', t[~t.with_])):
        print(f'\n5m MIX，{lab}：離日線 SMA5 的距離（% 價格）')
        for per, z1 in (('v3 那年', z0[z0.date > split]), ('前 4 年', z0[z0.date <= split])):
            g = z1.groupby(pd.cut(z1.dist, bins), observed=True)
            print(f'   {per}：' + '  '.join(f'{iv.left:g}–{iv.right:g}%: {len(x)} 筆 1R {100 * (x.r1 == 1).mean():.0f}% 2R {100 * (x.r2 == 2).mean():.0f}% {x.n2.mean():+.2f}R'
                                           for iv, x in g))


if __name__ == '__main__':
    main()
