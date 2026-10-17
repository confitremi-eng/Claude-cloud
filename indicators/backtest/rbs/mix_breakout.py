"""MIX-box breakout as a second alert next to the filtered alerts (NQ 2 minutes, the Databento year).

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/mix_breakout.py

Causal version of the mix_range.py breakout, bar by bar as the indicator sees it: a MIX period starts on the first
MIX bar (Trend Judge spread within +-10) after more than 2 non-MIX bars in a row or a data hole; when it has lasted
W minutes and is still alive, the box is the high / low of those W minutes (mix_range.py only kept periods that went
on past W). Then, for up to 2 hours, the first bar that goes 10% of the box height beyond the top (bottom) is the
breakout: entry at that price (a stop order) or at the close of a bar that closes beyond it (an alert at the close);
stop at the box middle, target R, 2-hour time exit, 1 point cost. A breakout bar in an event window, or one that
breaks both sides, ends the box.
Prints
  1. causal vs mix_range.py; stop-order entry vs entry at the close; W, target, window
  2. filtered alerts (Remi Superb defaults, 3R) alone, breakout alone, both (one position at a time)
  3. monthly R of both and their correlation
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import th_sweep as tw
import ma_position as mp
import streak_study as st
import mix_range as mr

COST = 1.0


def causal_boxes(B, W, grace=mr.GRACE):
    state, hole, trad, h, l = B['state'], B['hole'], B['tradable'], B['h'], B['l']
    boxes = []; s0 = -1; run = 0; formed = False
    for j in range(len(state)):
        if hole[j]: s0 = -1; run = 0
        sj = state[j]
        if sj == 0 and trad[j]:
            if s0 < 0: s0 = j; formed = False
            run = 0
        elif sj in (1, -1) and s0 >= 0:
            run += 1
            if run > grace: s0 = -1; run = 0
        elif sj not in (0, 1, -1):
            s0 = -1; run = 0
        if s0 >= 0 and not formed and j - s0 + 1 == W:
            boxes.append((s0, j, h[s0:j + 1].max(), l[s0:j + 1].min())); formed = True
    return boxes


def breakouts(B, boxes, R, buf=0.1, max_age=60, entry='stop'):
    h, l, c, o, hole, evt = B['h'], B['l'], B['c'], B['o'], B['hole'], B['evt']
    n = len(c); out = []
    for s0, f, top, bot in boxes:
        H = top - bot
        if H <= 0: continue
        bu, bd, mid = top + buf * H, bot - buf * H, (top + bot) / 2
        for j in range(f + 1, min(f + max_age, n - 1) + 1):
            if hole[j]: break
            up, dn = (h[j] >= bu, l[j] <= bd) if entry == 'stop' else (c[j] > bu, c[j] < bd)
            if not (up or dn): continue
            if (up and dn) or evt[j]: break
            side = 1 if up else -1
            px = (max(o[j], bu) if side == 1 else min(o[j], bd)) if entry == 'stop' else c[j]
            stop = mid; risk = (px - stop) * side
            if risk <= 0: break
            tgt = px + side * R * risk; res = None; ex = j; last = min(j + mr.HOLD, n - 1)
            if entry == 'stop' and ((l[j] <= stop) if side == 1 else (h[j] >= stop)): res = -1.0
            else:
                for k in range(j + 1, last + 1):
                    if hole[k]: res = (c[k - 1] - px) * side / risk; ex = k - 1; break
                    if (l[k] <= stop) if side == 1 else (h[k] >= stop): res = -1.0; ex = k; break
                    if (h[k] >= tgt) if side == 1 else (l[k] <= tgt): res = R; ex = k; break
                if res is None: res = (c[last] - px) * side / risk; ex = last
            out.append(dict(i=j, x=ex, side=side, risk=risk, R=res, net=res - COST / risk, win=res - COST / risk > 0,
                            age=(j - f) * mr.TF, hh=H / B['atr'][f], date=B['date'][j], month=B['date'][j][:7],
                            sess=B['sess'][j], tgtR=R, kind='突破'))
            break
    return pd.DataFrame(out)


def seq_all(rows):
    rows = rows.sort_values(['i', 'kind']).reset_index(drop=True); keep = []; busy = -1
    for q, (i, x) in enumerate(zip(rows.i.values, rows.x.values)):
        if i >= busy: keep.append(q); busy = x
    return rows.iloc[keep]


def summ(t):
    if len(t) == 0: return '   0 筆'
    t = t.sort_values('i'); net = t.net.values; a = t.date.values < ss.SPLIT
    eq = np.cumsum(net); dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
    mo = pd.Series(net).groupby(t.month.values).sum(); stk = st.streaks(net > 0)
    return (f'{len(t):4d} 筆  勝率 {100 * (net > 0).mean():4.1f}%  每筆 {net.mean():+.3f}R（前 {net[a].mean():+.3f} 後 {net[~a].mean():+.3f}）'
            f'  一年 {net.sum():+6.1f}R  回撤 {dd:5.1f}R  報酬/回撤 {net.sum() / dd:4.1f}  最長連虧 {stk.max() if len(stk) else 0:2d}  賺錢月 {(mo > 0).sum()}/{len(mo)}')


def filtered(R=3.0):
    s = tw.build(); df = rbs.prepared('NQ', tw.TF)
    s = pd.concat([s, mp.features(s, df)], axis=1)
    b = s[(s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.spread > 10.0) & (s.tjSlow < 3)]
    return pd.DataFrame(dict(i=b.i.values, x=b[f'x{R:g}'].values, side=b.side.values, risk=b.risk.values,
                             net=b[f'r{R:g}'].values - COST / b.risk.values, date=b.date.values, month=b.month.values, kind='趨勢'))


def main():
    B = mr.load()
    eps = mr.mix_periods(B)
    print('######## 1. 突破：逐根判斷 vs 原本的算法；掛單進場 vs 收盤進場')
    for W in (23, 30):
        old = mr.breakout_trades(B, eps, W, 3.0)
        bx = causal_boxes(B, W)
        print(f'  W = {W * mr.TF} 分：原本 {len(old)} 筆 每筆 {old.net.mean():+.3f}R；逐根判斷有 {len(bx)} 個區間')
        for entry, nm in (('stop', '掛突破單（價到就成交）'), ('close', 'K 棒收在突破價外，收盤進場')):
            for R in (2.0, 3.0):
                print(f'    {nm:<22} {R:g}R {summ(breakouts(B, bx, R, entry=entry))}')
    print('  W = 60 分，掛突破單 3R，換有效時間')
    bx = causal_boxes(B, 30)
    for age in (30, 60, 120):
        print(f'    形成後 {age * mr.TF} 分鐘內 {summ(breakouts(B, bx, 3.0, max_age=age))}')

    print('\n######## 2. 合起來（一次一筆）')
    fl = filtered(3.0)
    print(f'  過濾快訊（3R）單獨          {summ(seq_all(fl))}')
    for entry, nm in (('stop', '掛單'), ('close', '收盤')):
        for R in (2.0, 3.0):
            bo = breakouts(B, bx, R, entry=entry)
            both = seq_all(pd.concat([fl, bo[fl.columns]], ignore_index=True))
            part = '  '.join(f'{k} {(both.kind == k).sum()} 筆 {both.net[both.kind == k].sum():+.1f}R' for k in ('趨勢', '突破'))
            print(f'  + 突破（{nm}、{R:g}R）單獨     {summ(seq_all(bo))}')
            print(f'    合起來                   {summ(both)}（{part}）')

    print('\n######## 3. 每月 R（各自單獨做）')
    bo = breakouts(B, bx, 3.0, entry='stop')
    m1 = seq_all(fl).groupby('month').net.sum(); m2 = seq_all(bo).groupby('month').net.sum()
    m = pd.DataFrame({'過濾快訊': m1, 'MIX 突破': m2}).fillna(0)
    m['合計'] = m.sum(axis=1)
    print(m.round(1).to_string())
    print(f'  兩者每月 R 的相關係數 {m["過濾快訊"].corr(m["MIX 突破"]):+.2f}')


if __name__ == '__main__':
    main()
