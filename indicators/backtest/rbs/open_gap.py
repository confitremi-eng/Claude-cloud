"""Globex open (18:00 New York) gap down with a rising first candle ('hollow red': close above its open but still below
the previous close), and the mirror (gap up, falling first candle). Is it worth a trade, and when? (NQ, five years)

  cd indicators/backtest
  python3 -I rbs/open_gap.py

Previous close = the 16:59 one-minute close (before the 17:00 halt). First candle = 18:00-18:02 (one 2m bar).
Gap = 18:00 open - previous close (points and % of price). Setup (long): gap <= -min_gap, first candle close > open and
< previous close. Entry at the first candle's close (18:02); stop = the first candle's low (minus 1 tick);
targets 1R / 2R / 3R and the gap fill (previous close), within 4 hours; 1 point cost. Groups by gap size, Sunday open or
weekday, and how much of the first candle's range it closed back up. Mirror for gap-up shorts.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import oos_check as oc


def main():
    one = oc.load()
    ix = one.index if one.index.tz is not None else one.index.tz_localize('UTC')
    ny = ix.tz_convert(ss.NY)
    o, h, l, c = one.open.values, one.high.values, one.low.values, one.close.values
    mins = np.asarray(ny.hour * 60 + ny.minute)
    pos_open = np.where(mins == 1080)[0]          # 18:00 bars
    rows = []
    for j in pos_open:
        if j < 2 or j + 242 >= len(c): continue
        k0 = j - 1
        while k0 > 0 and mins[k0] > 1020: k0 -= 1  # last bar before 17:00 halt (16:59) — skip anything after 17:00
        if mins[k0] != 1019 or (ix[j] - ix[k0]).total_seconds() > 4 * 86400: continue
        pc = c[k0]
        if not (mins[j + 1] == 1081): continue
        fo, fh, fl, fc = o[j], max(h[j], h[j + 1]), min(l[j], l[j + 1]), c[j + 1]
        gap = fo - pc
        for side in (1, -1):
            if side == 1 and not (gap < 0 and fc > fo and fc < pc): continue
            if side == -1 and not (gap > 0 and fc < fo and fc > pc): continue
            entry = fc; stop = (fl - 0.25) if side == 1 else (fh + 0.25); risk = (entry - stop) * side
            if risk <= 0: continue
            res = {}
            end = j + 2 + 240
            for R in (1, 2, 3):
                tgt = entry + side * R * risk; r = None
                for q in range(j + 2, end):
                    if (l[q] <= stop) if side == 1 else (h[q] >= stop): r = -1; break
                    if (h[q] >= tgt) if side == 1 else (l[q] <= tgt): r = R; break
                res[R] = r if r is not None else (c[end - 1] - entry) * side / risk
            fill = None
            for q in range(j + 2, end):
                if (l[q] <= stop) if side == 1 else (h[q] >= stop): fill = False; break
                if (h[q] >= pc) if side == 1 else (l[q] <= pc): fill = True; break
            mfe = (np.max(h[j + 2:end]) - entry) if side == 1 else (entry - np.min(l[j + 2:end]))
            rows.append(dict(date=ny[j].strftime('%Y-%m-%d'), dow=ny[j].strftime('%a'), side=side, gap=gap, gap_pct=100 * gap / pc,
                             recover=(fc - fl) / (fh - fl) if side == 1 and fh > fl else (fh - fc) / (fh - fl) if fh > fl else 0,
                             risk=risk, r1=res[1], r2=res[2], r3=res[3], fill=fill, mfe=mfe))
    t = pd.DataFrame(rows)
    for R in (1, 2, 3): t[f'n{R}'] = t[f'r{R}'] - 1 / t.risk
    t['sun'] = t.dow == 'Sun'
    t['yr'] = pd.cut(t.date, [oc.YEARS[0][1]] + [b for nm, a, b in oc.YEARS], labels=[nm[:2] for nm, a, b in oc.YEARS], include_lowest=True)

    def stats(z):
        if not len(z): return '      0 筆'
        return (f'{len(z):4d} 筆  1R 勝 {100 * (z.r1 == 1).mean():3.0f}%  2R 勝 {100 * (z.r2 == 2).mean():3.0f}%  3R 勝 {100 * (z.r3 == 3).mean():3.0f}%  '
                f'回補缺口 {100 * (z.fill == True).mean():3.0f}%  每筆 1R {z.n1.mean():+.2f} 2R {z.n2.mean():+.2f} 3R {z.n3.mean():+.2f}  停損中位 {z.risk.median():.0f} 點')
    for side, lab in ((1, '低開、第一根收紅回升（做多）'), (-1, '高開、第一根收黑回落（做空）')):
        z = t[t.side == side]
        print(f'\n{lab}，五年')
        print('   全部            ' + stats(z))
        for a, b, nm in ((0, 0.1, '缺口 < 0.1%'), (0.1, 0.3, '缺口 0.1–0.3%'), (0.3, 0.6, '缺口 0.3–0.6%'), (0.6, 99, '缺口 ≥ 0.6%')):
            print(f'   {nm:<15} ' + stats(z[(z.gap_pct.abs() >= a) & (z.gap_pct.abs() < b)]))
        print('   週日開盤        ' + stats(z[z.sun]))
        print('   平日開盤        ' + stats(z[~z.sun]))
        for a, b, nm in ((0, 0.5, '收回 < 一半'), (0.5, 0.8, '收回 50–80%'), (0.8, 1.01, '收回 ≥ 80%')):
            print(f'   第一根{nm:<10} ' + stats(z[(z.recover >= a) & (z.recover < b)]))
        print('   各年（缺口 ≥ 0.3%）：' + '  '.join(f'{y}: {len(g)} 筆 1R {100 * (g.r1 == 1).mean():.0f}% 回補 {100 * (g.fill == True).mean():.0f}%'
                                               for y, g in z[z.gap_pct.abs() >= 0.3].groupby('yr', observed=True)))
    big = t[(t.side == 1) & (t.gap_pct <= -0.3)].sort_values('date').tail(8)
    print('\n最近的大低開（≥ 0.3%）：'); print(big[['date', 'dow', 'gap', 'gap_pct', 'recover', 'risk', 'r1', 'r3', 'fill', 'mfe']].round(2).to_string(index=False))


if __name__ == '__main__':
    main()
