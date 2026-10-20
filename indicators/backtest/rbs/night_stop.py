"""Stop the night session after N losses in a row, keep trading the cash session (v3, NQ 2m / 5m, five years).

  cd indicators/backtest
  python3 -I rbs/night_stop.py

Night = entries outside 09:30-16:00 New York on weekdays. Within one trading session (18:00 to 17:00 New York), once N
night trades in a row have lost, no more night entries until the next session; cash-session entries carry on (they
do not count toward or reset the streak). v3 frozen otherwise (FOMC days off as now), one at a time, 1 point cost.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import oos_check as oc


def sim(C, trend, mix, R, n_stop):
    df = C.df; h, l, c = C.h, C.l, C.c
    holeb = np.r_[False, (df.datetime.diff() > pd.Timedelta(minutes=30)).values[1:]]
    trad = df.tradable.values
    em = (df.datetime + pd.Timedelta(minutes=C.tf)).dt.tz_convert(ss.NY)
    emin = (em.dt.hour * 60 + em.dt.minute).values; wd = em.dt.weekday.values
    cash = (emin > 570) & (emin <= 960) & (wd < 5)
    sess = (em + pd.Timedelta(hours=6)).dt.date.values
    tr = {int(i): int(k) for i, k in zip(trend.i, trend.side)}
    mx = {j: (k, px, st) for j, k, px, st, _ in mix}
    out = []; pos = 0; cur = None; streak = 0; blocked = False; nblock = 0
    for j in range(len(c)):
        if sess[j] != cur: cur = sess[j]; streak = 0; blocked = False
        if pos != 0 and j > vb:
            hs = (l[j] <= vs) if pos == 1 else (h[j] >= vs)
            ht = (h[j] >= vt) if pos == 1 else (l[j] <= vt)
            if hs or ht or j - vb >= 60 or C.halt[j] or holeb[j]:
                px = vs if hs else vt if ht else (c[j - 1] if holeb[j] else c[j])
                risk = abs(ve - vs); net = (px - ve) * pos / risk - oc.COST / risk
                out.append((d0, net, (px - ve) * pos / risk, night))
                if night and sess_in == cur:
                    streak = streak + 1 if net < 0 else 0
                    if n_stop and streak >= n_stop: blocked = True
                pos = 0
        if not trad[j] or C.halt[j] or C.late[j]: continue
        nt = not cash[j]
        if nt and blocked:
            if j in mx or j in tr: nblock += 1
            continue
        if pos == 0 and j in mx:
            k, px, st = mx[j]
            pos, ve, vs, vt, vb, d0, night, sess_in = k, px, st, px + R * (px - st), j, C.date[j], nt, cur
            if (pos == 1 and l[j] <= vs) or (pos == -1 and h[j] >= vs):
                risk = abs(ve - vs); out.append((d0, -1.0 - oc.COST / risk, -1.0, nt))
                if nt:
                    streak += 1
                    if n_stop and streak >= n_stop: blocked = True
                pos = 0
        if pos == 0 and j in tr:
            k = tr[j]; st = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j])
            pos, ve, vs, vt, vb, d0, night, sess_in = k, c[j], st, c[j] + R * (c[j] - st), j, C.date[j], nt, cur
    return pd.DataFrame(out, columns=['date', 'net', 'R', 'night']), nblock


def main():
    one = oc.load(); M = oc.Market(one)
    for tf, R in ((2, 3.0), (5, 2.0)):
        C = M.ctx(tf)
        T = oc.trend_set(C.df, M.H, tf, 20, C.df.thr.values, 3.0, 0, 180)
        T = T[~T.date.isin(ss.FOMC)]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC]
        print(f'\nNQ {tf}m（v3 含 FOMC 整天不做；每年 R：Y1 Y2 Y3 Y4 IS）')
        for n in (0, 1, 2, 3, 4):
            t, nb = sim(C, T, mix, R, n)
            oc.one_line('v3 現在' if n == 0 else f'夜盤連錯 {n} 次就停', t)
            if n:
                print(f'      五年擋掉 {nb} 個夜盤訊號；夜盤 R 每年：' + '  '.join(f'{t[(t.date >= a) & (t.date <= b) & t.night].net.sum():+.0f}' for nm, a, b in oc.YEARS))


if __name__ == '__main__':
    main()
