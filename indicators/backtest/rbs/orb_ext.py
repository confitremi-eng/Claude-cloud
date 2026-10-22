"""NQ opening-range breakout: how far it extends (1x-5x the range), and at which extension the pullback is worth fading.

  cd indicators/backtest
  python3 -I rbs/orb_ext.py [eth|rth] [data.csv]     # default eth, data/NQ_1m_databento.csv (works on NQ_1m_5y.csv)

Session
  eth  Globex: opens 18:00 ET, ends 16:59 ET the next day (Sunday evening opens Monday's session)
  rth  cash: 09:30-15:59 ET
Opening range (OR) = the first 5 or 15 minutes; H = its high - low. Breakout = the first later bar that trades beyond
the OR (a bar through both sides is skipped); the extension levels are OR edge +- k x H, k = 1..5, on the breakout side.
  1. how often each level is reached after the breakout
  2. ORB itself: stop order at the OR edge, stop at the other edge (1 H) or the middle (0.5 H), target k x H from the
     entry, flat at the session end
  3. fade at level k (反抽 / 回檔 against the breakout): limit entry at the first touch of level k, stop s x H beyond it
     (s = 0.5 / 1), target a pullback of 0.5 H or 1 H (1 H = back to level k-1); stop first when both are in one bar
     (the entry bar counts for the stop)
All 1 point cost, entries until 30 minutes before the session end. Halves of the dates (前 / 後).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss

COST = 1.0
KS = (1, 2, 3, 4, 5)


def sessions(path, mode):
    one = pd.read_csv(path, parse_dates=['datetime']).set_index('datetime').sort_index()
    ny = one.index.tz_convert(ss.NY); m = np.asarray(ny.hour * 60 + ny.minute)
    if mode == 'eth':
        # session date = the New York date the session ends on
        sd = (ny + pd.to_timedelta(np.where(m >= 1080, 1, 0), unit='D')).strftime('%Y-%m-%d')
        keep = (m >= 1080) | (m < 1020)
        start, last = 1080, 1019
    else:
        sd = ny.strftime('%Y-%m-%d'); keep = (m >= 570) & (m < 960); start, last = 570, 959
    one = one[keep].assign(sd=np.asarray(sd)[keep], m=m[keep])
    out = []
    for d, g in one.groupby('sd', sort=True):
        if g.m.values[0] != start or len(g) < (900 if mode == 'eth' else 300): continue
        out.append((d, g.open.values, g.high.values, g.low.values, g.close.values, g.m.values))
    return out, start, last


def study(S, W, last):
    rows = []
    for d, o, h, l, c, m in S:
        n = len(c)
        if n <= W + 5: continue
        top, bot = h[:W].max(), l[:W].min(); H = top - bot
        if H <= 0: continue
        cut = n - 30                                      # no new entries in the last 30 minutes
        j = None
        for q in range(W, cut):
            up, dn = h[q] >= top + 0.25, l[q] <= bot - 0.25
            if up or dn:
                if up and dn: j = -1
                else: j = q; side = 1 if up else -1
                break
        if j is None or j < 0: continue
        edge = top if side == 1 else bot; other = bot if side == 1 else top
        ext = (h[j:] - edge).max() if side == 1 else (edge - l[j:]).min() * -1
        r = dict(date=d, H=H, side=side, reach=ext / H)
        # 2. ORB itself
        px = max(o[j], edge) if side == 1 else min(o[j], edge)
        for sname, stop in (('1H', other), ('0.5H', (top + bot) / 2)):
            risk = (px - stop) * side
            for k in KS:
                tgt = px + side * k * H; res = None
                if (l[j] <= stop) if side == 1 else (h[j] >= stop): res = -1.0
                else:
                    for q in range(j + 1, n):
                        if (l[q] <= stop) if side == 1 else (h[q] >= stop): res = -1.0; break
                        if (h[q] >= tgt) if side == 1 else (l[q] <= tgt): res = k * H / risk; break
                if res is None: res = (c[-1] - px) * side / risk
                r[f'orb_{sname}_{k}'] = res - COST / risk
        # 3. fade at level k
        for k in KS:
            lev = edge + side * k * H
            e = None
            for q in range(j, cut):
                if (h[q] >= lev) if side == 1 else (l[q] <= lev): e = q; break
            if e is None: continue
            fill = o[e] if (o[e] - lev) * side > 0 else lev            # opened beyond the level: the limit fills at the open
            for s in (0.5, 1.0):
                stop = lev + side * s * H; risk = (stop - fill) * side
                if risk <= 0: continue
                for tg, dist in (('0.5H', 0.5 * H), ('1H', 1.0 * H)):
                    tgt = fill - side * dist; res = None
                    if (h[e] >= stop) if side == 1 else (l[e] <= stop): res = -1.0
                    else:
                        for q in range(e + 1, n):
                            if (h[q] >= stop) if side == 1 else (l[q] <= stop): res = -1.0; break
                            if (l[q] <= tgt) if side == 1 else (h[q] >= tgt): res = dist / risk; break
                    if res is None: res = (fill - c[-1]) * side / risk
                    r[f'fade_{k}_{s:g}_{tg}'] = res - COST / risk
        rows.append(r)
    return pd.DataFrame(rows)


def cell(x, mid, dates):
    x = x.dropna()
    if len(x) < 5: return f'{len(x):4d} 筆'
    a = x[dates[x.index] < mid]; b = x[dates[x.index] >= mid]
    return f'{len(x):4d} 筆 勝 {100 * (x > 0).mean():3.0f}% 每筆 {x.mean():+.2f}R 合計 {x.sum():+6.1f}R（前 {a.mean():+.2f} / 後 {b.mean():+.2f}）'


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'eth'
    path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'NQ_1m_databento.csv')
    S, start, last = sessions(path, mode)
    print(f'NQ {mode.upper()}（開盤 {start // 60:02d}:{start % 60:02d} 美東），{os.path.basename(path)}，{len(S)} 個交易時段；扣 {COST:g} 點')
    for W in (5, 15):
        t = study(S, W, last)
        dates = t.date; mid = sorted(dates)[len(dates) // 2]
        print(f'\n################ 開盤區間 {W} 分鐘：{len(t)} 天有突破，區間高度中位 {t.H.median():.0f} 點（{t.H.quantile(.25):.0f}–{t.H.quantile(.75):.0f}）')
        print('  1. 突破後能走到幾倍（從區間邊緣算）')
        print('     ' + '  '.join(f'{k}x {100 * (t.reach >= k).mean():3.0f}%' for k in KS) + f'   走到中位 {t.reach.median():.1f}x')
        print('     到了 k 倍之後再走到 k+1 倍：' + '  '.join(f'{k}→{k + 1} {100 * (t.reach >= k + 1).sum() / max((t.reach >= k).sum(), 1):3.0f}%' for k in KS[:-1]))
        print('  2. 順勢 ORB（區間邊緣掛突破單，目標 k 倍區間）')
        for sname in ('1H', '0.5H'):
            for k in KS:
                print(f'     停損 {"對邊" if sname == "1H" else "中線"} 目標 {k}x  {cell(t[f"orb_{sname}_{k}"], mid, dates)}')
        print('  3. 在 k 倍反向做（反抽 / 回檔），碰到就進場')
        for k in KS:
            for s in (0.5, 1.0):
                for tg in ('0.5H', '1H'):
                    col = f'fade_{k}_{s:g}_{tg}'
                    if col in t:
                        rr = (0.5 if tg == '0.5H' else 1.0) / s
                        print(f'     {k}x 停損 {s:g}H 目標回 {tg}（{rr:g}R） {cell(t[col], mid, dates)}')


if __name__ == '__main__':
    main()
