"""Charts of how v3 (NQ 2m) failed in the earlier years: writes ../v3_failure.html (Chart.js page).

  cd indicators/backtest
  python3 -I rbs/v3_failure.py

v3 frozen (rbs/oos_check.py), one position at a time, 3R, 1 point cost, five years. For every trade: kind, exit
(target / stop / time or halt), MFE = best move in its favour before the exit (in R), hour of entry (New York).
Charts: cumulative R; exit mix per year; how far trades went before being stopped; R by entry hour; trend vs MIX.
"""
import sys, os, json; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import oos_check as oc

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def trades(C, trend, mix, R=3.0):
    df = C.df; h, l, c = C.h, C.l, C.c
    holeb = np.r_[False, (df.datetime.diff() > pd.Timedelta(minutes=30)).values[1:]]
    trad = df.tradable.values; et = (df.datetime + pd.Timedelta(minutes=C.tf)).dt.tz_convert(ss.NY)
    hour = et.dt.hour.values
    tr = {int(i): int(k) for i, k in zip(trend.i, trend.side)}
    mx = {j: (k, px, st) for j, k, px, st, _ in mix}
    out = []; pos = 0
    for j in range(len(c)):
        if pos != 0 and j > vb:
            fav = (h[j] - ve) if pos == 1 else (ve - l[j]); mfe = max(mfe, fav)
            hs = (l[j] <= vs) if pos == 1 else (h[j] >= vs)
            ht = (h[j] >= vt) if pos == 1 else (l[j] <= vt)
            if hs or ht or j - vb >= 60 or C.halt[j] or holeb[j]:
                px = vs if hs else vt if ht else (c[j - 1] if holeb[j] else c[j])
                if hs: mfe = min(mfe, max(0.0, mfe))
                risk = abs(ve - vs)
                out.append(dict(date=d0, kind=kind, R=(px - ve) * pos / risk, net=(px - ve) * pos / risk - oc.COST / risk,
                                exit='停損' if hs else '目標' if ht else '時間 / 休市', mfe=mfe / risk, hour=hr, bars=j - vb))
                pos = 0
        if not trad[j] or C.halt[j] or C.late[j]: continue
        if pos == 0 and j in mx:
            k, px, st = mx[j]
            pos, ve, vs, vt, vb, kind, d0, hr, mfe = k, px, st, px + R * (px - st), j, 'MIX', C.date[j], hour[j], 0.0
            if (pos == 1 and l[j] <= vs) or (pos == -1 and h[j] >= vs):
                risk = abs(ve - vs)
                out.append(dict(date=d0, kind=kind, R=-1.0, net=-1.0 - oc.COST / risk, exit='停損', mfe=0.0, hour=hr, bars=0)); pos = 0
        if pos == 0 and j in tr:
            k = tr[j]; st = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j])
            pos, ve, vs, vt, vb, kind, d0, hr, mfe = k, c[j], st, c[j] + R * (c[j] - st), j, '趨勢', C.date[j], hour[j], 0.0
    return pd.DataFrame(out)


def period(d):
    return 'IS' if d >= '2025-10-15' else 'OOS'


def main():
    one = oc.load(); M = oc.Market(one); C = M.ctx(2)
    T = oc.trend_set(C.df, M.H, 2, 20, C.df.thr.values, 3.0, 0, 180)
    t = trades(C, T, oc.mix_list(C))
    t = t[(t.date >= '2021-10-15') & (t.date <= '2026-10-14')].reset_index(drop=True)
    t['p'] = t.date.map(period)
    yname = lambda d: next(nm[:2] for nm, a, b in oc.YEARS if a <= d <= b)
    t['y'] = t.date.map(yname)
    data = {}
    daily = t.groupby('date').net.sum().cumsum()
    data['eq'] = {'x': list(daily.index), 'y': [round(v, 1) for v in daily.values]}
    years = [nm[:2] for nm, a, b in oc.YEARS]
    ylab = {nm[:2]: nm for nm, a, b in oc.YEARS}
    data['years'] = [ylab[y] for y in years]
    data['exit'] = {e: [round(100 * (t[t.y == y].exit == e).mean(), 1) for y in years] for e in ('目標', '停損', '時間 / 休市')}
    data['win'] = [round(100 * (t[t.y == y].R > 0).mean(), 1) for y in years]
    stopped = t[t.exit == '停損']
    bins = [(0, 0.5), (0.5, 1), (1, 2), (2, 3)]
    data['mfe_bins'] = ['0–0.5R', '0.5–1R', '1–2R', '2–3R']
    data['mfe'] = {p: [round(100 * ((stopped[stopped.p == p].mfe >= a) & (stopped[stopped.p == p].mfe < b)).mean(), 1) for a, b in bins] for p in ('OOS', 'IS')}
    data['stop_bars'] = {p: round(float(stopped[stopped.p == p].bars.median()), 1) for p in ('OOS', 'IS')}
    hours = list(range(0, 24))
    data['hours'] = [f'{h:02d}' for h in hours]
    data['hourR'] = {p: [round(float(t[(t.p == p) & (t.hour == h)].net.mean()), 3) if ((t.p == p) & (t.hour == h)).sum() >= 15 else None for h in hours] for p in ('OOS', 'IS')}
    data['kind'] = {k: [round(float(t[(t.y == y) & (t.kind == k)].net.sum()), 1) for y in years] for k in ('趨勢', 'MIX')}
    data['summary'] = {p: dict(n=int((t.p == p).sum()), win=round(100 * (t[t.p == p].R > 0).mean(), 1), stop=round(100 * (t[t.p == p].exit == '停損').mean(), 1),
                               tgt=round(100 * (t[t.p == p].exit == '目標').mean(), 1), per=round(float(t[t.p == p].net.mean()), 3)) for p in ('OOS', 'IS')}
    page = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'v3_failure_template.html'), encoding='utf-8').read()
    out = os.path.join(HERE, 'v3_failure.html')
    open(out, 'w', encoding='utf-8').write(page.replace('/*DATA*/null', json.dumps(data, ensure_ascii=False)))
    print('寫好', out); print(json.dumps(data['summary'], ensure_ascii=False)); print('停損前持有根數中位數', data['stop_bars'])
    print('停損單的最大浮盈分布', data['mfe']); print('出場', data['exit']); print('勝率', data['win']); print('趨勢 / MIX', data['kind'])


if __name__ == '__main__':
    main()
