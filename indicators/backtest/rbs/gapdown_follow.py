"""QQQ (NQ cash-session bars) gap-down days: at what gap size does the day tend to keep falling?

  cd indicators/backtest
  python3 -I rbs/gapdown_follow.py [data/NQ_1m_5y.csv]

Gap = 09:30 open vs the previous 15:59 close. Per gap band: days, share closing below the open (kept falling), median
open-to-close %, share closing below the opening 30-minute low, share filling the gap, and where the day's low comes
(before 10:00 / after 12:00). Also per year for the bands that stand out.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import oos_check as oc
import gapdown_long as gl

HERE = os.path.dirname(os.path.abspath(__file__))
BANDS = ((0.0, -0.3, '平開 / 高開（對照）'), (-0.3, -0.5, '−0.3 ~ −0.5%'), (-0.5, -0.75, '−0.5 ~ −0.75%'), (-0.75, -1.0, '−0.75 ~ −1%'),
         (-1.0, -1.5, '−1 ~ −1.5%'), (-1.5, -2.0, '−1.5 ~ −2%'), (-2.0, -99, '≤ −2%'))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'data', 'NQ_1m_5y.csv')
    one = gl.load(path); rows = []; prev = None
    for d, g in one.groupby('day', sort=True):
        o, h, l, c, m = g.open.values, g.high.values, g.low.values, g.close.values, g['min'].values
        if prev is not None:
            op = o[0]; cl = c[-1]; f30 = m < 600
            rows.append(dict(date=d, gap=100 * (op / prev - 1), oc=100 * (cl / op - 1), down=cl < op, below30=cl < l[f30].min(),
                             fill=h.max() >= prev, low_t=m[int(np.argmin(l))], close_vs_prev=100 * (cl / prev - 1)))
        prev = c[-1]
    t = pd.DataFrame(rows)
    print(f'{os.path.basename(path)}：{len(t)} 天（{t.date.min()} .. {t.date.max()}），NQ 美股盤代替 QQQ')
    print(f'   {"跳空":<18}{"天數":>5}{"收在開盤下":>10}{"開→收中位":>10}{"收破前30分低":>12}{"回補昨收":>9}{"低點在10點前":>12}{"低點在12點後":>12}')
    for a, b, lab in BANDS:
        z = t[t.gap > -0.3] if a == 0.0 else t[(t.gap <= a) & (t.gap > b)]
        print(f'   {lab:<18}{len(z):5d}{100 * z.down.mean():9.0f}%{z.oc.median():+9.2f}%{100 * z.below30.mean():11.0f}%{100 * z.fill.mean():8.0f}%'
              f'{100 * (z.low_t < 600).mean():11.0f}%{100 * (z.low_t >= 720).mean():11.0f}%')
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    print('\n各年：收在開盤下的比例（天數）')
    print(f'   {"跳空":<18}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>14}' for nm, a, b in yrs))
    for a, b, lab in BANDS:
        z = t[t.gap > -0.3] if a == 0.0 else t[(t.gap <= a) & (t.gap > b)]
        print(f'   {lab:<18}' + ''.join(f'{100 * q.down.mean() if len(q) else 0:8.0f}% ({len(q):2d})' for q in (z[(z.date >= p) & (z.date <= e)] for _, p, e in yrs)))


if __name__ == '__main__':
    main()
