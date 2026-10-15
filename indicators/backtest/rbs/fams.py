"""Signal families for Remi's Buy/Sell research. All return (i, dir, swing_extreme_for_stop)."""
import numpy as np
import pandas as pd
from rbs import bo_signals, ema


def gate(df, sigs, strong=False):
    """Keep only signals in the Trend Judge direction (|dir| >= 1, or == 2 when strong)."""
    td = df.tj_dir.values
    need = 2 if strong else 1
    return [s for s in sigs if td[s[0]] * s[1] >= need]


def fam_bo(df, N=20, ema_on=True, strong=False):
    return gate(df, bo_signals(df, N=N, ema_on=ema_on), strong)


def fam_tjpull(df, strong=False, touch='fast', trig='swingbar'):
    """Pullback to Trend Judge's fast EMA inside a trend.
    Buy setup arms when (in trend up) the bar's low touches the fast EMA; the lowest bar of the
    pullback becomes the swing bar. Trigger: first close above that swing bar's high (or prior bar high).
    Disarms when the trend gate fails. Mirror for sells."""
    h, l, c = df.high.values, df.low.values, df.close.values
    td = df.tj_dir.values
    lvl = df.emaF.values if touch == 'fast' else df.emaS.values
    need = 2 if strong else 1
    out = []
    armB = armS = False
    swLo = swLoH = swHi = swHiL = np.nan
    for i in range(1, len(c)):
        upT = td[i] >= need
        dnT = td[i] <= -need
        # buys
        if not upT:
            armB = False
        elif l[i] <= lvl[i]:
            if not armB or l[i] < swLo:
                swLo, swLoH = l[i], h[i]
            armB = True
        elif armB:
            levB = swLoH if trig == 'swingbar' else h[i - 1]
            if c[i] > levB:
                out.append((i, 1, swLo))
                armB = False
        # sells
        if not dnT:
            armS = False
        elif h[i] >= lvl[i]:
            if not armS or h[i] > swHi:
                swHi, swHiL = h[i], l[i]
            armS = True
        elif armS:
            levS = swHiL if trig == 'swingbar' else l[i - 1]
            if c[i] < levS:
                out.append((i, -1, swHi))
                armS = False
    return out


def fam_breakout(df, N=20, stopN=10, strong=False):
    """Close crosses the prior N-bar high (low) in the Trend Judge direction; stop = stopN-bar low (high)."""
    h, l, c = df.high.values, df.low.values, df.close.values
    hh = pd.Series(h).rolling(N).max().shift().values
    ll = pd.Series(l).rolling(N).min().shift().values
    sl = pd.Series(l).rolling(stopN).min().values
    sh = pd.Series(h).rolling(stopN).max().values
    td = df.tj_dir.values
    need = 2 if strong else 1
    out = []
    for i in range(N + 1, len(c)):
        if td[i] >= need and c[i] > hh[i] and c[i - 1] <= hh[i - 1]:
            out.append((i, 1, sl[i]))
        if td[i] <= -need and c[i] < ll[i] and c[i - 1] >= ll[i - 1]:
            out.append((i, -1, sh[i]))
    return out
