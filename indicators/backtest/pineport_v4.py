import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""Line-by-line port of the v4 Pine signal + backtest-stats logic, checked against bt.simulate()."""
import numpy as np, pandas as pd
from bt import load, signals, simulate, ema

def pine_v4(df, stageLen=20, emaLen=8, emaEnable=True, targetR=1.5, maxHold=60, costPts=1.0, stopBuf=1, mintick=0.25, trend=None):
    h, l, c = df.high.values, df.low.values, df.close.values
    sigEma = ema((h + l) / 2, emaLen)
    refHigh = swLow = refLow = swHigh = np.nan; armBuy = armSell = False
    T = []                                    # open trades: [dir, entry, stop, tgt, bar, grp]
    S = np.zeros((3, 6))                      # per group: n, wins, sumR, grossW, grossL, pts
    buf = stopBuf * mintick
    sigs = []; closed = {}
    for i in range(len(c)):
        lp = l[i - stageLen:i].min() if i >= stageLen else np.nan
        hp = h[i - stageLen:i].max() if i >= stageLen else np.nan
        newLow = (not np.isnan(lp)) and l[i] < lp
        newHigh = (not np.isnan(hp)) and h[i] > hp
        trigBuy = (not newLow) and armBuy and c[i] > refHigh
        trigSell = (not newHigh) and armSell and c[i] < refLow
        buyStop, sellStop = swLow, swHigh
        if newLow: refHigh, swLow, armBuy = h[i], l[i], True
        elif trigBuy: armBuy = False
        if newHigh: refLow, swHigh, armSell = l[i], h[i], True
        elif trigSell: armSell = False
        buySetup = trigBuy and (not emaEnable or c[i] > sigEma[i])
        sellSetup = trigSell and (not emaEnable or c[i] < sigEma[i])
        # --- stats (barstate.isconfirmed on every historical bar) ---
        for k in range(len(T) - 1, -1, -1):
            dirn, en, st, tg, bar, g = T[k]
            hitStop = l[i] <= st if dirn == 1 else h[i] >= st
            hitTgt = h[i] >= tg if dirn == 1 else l[i] <= tg
            res = -1 if hitStop else 1 if hitTgt else 2 if i - bar >= maxHold else 0
            if res != 0:
                px = st if res == -1 else tg if res == 1 else c[i]
                pts = (px - en) * dirn - costPts; r = pts / ((en - st) * dirn)
                closed[(bar, dirn)] = r
                for gi in ([0, g] if g > 0 else [0]):
                    S[gi, 0] += 1; S[gi, 2] += r; S[gi, 5] += pts
                    if r > 0: S[gi, 1] += 1; S[gi, 3] += r
                    else: S[gi, 4] -= r
                del T[k]
        useTrend = trend is not None
        if buySetup and c[i] - (buyStop - buf) > 0:
            st = buyStop - buf; T.append([1, c[i], st, c[i] + targetR * (c[i] - st), i, (1 if trend[i] == 1 else 2) if useTrend else 0]); sigs.append((i, 1))
        if sellSetup and (sellStop + buf) - c[i] > 0:
            st = sellStop + buf; T.append([-1, c[i], st, c[i] - targetR * (st - c[i]), i, (1 if trend[i] == -1 else 2) if useTrend else 0]); sigs.append((i, -1))
    return S, sigs, T, closed

for tf in (1, 5):
    df = load(tf)
    df1 = df.copy(); df1['block'] = 0; df1['bar_in_block'] = np.arange(len(df1))     # one continuous series
    S, sigs, openT, closed = pine_v4(df1)
    ref = simulate(df1, signals(df1), targets=(1.5,), horizon=60, cost=1.0, stop_buf=0.25, warm=0)
    ref = ref[ref.i < len(df1) - 61]              # drop trades the Pine engine would still hold at the end
    same_sigs = [(i, d) for i, d, *_ in signals(df1)] == sigs
    print(f'{tf}-min: signals identical to backtester: {same_sigs} ({len(sigs)})')
    print(f'   Pine port: n={S[0,0]:.0f} win={100*S[0,1]/S[0,0]:.2f}% avgR={S[0,2]/S[0,0]:+.4f} PF={S[0,3]/S[0,4]:.3f} pts={S[0,5]:+.1f}')
    r = ref['R1.5']
    print(f'   backtester: n={len(r)} win={100*(r>0).mean():.2f}% avgR={r.mean():+.4f} PF={r[r>0].sum()/-r[r<0].sum():.3f}')

    m = [(row.i, row.dir, row['R1.5'], closed.get((row.i, row.dir))) for _, row in ref.iterrows()]
    diff = [x for x in m if x[3] is None or abs(x[2] - x[3]) > 1e-9]
    print(f'   trade-by-trade: {len(m)} compared, {len(diff)} differ', diff[:3])
