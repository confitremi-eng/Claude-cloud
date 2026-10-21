"""US cash open (09:30 New York) gap with a reversing first candle, on the 1m and 2m charts (NQ cash-session bars stand in
for QQQ, as in the other QQQ studies). Five years.

  cd indicators/backtest
  python3 -I rbs/rth_open_gap.py

Previous close = the 15:59 one-minute close of the previous session. First candle = 09:30 bar (1m) or 09:30-09:32 (2m).
Long: gap down, first candle closes up but still below the previous close ('低開高走'); short mirrored ('高開低走').
Entry at the first candle's close; stop = its low / high (1 tick beyond); targets 1R / 2R / 3R and the gap fill, until
16:00; 1 point cost. Groups by gap size (% of price). Per year at the end (gap >= 0.3%).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import oos_check as oc


def study(one, n_first):
    ix = one.index if one.index.tz is not None else one.index.tz_localize('UTC')
    ny = ix.tz_convert(ss.NY); mins = np.asarray(ny.hour * 60 + ny.minute); days = np.asarray(ny.strftime('%Y-%m-%d'))
    o, h, l, c = one.open.values, one.high.values, one.low.values, one.close.values
    closes = {}
    for j in np.where(mins == 959)[0]: closes[days[j]] = c[j]
    order = sorted(closes)
    prev = {order[i]: closes[order[i - 1]] for i in range(1, len(order))}
    rows = []
    for j in np.where(mins == 570)[0]:
        d = days[j]
        if d not in prev or j + n_first + 5 >= len(c) or mins[j + n_first - 1] != 570 + n_first - 1: continue
        pc = prev[d]; fo = o[j]; fh = h[j:j + n_first].max(); fl = l[j:j + n_first].min(); fc = c[j + n_first - 1]
        gap = fo - pc
        end = j + n_first
        while end < len(c) and days[end] == d and mins[end] < 960: end += 1
        for side in (1, -1):
            if side == 1 and not (gap < 0 and fc > fo and fc < pc): continue
            if side == -1 and not (gap > 0 and fc < fo and fc > pc): continue
            stop = fl - 0.25 if side == 1 else fh + 0.25; risk = (fc - stop) * side
            if risk <= 0: continue
            res = {}
            for R in (1, 2, 3):
                tgt = fc + side * R * risk; r = None
                for q in range(j + n_first, end):
                    if (l[q] <= stop) if side == 1 else (h[q] >= stop): r = -1; break
                    if (h[q] >= tgt) if side == 1 else (l[q] <= tgt): r = R; break
                res[R] = r if r is not None else (c[end - 1] - fc) * side / risk
            fill = None
            for q in range(j + n_first, end):
                if (l[q] <= stop) if side == 1 else (h[q] >= stop): fill = False; break
                if (h[q] >= pc) if side == 1 else (l[q] <= pc): fill = True; break
            rows.append(dict(date=d, side=side, gap_pct=100 * gap / pc, risk=risk, r1=res[1], r2=res[2], r3=res[3], fill=fill))
    t = pd.DataFrame(rows)
    for R in (1, 2, 3): t[f'n{R}'] = t[f'r{R}'] - 1 / t.risk
    t['yr'] = pd.cut(t.date, [oc.YEARS[0][1]] + [b for nm, a, b in oc.YEARS], labels=[nm[:2] for nm, a, b in oc.YEARS], include_lowest=True)
    return t


def stats(z):
    if not len(z): return '   0 筆'
    return (f'{len(z):4d} 筆  1R {100 * (z.r1 == 1).mean():3.0f}%  2R {100 * (z.r2 == 2).mean():3.0f}%  3R {100 * (z.r3 == 3).mean():3.0f}%  '
            f'回補 {100 * (z.fill == True).mean():3.0f}%  每筆 1R {z.n1.mean():+.2f} 2R {z.n2.mean():+.2f} 3R {z.n3.mean():+.2f}  停損中位 {z.risk.median():.0f} 點')


def main():
    one = oc.load()
    for n, lab in ((1, '1 分 K'), (2, '2 分 K')):
        t = study(one, n)
        for side, sl in ((1, '低開高走（做多）'), (-1, '高開低走（做空）')):
            z = t[t.side == side]
            print(f'\n{lab}：{sl}')
            print('   全部            ' + stats(z))
            for a, b, nm in ((0, 0.2, '缺口 < 0.2%'), (0.2, 0.5, '缺口 0.2–0.5%'), (0.5, 1.0, '缺口 0.5–1%'), (1.0, 99, '缺口 ≥ 1%')):
                print(f'   {nm:<15} ' + stats(z[(z.gap_pct.abs() >= a) & (z.gap_pct.abs() < b)]))
            g = z[z.gap_pct.abs() >= 0.5]
            print('   各年（缺口 ≥ 0.5%）：' + '  '.join(f'{y}: {len(x)} 筆 1R {100 * (x.r1 == 1).mean():.0f}% 2R {100 * (x.r2 == 2).mean():.0f}%' for y, x in g.groupby('yr', observed=True)))


if __name__ == '__main__':
    main()
