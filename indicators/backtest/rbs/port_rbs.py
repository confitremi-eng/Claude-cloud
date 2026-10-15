import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""Line-by-line port of remis_buy_sell.pine (breakout mode) + equivalence checks against the research code."""
import numpy as np, pandas as pd
from rbs import prepared, simulate, TH, TICK, COST
from round3 import variant
from round4 import er as er_research

def pine_rbs(df, sym, dir_in=None, brkLen=30, stopLen=10, erLen=20, erMin=0.4, need=2, rthOnly=True,
             exitClose=True, targetR=2.0, maxHold=60, emaLen=1130, fastSec=5, slowSec=15, tf=1):
    h, l, c, o = df.high.values, df.low.values, df.close.values, df.open.values
    n = len(c); tick = TICK[sym]; cost = COST[sym]; th, st = TH[sym]
    et = df.datetime.dt.tz_convert('America/New_York'); m = (et.dt.hour * 60 + et.dt.minute).values
    inRth = (m >= 570) & (m < 960); inHold = (m >= 570) & (m < 975)
    dayid = (et + pd.Timedelta(hours=6)).dt.date.values
    t2 = (df.datetime.dt.floor('2min')).values
    # trend: minute-equivalent EMAs on chart closes, locked at each new 2-minute window
    aF = 1 - (1 - 2 / (emaLen + 1)) ** (60 / fastSec * tf); aS = 1 - (1 - 2 / (emaLen + 1)) ** (60 / slowSec * tf)
    eF = eS = np.nan; locked = np.nan; dircode = np.zeros(n, int)
    # ER
    ch = np.abs(np.diff(c, prepend=np.nan))
    trades = []; S = np.zeros((3, 6)); sigs = []
    for i in range(n):
        eF = c[i] if np.isnan(eF) else aF * c[i] + (1 - aF) * eF
        eS = c[i] if np.isnan(eS) else aS * c[i] + (1 - aS) * eS
        if i > 0 and t2[i] != t2[i - 1]:
            locked = eF - eS
        if dir_in is not None:
            d = int(dir_in[i])
        else:
            d = 0 if np.isnan(locked) else (2 if locked > st else 1 if locked > th else -2 if locked < -st else -1 if locked < -th else 0)
        dircode[i] = d
        upOK, dnOK = d >= need, d <= -need
        sessOK = (not rthOnly) or inRth[i]
        newDay = i > 0 and dayid[i] != dayid[i - 1]
        forceOut = rthOnly and exitClose and ((not inHold[i]) or newDay)
        if i >= erLen:
            den = ch[i - erLen + 1:i + 1].sum()
            erv = abs(c[i] - c[i - erLen]) / den if den > 0 else 0.0
        else:
            erv = 0.0
        chopOK = erv > erMin
        if i >= brkLen + 1:
            hh = h[i - brkLen:i].max(); hh1 = h[i - 1 - brkLen:i - 1].max()
            ll = l[i - brkLen:i].min(); ll1 = l[i - 1 - brkLen:i - 1].min()
            brkUp = c[i] > hh and c[i - 1] <= hh1; brkDn = c[i] < ll and c[i - 1] >= ll1
        else:
            brkUp = brkDn = False
        lstop = l[max(0, i - stopLen + 1):i + 1].min() - tick; sstop = h[max(0, i - stopLen + 1):i + 1].max() + tick
        longSetup = brkUp and upOK and sessOK and chopOK
        shortSetup = brkDn and dnOK and sessOK and chopOK
        # --- stats (every historical bar is confirmed) ---
        for k in range(len(trades) - 1, -1, -1):
            dirn, en, stp, tg, bar = trades[k]
            hitS = l[i] <= stp if dirn == 1 else h[i] >= stp
            hitT = h[i] >= tg if dirn == 1 else l[i] <= tg
            res = 3 if forceOut else -1 if hitS else 1 if hitT else 2 if i - bar >= maxHold else 0
            if res:
                px = o[i] if res == 3 else stp if res == -1 else tg if res == 1 else c[i]
                pts = (px - en) * dirn - cost; r = pts / ((en - stp) * dirn)
                for gi in (0, 1 if dirn == 1 else 2):
                    S[gi, 0] += 1; S[gi, 2] += r; S[gi, 5] += pts
                    if r > 0: S[gi, 1] += 1; S[gi, 3] += r
                    else: S[gi, 4] -= r
                del trades[k]
        if longSetup and c[i] - lstop > 0:
            trades.append([1, c[i], lstop, c[i] + targetR * (c[i] - lstop), i]); sigs.append((i, 1, lstop + tick))
        if shortSetup and sstop - c[i] > 0:
            trades.append([-1, c[i], sstop, c[i] - targetR * (sstop - c[i]), i]); sigs.append((i, -1, sstop - tick))
    return sigs, S, dircode

START = pd.Timestamp('2026-04-03', tz='UTC')
for sym in ('NQ', 'ES'):
    for tf in (1, 5):
        df = prepared(sym, tf)
        # (1) same trend input as the research code -> signals must match the research rule exactly
        sigs, S, _ = pine_rbs(df, sym, dir_in=df.tj_dir.values, tf=tf, exitClose=False)
        E = er_research(df)
        ref = [s for s in variant(df, sym, N=30) if E[s[0]] > 0.4]
        mine = [s for s in sigs if df.datetime.iloc[s[0]] >= START]
        same = [(i, d) for i, d, _ in mine] == [(i, d) for i, d, _ in ref]
        stops_same = all(abs(a[2] - b[2]) < 1e-9 for a, b in zip(mine, ref))
        print(f'{sym} {tf}m: signals identical to research rule: {same} ({len(mine)} vs {len(ref)}), stops identical: {stops_same}')
        # (2) trade results: Pine engine without session exits vs research simulator on one continuous block
        df1 = df.copy(); df1['block'] = 0; df1['bar_in_block'] = np.arange(len(df1))
        t = simulate(df1, ref, sym, R=2.0, hold=60, warm=0)
        t = t[t.i < len(df1) - 61]
        print(f'   research sim: n={len(t)} win={100*(t.R>0).mean():.2f}% avgR={t.R.mean():+.4f}   Pine port: n={S[0,0]:.0f} win={100*S[0,1]/S[0,0]:.2f}% avgR={S[0,2]/S[0,0]:+.4f} (port counts {len(sigs)-len(mine)} pre-start trades)')
        # (3) how close is the indicator's own minute-equivalent trend to the research trend?
        _, _, dc = pine_rbs(df, sym, tf=tf)
        ok = df.datetime >= START
        print(f'   minute-mode trend state agrees with research trend on {100*(dc[ok] == df.tj_dir.values[ok]).mean():.1f}% of bars')

# (4) the data has full CME sessions only from 2026-08-17 on (earlier days are 09:30-16:14 only, which leaves gaps
#     the indicator's minute mode cannot bridge). On the full-session days the minute mode should track the trend.
FULL = pd.Timestamp('2026-08-18', tz='UTC')
for sym in ('NQ', 'ES'):
    for tf in (1, 2, 3, 5):
        df = prepared(sym, tf)
        _, _, dc = pine_rbs(df, sym, tf=tf)
        ok = (df.datetime >= FULL).values
        print(f'{sym} {tf}m: minute-mode trend agrees with research trend on {100*(dc[ok] == df.tj_dir.values[ok]).mean():.1f}% '
              f'of bars on full-session days ({ok.sum()} bars)')
