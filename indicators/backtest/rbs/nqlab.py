import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""Fast engine for the NQ parameter study (numba).

Rule family (all variants are implementable in remis_buy_sell.pine):
  long : Trend Judge diff > thr, close crosses above the highest high of the previous N bars,
         efficiency ratio(erLen) > erMin, at least `skip` minutes after 09:30 New York and before `stop_at`,
         the N-bar window lies inside today's 09:30 session (no lookback across the overnight hole).
  short: mirror.
  stop : lowest low of the last stopN bars - 1 tick (or entry - k * ATR14); target = R x risk (0 = none);
         exit at close after max_hold bars, at the close of the last bar before 16:15, or (optional)
         when the close crosses the opposite M-bar channel. Same-bar stop and target -> stop.
"""
import numpy as np
import pandas as pd
import numba as nb
from rbs import prepared, TICK, COST, atr
from round4 import er, adx

SEL = (pd.Timestamp('2026-04-03', tz='UTC'), pd.Timestamp('2026-09-02', tz='UTC'))   # parameter selection
HOLD = (pd.Timestamp('2026-02-02', tz='UTC'), pd.Timestamp('2026-04-01', tz='UTC'))  # untouched holdout


@nb.njit(cache=True)
def _sim(o, h, l, c, sig_i, sig_d, stop_px, R, max_hold, sess_end, trail_lo, trail_hi, use_trail, be_at):
    m = len(sig_i)
    px_out = np.empty(m)
    kind = np.empty(m, np.int8)       # -1 stop, 1 target, 2 time / session end, 4 trail
    exit_i = np.empty(m, np.int64)
    for k in range(m):
        i = sig_i[k]
        d = sig_d[k]
        entry = c[i]
        stop = stop_px[k]
        risk = (entry - stop) * d
        if R > 0:
            tgt = entry + d * R * risk
        else:
            tgt = np.inf * d
        end = min(sess_end[i], i + max_hold)
        px = c[end]
        kd = 2
        ei = end
        cur = stop
        moved = False
        for j in range(i + 1, end + 1):
            ei = j
            if d == 1:
                if l[j] <= cur:
                    px = cur
                    kd = -1
                    break
                if h[j] >= tgt:
                    px = tgt
                    kd = 1
                    break
                if use_trail and c[j] < trail_lo[j]:
                    px = c[j]
                    kd = 4
                    break
                if be_at > 0 and not moved and h[j] >= entry + be_at * risk:
                    cur = max(cur, entry)
                    moved = True
            else:
                if h[j] >= cur:
                    px = cur
                    kd = -1
                    break
                if l[j] <= tgt:
                    px = tgt
                    kd = 1
                    break
                if use_trail and c[j] > trail_hi[j]:
                    px = c[j]
                    kd = 4
                    break
                if be_at > 0 and not moved and l[j] <= entry - be_at * risk:
                    cur = min(cur, entry)
                    moved = True
        px_out[k] = px
        kind[k] = kd
        exit_i[k] = ei
    return px_out, kind, exit_i


class Lab:
    """Precomputed arrays for one symbol / timeframe."""

    def __init__(self, sym, tf):
        self.sym, self.tf = sym, tf
        df = prepared(sym, tf)
        self.df = df
        self.o, self.h, self.l, self.c = (df[k].values.astype(np.float64) for k in ('open', 'high', 'low', 'close'))
        self.diff = df.tj_diff.values
        et = df.datetime.dt.tz_convert('America/New_York')
        self.mins = (et.dt.hour * 60 + et.dt.minute).values
        self.day = et.dt.date.values
        self.month = et.dt.month.values
        self.time = df.datetime.values
        n = len(df)
        # bars since today's 09:30 bar (-1 before it), inside one data block
        since = np.full(n, -1)
        cnt = -1
        for i in range(n):
            if i == 0 or self.day[i] != self.day[i - 1] or df.block.values[i] != df.block.values[i - 1]:
                cnt = -1
            if self.mins[i] >= 570 and cnt < 0 and self.mins[i] < 960:
                cnt = 0
            elif cnt >= 0:
                cnt += 1
            since[i] = cnt
        self.since = since
        # last bar index before 16:15 on the same day and block (forced exit)
        sess_end = np.arange(n)
        last = n - 1
        for i in range(n - 1, -1, -1):
            if i == n - 1 or self.day[i] != self.day[i + 1] or df.block.values[i] != df.block.values[i + 1] or self.mins[i + 1] >= 975:
                last = i
            sess_end[i] = last
        self.sess_end = sess_end
        self.tradable = df.tradable.values
        self.atr = atr(self.h, self.l, self.c, 14)
        self._cache = {}

    def roll(self, kind, n):
        key = (kind, n)
        if key not in self._cache:
            if kind == 'hh':
                v = pd.Series(self.h).rolling(n).max().shift().values
            elif kind == 'll':
                v = pd.Series(self.l).rolling(n).min().shift().values
            elif kind == 'lo':
                v = pd.Series(self.l).rolling(n).min().values
            elif kind == 'hi':
                v = pd.Series(self.h).rolling(n).max().values
            elif kind == 'er':
                v = np.nan_to_num(er(self.df, n), nan=0.0)
            elif kind == 'adx':
                v = adx(self.df, n)
            elif kind == 'bias':
                # +1 / -1: previous New York day's 16:00 close above / below its n-day average (0 = unknown)
                rth = (self.mins >= 570) & (self.mins < 960)
                closes = pd.Series(self.c[rth], index=self.day[rth]).groupby(level=0).last()
                prev = np.sign(closes - closes.rolling(n).mean()).shift(1)
                v = np.nan_to_num(pd.Series(self.day).map(prev).values.astype(float), nan=0.0)
            self._cache[key] = v
        return self._cache[key]

    def signals(self, N=30, thr=40.0, erLen=20, erMin=0.4, adxMin=0.0, skip=0, stop_at=960, side=0, period=SEL, bias=0):
        """Signal bar indices and directions. skip = minutes after 09:30 before the first entry."""
        c = self.c
        hh, ll = self.roll('hh', N), self.roll('ll', N)
        up = (c > hh) & (np.r_[False, c[:-1] <= hh[:-1]])
        dn = (c < ll) & (np.r_[False, c[:-1] >= ll[:-1]])
        ok = (self.since >= N + 1) & (self.mins >= 570 + skip) & (self.mins < stop_at) & self.tradable
        t0, t1 = (np.datetime64(p.tz_convert(None)) for p in period)
        ok &= (self.time >= t0) & (self.time < t1)
        if erMin > 0:
            ok &= self.roll('er', erLen) > erMin
        if adxMin > 0:
            ok &= self.roll('adx', 14) > adxMin
        d = self.diff
        L = up & ok & (d > thr)
        S = dn & ok & (d < -thr)
        if bias > 0:
            b = self.roll('bias', bias)
            L &= b > 0
            S &= b < 0
        if side == 1:
            S[:] = False
        elif side == -1:
            L[:] = False
        il, is_ = np.nonzero(L)[0], np.nonzero(S)[0]
        idx = np.r_[il, is_]
        dirs = np.r_[np.ones(len(il), np.int64), -np.ones(len(is_), np.int64)]
        order = np.argsort(idx, kind='stable')
        return idx[order], dirs[order]

    def trades(self, idx, dirs, stopN=10, atrK=0.0, R=2.0, max_hold=60, trail=0, be_at=0.0):
        tick, cost = TICK[self.sym], COST[self.sym]
        if atrK > 0:
            stop = self.c[idx] - dirs * atrK * self.atr[idx]
        else:
            lo, hi = self.roll('lo', stopN), self.roll('hi', stopN)
            stop = np.where(dirs == 1, lo[idx] - tick, hi[idx] + tick)
        risk = (self.c[idx] - stop) * dirs
        good = risk > 0
        idx, dirs, stop, risk = idx[good], dirs[good], stop[good], risk[good]
        if trail > 0:
            tlo, thi = self.roll('ll', trail), self.roll('hh', trail)
        else:
            tlo = thi = np.zeros(len(self.c))
        px, kind, exit_i = _sim(self.o, self.h, self.l, self.c, idx.astype(np.int64), dirs.astype(np.int64), stop.astype(np.float64),
                        float(R), int(max_hold), self.sess_end.astype(np.int64), np.nan_to_num(tlo, nan=-np.inf),
                        np.nan_to_num(thi, nan=np.inf), trail > 0, float(be_at))
        pts = (px - self.c[idx]) * dirs - cost
        return pd.DataFrame({'i': idx, 'dir': dirs, 'R': pts / risk, 'pts': pts, 'risk': risk, 'kind': kind,
                             'exit_i': exit_i, 'day': self.day[idx], 'month': self.month[idx], 'time': self.time[idx]})


def day_limits(t, max_trades=0, max_losses=0):
    """Keep trades in entry order; per New York day skip new entries once `max_trades` were taken or
    `max_losses` taken trades have already closed at a loss (0 = no limit)."""
    keep = np.zeros(len(t), bool)
    for _, g in t.groupby('day', sort=False):
        taken = []
        for r in g.sort_values('i').itertuples():
            if max_trades and len(taken) >= max_trades:
                continue
            if max_losses and sum(1 for e, rr in taken if e < r.i and rr <= 0) >= max_losses:
                continue
            taken.append((r.exit_i, r.R))
            keep[t.index.get_loc(r.Index)] = True
    return t[keep]


def summarize(t):
    if len(t) == 0:
        return dict(n=0, win=np.nan, avgR=np.nan, pts=np.nan)
    return dict(n=len(t), win=100 * (t.R > 0).mean(), avgR=t.R.mean(), pts=t.pts.mean())
