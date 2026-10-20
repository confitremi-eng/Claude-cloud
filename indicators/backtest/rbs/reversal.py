"""When v3 trend signals fail in a row against a rally, is it the start of a big reversal?

  cd indicators/backtest
  python3 -I rbs/reversal.py [filter]      # filter: v3 one at a time with the filter, as the indicator does it

Prompted by 2026-10-20: two NQ 2m trend sells in a row while price had already climbed back over both EMA1130
lines; the first was stopped, the second went nowhere. Everything below is known at the signal bar:
  慢線另一邊   close on the wrong side of the 15 s EMA1130 (sell above / buy below it)
  差值縮小     Trend Judge spread on the trade's side smaller than 20 minutes ago (the trend fading)
  前一筆停損   the previous v3 trend signal on the same side, within 60 minutes, already hit its stop
After the signal: share where Trend Judge turns the other way (UP for a sell) within 60 / 120 minutes, the move
over the next 60 minutes on the trade's side in ATR, and the signal's own 1R / 3R result.
v3 frozen trend signals on NQ 2m (rbs/oos_check.py), the v3 year and the five years.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import market_matrix as mm
import oos_check as oc

PERIODS = (('v3 那一年 25/10–26/10', '2025-10-15', '2026-10-18'), ('五年 21/10–26/10', '2021-10-15', '2026-10-18'))


def main(tf=2):
    one = oc.load(); M = oc.Market(one); C = M.ctx(tf); df = C.df
    s = oc.trend_set(df, M.H, tf, 20, df.thr.values, 3.0, 0, 180).copy()
    _, atr = mm.ss.bar_context(df, tf)
    c = df.close.values; d = df.tj_diff.values; tdir = np.sign(df.tj_dir.values); n = len(c)
    i = s.i.values; k = s.side.values
    s['slow_side'] = (c[i] - df.emaS.values[i]) * k / atr[i]
    lag = max(1, round(20 / tf))
    s['dspr'] = (d[i] - d[np.maximum(i - lag, 0)]) * k
    # previous same-side signal within 60 minutes that was already stopped (3R table: r3 == -1 and exit before i)
    prev_fail = np.zeros(len(s), bool)
    ii, kk, xx, rr = s.i.values, s.side.values, s.x3.values, s.r3.values
    for q in range(len(s)):
        for p in range(q - 1, -1, -1):
            if ii[q] - ii[p] > round(60 / tf): break
            if kk[p] == kk[q]:
                prev_fail[q] = rr[p] <= -0.99 and xx[p] <= ii[q]
                break
    s['prev_fail'] = prev_fail
    for m in (60, 120):
        w = round(m / tf)
        s[f'flip{m}'] = [bool((tdir[j + 1:min(j + 1 + w, n)] == -kk_).any()) for j, kk_ in zip(i, k)]
    w60 = round(60 / tf)
    s['fwd'] = (c[np.minimum(i + w60, n - 1)] - c[i]) * k / atr[i]
    print(f'NQ {tf} 分 K，v3 的趨勢訊號（凍結規則）。轉向 = Trend Judge 之後轉成反方向的趨勢；60 分走勢 = 60 分鐘後收盤順著交易方向幾 ATR')
    for nm, a, b in PERIODS:
        z = s[(s.date >= a) & (s.date <= b)]
        print(f'\n## {nm}')
        print(f'   {"":<30} {"筆數":>5} {"60分內轉向":>9} {"120分內轉向":>10} {"60分走勢":>8} {"1R勝率":>7} {"3R每筆":>7}')
        rows = [('全部', z.side != 0), ('慢線另一邊', z.slow_side < 0), ('差值縮小', z.dspr < 0), ('前一筆停損', z.prev_fail),
                ('慢線另一邊 + 差值縮小', (z.slow_side < 0) & (z.dspr < 0)), ('前一筆停損 + 慢線另一邊', z.prev_fail & (z.slow_side < 0)),
                ('前一筆停損 + 差值縮小', z.prev_fail & (z.dspr < 0)), ('三個都有（像 10/20）', z.prev_fail & (z.slow_side < 0) & (z.dspr < 0))]
        for lab, m in rows:
            y = z[m]
            if len(y) == 0:
                print(f'   {lab:<30} {0:5d}'); continue
            print(f'   {lab:<30} {len(y):5d} {100 * y.flip60.mean():8.1f}% {100 * y.flip120.mean():9.1f}% {y.fwd.mean():+8.2f} {100 * (y.r1 > 0).mean():6.1f}% {(y.r3 - 1.0 / y.risk).mean():+7.2f}')


def sim_filter(C, trend, mix, R, slow_ok, mins=60, on=True):
    """oos_check.sim plus the filter: skip a trend entry when the last v3 trade on the same side was stopped out within
    `mins` minutes and the close is on the wrong side of the 15 s EMA1130 (slow_ok[bar] is False)."""
    import oos_check as oc
    df = C.df; h, l, c = C.h, C.l, C.c
    holeb = np.r_[False, (df.datetime.diff() > pd.Timedelta(minutes=30)).values[1:]]
    trad = df.tradable.values
    tr = {int(i): int(k) for i, k in zip(trend.i, trend.side)}
    mx = {j: (k, px, st) for j, k, px, st, _ in mix}
    trades = []; pos = 0; last_side = 0; last_stop_bar = -10 ** 9; skipped = 0
    w = round(mins / C.tf)
    for j in range(len(c)):
        if pos != 0 and j > vb:
            hs = (l[j] <= vs) if pos == 1 else (h[j] >= vs)
            ht = (h[j] >= vt) if pos == 1 else (l[j] <= vt)
            if hs or ht or j - vb >= 60 or C.halt[j] or holeb[j]:
                px = vs if hs else vt if ht else (c[j - 1] if holeb[j] else c[j])
                trades.append((kind, pos, ve, px, abs(ve - vs), d0))
                last_side = pos; last_stop_bar = j if hs else -10 ** 9; pos = 0
        if not trad[j] or C.halt[j] or C.late[j]: continue
        if pos == 0 and j in mx:
            k, px, st = mx[j]
            pos, ve, vs, vt, vb, kind, d0 = k, px, st, px + R * (px - st), j, 'MIX', C.date[j]
            if (pos == 1 and l[j] <= vs) or (pos == -1 and h[j] >= vs):
                trades.append((kind, pos, ve, vs, abs(ve - vs), d0)); last_side = pos; last_stop_bar = j; pos = 0
        if pos == 0 and j in tr:
            k = tr[j]
            if on and last_side == k and j - last_stop_bar <= w and not slow_ok[j, 0 if k == 1 else 1]:
                skipped += 1; continue
            st = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j])
            pos, ve, vs, vt, vb, kind, d0 = k, c[j], st, c[j] + R * (c[j] - st), j, '趨勢', C.date[j]
    t = pd.DataFrame(trades, columns=['kind', 'side', 'entry', 'exit', 'risk', 'date'])
    t['R'] = (t.exit - t.entry) * t.side / t.risk
    t['net'] = t.R - oc.COST / t.risk
    return t, skipped


def filter_test():
    for tf, R in ((2, 3.0), (5, 2.0)):
        one = oc.load(); M = oc.Market(one); C = M.ctx(tf); df = C.df
        s = oc.trend_set(df, M.H, tf, 20, df.thr.values, 3.0, 0, 180)
        mix = oc.mix_list(C)
        emaS = df.emaS.values; c = df.close.values
        slow_ok = np.c_[c > emaS, c < emaS]          # buy ok if above the slow line, sell ok if below
        print(f'\nNQ {tf} 分 K，v3（趨勢 + MIX，一次一筆，{R:g}R）：前一筆同方向 60 分內停損、而且價格在慢線另一邊 → 這筆趨勢訊號不做')
        for lab, on in (('v3 現在', False), ('加過濾', True)):
            t, sk = sim_filter(C, s, mix, R, slow_ok, on=on)
            parts = []
            for nm, a, b in (('v3 那一年', '2025-10-15', '2026-10-18'), ('2025/01–10', '2025-01-01', '2025-10-14'), ('樣本外 4 年', '2021-10-15', '2025-10-14')):
                r = oc.year_stats(t[(t.date >= a) & (t.date <= b)])
                parts.append(f'{nm} {r["tot"]:+6.1f}R / 回撤 {r["dd"]:5.1f}（{r["n"]} 筆）')
            print(f'   {lab:<8} ' + '   '.join(parts) + (f'   五年擋掉 {sk} 筆' if on else ''))


if __name__ == '__main__':
    filter_test() if 'filter' in sys.argv else main()
