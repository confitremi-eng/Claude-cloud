"""Trend Judge MIX periods on NQ 2 minutes (the Databento year): are they ranges, and can the edges be traded?

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/mix_range.py

MIX = Trend Judge spread within +-10 (一般 threshold 10) on the 2-minute chart, estimated from 1-minute closes.
A MIX period is a run of MIX bars; trend blips of up to 2 bars (4 minutes) inside it are ignored, and a data
hole longer than 30 minutes ends it.
Prints
  1. MIX periods: how many, how long, how much of the MIX time sits in periods of an hour or more
  2. periods of an hour or more: range in ATR and efficiency ratio against trend hours, and whether the box of
     the first 30 / 60 minutes holds for the rest of the period
  3. trading the box edges. Box = high / low of the first W minutes of a MIX period. Sell limit in the top
     zone (10% of the box height below the top), buy limit in the bottom zone, stop 20% of the height beyond
     the box, target the middle or the far zone; stop first when both are hit in one bar, 2-hour time exit,
     1 point cost. A box ends after a stop-out, when Trend Judge leaves MIX, or after a maximum age.
     By W, by box age at entry, by box height, by session; robustness of zone / stop sizes
  4. other box definitions: wait until the first touch held; boxes found from price alone (last N bars within
     k ATR); and the opposite trade, the first breakout of the MIX box
  5. the MIX-box breakout: box time W, breakout distance, stop, how soon after the box forms, by side / session /
     box height / minutes after forming / whether Trend Judge has already left MIX
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss

TH = 10.0
TF = 2
GRACE = 2
COST = 1.0
HOLD = 60


def load():
    df = rbs.prepared('NQ', TF)
    h, l, c, o = df.high.values, df.low.values, df.close.values, df.open.values
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values
    d = df.tj_diff.values
    state = np.where(np.isnan(d), 9, np.where(d > TH, 1, np.where(d < -TH, -1, 0)))
    t = df.datetime
    hole = np.r_[True, (t.diff() > pd.Timedelta(minutes=30)).values[1:]]
    ee = (t + pd.Timedelta(minutes=TF)).dt.tz_convert(ss.NY)
    me = (ee.dt.hour * 60 + ee.dt.minute).values; wd = ee.dt.weekday.values
    fomc = np.isin(ee.dt.date.astype(str).values, list(ss.FOMC))
    evt = (((wd < 5) & (((me >= 508) & (me < 540)) | ((me >= 598) & (me < 615)))) | (fomc & (me >= 838) & (me < 900))
           | ((me >= 570) & (me < 600)) | ((me >= 945) & (me < 975)) | ((me >= 1005) & (me < 1020)) | ((me >= 1080) & (me < 1110)))
    sess = np.select([(me >= 1200) | (me < 180), me < 570, me < 960], ['亞洲 20-03', '歐洲 03-09:30', '美股 09:30-16'], '收盤後 16-20')
    date = (t.dt.tz_convert(ss.NY)).dt.date.astype(str).values
    return dict(df=df, h=h, l=l, c=c, o=o, atr=atr, state=state, hole=hole, evt=evt, sess=sess, date=date,
                tradable=df.tradable.values)


def mix_periods(B):
    state, hole, trad = B['state'], B['hole'], B['tradable']
    n = len(state); eps = []; j = 0
    while j < n:
        if state[j] == 0 and trad[j]:
            s0 = e = j; k = j + 1; gap = 0
            while k < n and not hole[k]:
                if state[k] == 0: e = k; gap = 0
                elif state[k] in (1, -1):
                    gap += 1
                    if gap > GRACE: break
                else: break
                k += 1
            eps.append((s0, e)); j = e + 1
        else:
            j += 1
    return eps


def part1(B, eps):
    print('\n######## 1. MIX 持續多久')
    dur = np.array([(e - s + 1) * TF for s, e in eps])
    trad = B['tradable'] & (B['state'] != 9)
    print(f'  一年 {len(eps)} 段 MIX，佔全部時間 {100 * (B["state"][trad] == 0).mean():.0f}%；中位數 {np.median(dur):.0f} 分鐘')
    for lo, hi in ((0, 10), (10, 30), (30, 60), (60, 120), (120, 240), (240, 10 ** 6)):
        m = (dur >= lo) & (dur < hi)
        nm = f'{lo}–{hi} 分' if hi < 10 ** 6 else f'{lo} 分以上'
        print(f'    {nm:<12} {m.sum():4d} 段（{100 * m.mean():4.1f}%），佔 MIX 時間 {100 * dur[m].sum() / dur.sum():4.1f}%')


def er(c, a, b):
    seg = c[a:b + 1]
    return abs(seg[-1] - seg[0]) / np.abs(np.diff(seg)).sum() if len(seg) > 2 else np.nan


def part2(B, eps):
    print('\n######## 2. 持續 1 小時以上的 MIX：是不是區間')
    h, l, c, atr, state, hole = B['h'], B['l'], B['c'], B['atr'], B['state'], B['hole']
    long_eps = [(s, e) for s, e in eps if (e - s + 1) * TF >= 60]
    mix_er = [er(c, s, s + 29) for s, e in long_eps]
    mix_rng = [(h[s:s + 30].max() - l[s:s + 30].min()) / atr[s] for s, e in long_eps]
    tr_er, tr_rng = [], []
    n = len(c); j = 0
    while j + 30 < n:                                 # non-overlapping trend hours for comparison
        w = state[j:j + 30]
        if np.all(np.abs(w) == 1) and np.all(w == w[0]) and not hole[j + 1:j + 30].any():
            tr_er.append(er(c, j, j + 29)); tr_rng.append((h[j:j + 30].max() - l[j:j + 30].min()) / atr[j]); j += 30
        else:
            j += 1
    print(f'  {len(long_eps)} 段。第一個小時：ER 中位數 {np.nanmedian(mix_er):.2f}（趨勢中的一小時 {np.nanmedian(tr_er):.2f}），'
          f'高低差 {np.median(mix_rng):.1f} ATR（趨勢中 {np.median(tr_rng):.1f} ATR）')
    full = [(h[s:e + 1].max() - l[s:e + 1].min()) / atr[s] for s, e in long_eps]
    pts = [h[s:e + 1].max() - l[s:e + 1].min() for s, e in long_eps]
    print(f'  整段 MIX 的高低差：中位數 {np.median(full):.1f} ATR（{np.median(pts):.0f} 點），四分位 {np.quantile(full, .25):.1f}–{np.quantile(full, .75):.1f} ATR')
    for W in (15, 30):
        rows = []
        for s, e in long_eps:
            if e - s + 1 < W + 15: continue
            top, bot = h[s:s + W].max(), l[s:s + W].min(); H = top - bot
            rest = slice(s + W, e + 1); cr = c[rest]
            inside = ((cr <= top) & (cr >= bot)).mean()
            out = (cr > top + 0.25 * H) | (cr < bot - 0.25 * H)
            first_out = (np.argmax(out) if out.any() else len(cr)) * TF
            ext = max(h[rest].max() - top, bot - l[rest].min(), 0) / H
            rows.append((inside, out.any(), first_out, ext, len(cr) * TF))
        r = pd.DataFrame(rows, columns=['inside', 'broke', 'first_out', 'ext', 'rest'])
        print(f'  前 {W * TF} 分鐘的區間（{len(r)} 段，之後還剩至少 30 分鐘 MIX）：之後收盤留在區間內的時間 中位數 {100 * r.inside.median():.0f}%；'
              f'收盤超出區間 25% 以上的有 {100 * r.broke.mean():.0f}%（第一次超出 中位數 {r.first_out[r.broke].median():.0f} 分鐘後）；'
              f'整段都沒超出的 {100 * (~r.broke).mean():.0f}%（這些段剩下的 MIX 中位數 {r.rest[~r.broke].median():.0f} 分鐘）')


def box_trades(B, eps, W, zone=0.1, stop_k=0.2, target='mid', max_age=None, end_on_trend=True, avoid_evt=True,
               min_h=0.0, max_h=np.inf):
    h, l, c, o, atr, state, hole, evt = B['h'], B['l'], B['c'], B['o'], B['atr'], B['state'], B['hole'], B['evt']
    n = len(c); out = []
    for s, e in eps:
        if e - s + 1 <= W: continue
        f = s + W - 1
        top, bot = h[s:f + 1].max(), l[s:f + 1].min(); H = top - bot
        if H <= 0: continue
        hh = H / atr[f]
        if not (min_h <= hh < max_h): continue
        sl, bl = top - zone * H, bot + zone * H                  # sell / buy limits
        ss_, bs = top + stop_k * H, bot - stop_k * H              # stops
        mid = (top + bot) / 2
        tg_s, tg_b = (mid, mid) if target == 'mid' else (bl, sl)
        end = e if end_on_trend else n - 1
        if max_age is not None: end = min(end, f + max_age)
        j = f + 1
        while j <= end and j < n:
            if hole[j]: break
            if (avoid_evt and evt[j]) or (h[j] >= sl and l[j] <= bl):
                j += 1; continue
            side = -1 if h[j] >= sl else (1 if l[j] <= bl else 0)
            if side == 0:
                j += 1; continue
            if side == -1:
                if o[j] >= ss_: break                             # gapped through the stop: box is gone
                px = max(o[j], sl); stop, tgt = ss_, tg_s
            else:
                if o[j] <= bs: break
                px = min(o[j], bl); stop, tgt = bs, tg_b
            risk = (stop - px) * -side
            if risk <= 0: break
            res, ex = None, j
            if (h[j] >= stop) if side == -1 else (l[j] <= stop):
                res = -1.0
            else:
                last = min(j + HOLD, n - 1)
                for k in range(j + 1, last + 1):
                    if hole[k]: res = (c[k - 1] - px) * side / risk; ex = k - 1; break
                    if (h[k] >= stop) if side == -1 else (l[k] <= stop): res = -1.0; ex = k; break
                    if (l[k] <= tgt) if side == -1 else (h[k] >= tgt): res = (tgt - px) * side / risk; ex = k; break
                if res is None: res = (c[last] - px) * side / risk; ex = last
            out.append(dict(i=j, side=side, risk=risk, R=res, net=res - COST / risk, age=(j - f) * TF, hh=hh,
                            win=res - COST / risk > 0, date=B['date'][j], month=B['date'][j][:7], sess=B['sess'][j],
                            tgtR=abs(tgt - px) / risk))
            if res <= -1.0 + 1e-9: break                          # the edge failed: done with this box
            j = ex + 1
    return pd.DataFrame(out)


def summ(t):
    if len(t) == 0: return '   0 筆'
    t = t.sort_values('i'); net = t.net.values; a = t.date.values < ss.SPLIT
    eq = np.cumsum(net); dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
    mo = pd.Series(net).groupby(t.month.values).sum()
    return (f'{len(t):4d} 筆  勝率 {100 * t.win.mean():4.1f}%  目標約 {t.tgtR.median():.2f}R  每筆 {net.mean():+.3f}R（前 {net[a].mean():+.3f} 後 {net[~a].mean():+.3f}）'
            f'  一年 {net.sum():+6.1f}R  回撤 {dd:5.1f}R  賺錢月 {(mo > 0).sum()}/{len(mo)}')


def part3(B, eps):
    print('\n######## 3. 做區間上下緣（賣在上緣 10% 內、買在下緣 10% 內，停損在區間外 20%，避開事件時段）')
    print('  A. 區間要觀察多久才成形（W），目標：中線 / 對邊')
    for W in (10, 15, 23, 30, 45):
        nbox = sum(1 for s, e in eps if e - s + 1 > W)
        for tg in ('mid', 'far'):
            t = box_trades(B, eps, W, target=tg)
            print(f'    W = {W * TF:3d} 分（{nbox:4d} 個區間） {"中線" if tg == "mid" else "對邊"}：{summ(t)}')
    print('\n  B. 區間已經存在多久時進場（W = 30 / 60 分，目標中線）')
    for W in (15, 30):
        t = box_trades(B, eps, W, target='mid')
        for lab, y in t.groupby(pd.cut(t.age, [0, 30, 60, 120, 240, 10 ** 6], right=False), observed=True):
            print(f'    W = {W * TF} 分  區間存在 {str(lab):<14} {summ(y)}')
    print('\n  C. 區間寬度（W = 30 / 60 分，目標中線）')
    for W in (15, 30):
        t = box_trades(B, eps, W, target='mid')
        for lab, y in t.groupby(pd.cut(t.hh, [0, 3, 5, 8, 12, 1000], right=False), observed=True):
            print(f'    W = {W * TF} 分  寬度 {str(lab):<12} ATR {summ(y)}')
    print('\n  D. 時段（W = 30 / 60 分，目標中線）')
    for W in (15, 30):
        t = box_trades(B, eps, W, target='mid')
        for lab, y in t.groupby('sess'):
            print(f'    W = {W * TF} 分  {lab:<14} {summ(y)}')
    print('\n  E. 換參數看穩不穩（W = 30 / 60 分，目標中線）')
    for W in (15, 30):
        for nm, kw in (('基準', {}), ('進場區 5%', dict(zone=0.05)), ('進場區 20%', dict(zone=0.2)),
                       ('停損 10%', dict(stop_k=0.1)), ('停損 30%', dict(stop_k=0.3)), ('不避開事件時段', dict(avoid_evt=False)),
                       ('TJ 離開 MIX 後區間照用', dict(end_on_trend=False, max_age=120)), ('區間最多用 1 小時', dict(max_age=30)),
                       ('區間最多用 2 小時', dict(max_age=60))):
            print(f'    W = {W * TF} 分  {nm:<20} {summ(box_trades(B, eps, W, target="mid", **kw))}')


def edge_trades(B, boxes, zone=0.1, stop_k=0.2, skip_first=False):
    """Fade the edges of given boxes: list of (formed_bar, last_valid_bar, top, bot). Same rules as box_trades."""
    h, l, c, o, atr, hole, evt = B['h'], B['l'], B['c'], B['o'], B['atr'], B['hole'], B['evt']
    n = len(c); out = []
    for f, end, top, bot in boxes:
        H = top - bot
        if H <= 0: continue
        sl, bl, ss_, bs, mid = top - zone * H, bot + zone * H, top + stop_k * H, bot - stop_k * H, (top + bot) / 2
        j = f + 1; seen = 0
        while j <= min(end, n - 1):
            if hole[j]: break
            if evt[j] or (h[j] >= sl and l[j] <= bl): j += 1; continue
            side = -1 if h[j] >= sl else (1 if l[j] <= bl else 0)
            if side == 0: j += 1; continue
            if (side == -1 and o[j] >= ss_) or (side == 1 and o[j] <= bs): break
            px = max(o[j], sl) if side == -1 else min(o[j], bl); stop = ss_ if side == -1 else bs
            risk = (stop - px) * -side; res, ex = None, j
            if (h[j] >= stop) if side == -1 else (l[j] <= stop): res = -1.0
            else:
                last = min(j + HOLD, n - 1)
                for k in range(j + 1, last + 1):
                    if hole[k]: res = (c[k - 1] - px) * side / risk; ex = k - 1; break
                    if (h[k] >= stop) if side == -1 else (l[k] <= stop): res = -1.0; ex = k; break
                    if (l[k] <= mid) if side == -1 else (h[k] >= mid): res = (mid - px) * side / risk; ex = k; break
                if res is None: res = (c[last] - px) * side / risk; ex = last
            if not (skip_first and seen == 0):
                out.append(dict(i=j, side=side, risk=risk, R=res, net=res - COST / risk, win=res - COST / risk > 0, age=(j - f) * TF,
                                hh=H / atr[f], date=B['date'][j], month=B['date'][j][:7], sess=B['sess'][j], tgtR=abs(mid - px) / risk))
            seen += 1
            if res <= -1.0 + 1e-9: break
            j = ex + 1
    return pd.DataFrame(out)


def price_boxes(B, N, k, need_mix):
    """Boxes found from price alone: the last N bars stayed within k ATR (optionally all of them MIX)."""
    h, l, atr, state, hole = B['h'], B['l'], B['atr'], B['state'], B['hole']
    hh = pd.Series(h).rolling(N).max().values; ll = pd.Series(l).rolling(N).min().values
    holes = pd.Series(hole.astype(float)).rolling(N).sum().values
    mixn = pd.Series((state == 0).astype(float)).rolling(N).sum().values
    boxes = []; j = N; n = len(h)
    while j < n:
        if holes[j] == 0 and hh[j] - ll[j] <= k * atr[j] and B['tradable'][j] and (not need_mix or mixn[j] == N):
            boxes.append((j, j + 60, hh[j], ll[j])); j += 60           # use the box for up to 2 hours, then look again
        else:
            j += 1
    return boxes


def breakout_trades(B, eps, W, R, stop_at='mid', max_age=60, buf=0.1):
    """First break of the W-minute MIX box: buy above top + buf, sell below bottom - buf (share of the height);
    stop at the middle (or the far edge); within max_age bars after the box is formed."""
    h, l, c, o, hole, evt = B['h'], B['l'], B['c'], B['o'], B['hole'], B['evt']
    n = len(c); out = []
    for s, e in eps:
        if e - s + 1 <= W: continue
        f = s + W - 1; top, bot = h[s:f + 1].max(), l[s:f + 1].min(); H = top - bot
        if H <= 0: continue
        bu, bd = top + buf * H, bot - buf * H; mid = (top + bot) / 2
        for j in range(f + 1, min(f + max_age, n - 1) + 1):
            if hole[j]: break
            up, dn = h[j] >= bu, l[j] <= bd
            if not (up or dn): continue
            if (up and dn) or evt[j]: break
            side = 1 if up else -1
            px = max(o[j], bu) if side == 1 else min(o[j], bd)
            stop = mid if stop_at == 'mid' else (bot if side == 1 else top)
            risk = (px - stop) * side
            if risk <= 0: break
            tgt = px + side * R * risk; res = None; last = min(j + HOLD, n - 1)
            if (l[j] <= stop) if side == 1 else (h[j] >= stop): res = -1.0
            else:
                for k in range(j + 1, last + 1):
                    if hole[k]: res = (c[k - 1] - px) * side / risk; break
                    if (l[k] <= stop) if side == 1 else (h[k] >= stop): res = -1.0; break
                    if (h[k] >= tgt) if side == 1 else (l[k] <= tgt): res = R; break
                if res is None: res = (c[last] - px) * side / risk
            out.append(dict(i=j, side=side, risk=risk, R=res, net=res - COST / risk, win=res - COST / risk > 0, age=(j - f) * TF,
                            hh=H / B['atr'][f], date=B['date'][j], month=B['date'][j][:7], sess=B['sess'][j], tgtR=R,
                            mix_left=(e - j) * TF))
            break
    return pd.DataFrame(out)


def part4(B, eps):
    print('\n######## 4. 其他定義')
    print('  A. 等區間被驗證：第一次碰邊緣不做（只看它有沒有守住），守住才做之後的碰觸')
    for W in (15, 30, 45):
        boxes = [(s + W - 1, e, B['h'][s:s + W].max(), B['l'][s:s + W].min()) for s, e in eps if e - s + 1 > W]
        print(f'    W = {W * TF:3d} 分 {summ(edge_trades(B, boxes, skip_first=True))}')
    print('  B. 用價格判斷區間：最近 N 根高低差 ≤ k ATR，之後 2 小時做上下緣（中線出場）')
    for N in (30, 45, 60):
        for k in (3, 4, 5):
            for need_mix, nm in ((False, '不看 TJ'), (True, '而且 TJ 全是 MIX')):
                bx = price_boxes(B, N, k, need_mix)
                print(f'    N = {N * TF:3d} 分 k = {k} {nm:<12} {len(bx):4d} 個區間 {summ(edge_trades(B, bx))}')
    print('  C. 反過來做突破：MIX 區間（前 W 分鐘）第一次被突破 10%，停損在中線，形成後 2 小時內')
    for W in (15, 30):
        for R in (1.0, 2.0, 3.0):
            print(f'    W = {W * TF} 分 {R:g}R {summ(breakout_trades(B, eps, W, R))}')


def part5(B, eps):
    print('\n######## 5. MIX 區間突破：穩不穩')
    for W in (15, 23, 30, 38, 45):
        cells = []
        for R in (2.0, 3.0):
            t = breakout_trades(B, eps, W, R); a = t.date < ss.SPLIT
            cells.append(f'{R:g}R {t.net.mean():+.3f}（前 {t.net[a].mean():+.3f} 後 {t.net[~a].mean():+.3f}）{len(t)} 筆')
        print(f'  W = {W * TF:3d} 分  ' + '   '.join(cells))
    print('  W = 60 分換參數')
    for nm, kw in (('突破 10%、停損中線、形成後 2 小時內', {}), ('突破 5%', dict(buf=0.05)), ('突破 20%', dict(buf=0.2)),
                   ('停損在對邊', dict(stop_at='edge')), ('形成後 1 小時內', dict(max_age=30)), ('形成後 4 小時內', dict(max_age=120))):
        for R in (2.0, 3.0):
            print(f'    {nm:<22} {R:g}R {summ(breakout_trades(B, eps, 30, R, **kw))}')
    t = breakout_trades(B, eps, 30, 3.0)
    print('  W = 60 分 3R 分組')
    for nm, g in (('方向', t.side.map({1: '向上突破做多', -1: '向下突破做空'})), ('時段', t.sess),
                  ('區間寬度 ATR', pd.cut(t.hh, [0, 4, 6, 8, 12, 100], right=False)),
                  ('形成後幾分鐘突破', pd.cut(t.age, [0, 15, 30, 60, 121], right=False)),
                  ('突破時', pd.Series(np.where(t.mix_left > 0, 'TJ 還是 MIX', 'TJ 已離開 MIX'), index=t.index))):
        for lab, y in t.groupby(g, observed=True):
            print(f'    {nm} {str(lab):<16} {summ(y)}')


def main():
    B = load()
    eps = mix_periods(B)
    print(f'NQ 2 分 K {B["date"][0]} .. {B["date"][-1]}，MIX = Trend Judge 差值在 ±{TH:g} 內')
    part1(B, eps); part2(B, eps); part3(B, eps); part4(B, eps); part5(B, eps)


if __name__ == '__main__':
    main()
