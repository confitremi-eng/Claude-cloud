"""Trade ES or TXF on the NQ 2-minute Remi Superb signals: how well do the NQ signals carry over?

  cd indicators/backtest
  python3 rbs/nq_follow.py es data/ES_1m_databento.csv
  python3 -I rbs/nq_follow.py txf data_TXFR1_2024.sql data_TXFR1_2025.sql data_TXFR1_2026.sql
  (the NQ file is data/NQ_1m_databento.csv, or NQ_DATA)

NQ signals = Remi Superb on the NQ 2-minute chart with its defaults (threshold 10):
  Trend  filtered alerts: NQ entry at the signal bar's close, stop at the two-bar extreme
  MIX    MIX-box breakout: NQ entry with a stop order at the breakout price, in the minute NQ trades there, stop at
         the box middle
The other market (X) is traded at the same moment: its close of the minute the NQ entry happens in (the signal
bar's last minute for Trend, the breakout minute for MIX), or one minute later. A signal is executable when X has a
bar within the last 3 minutes, past a warm-up, and not in a TXF roll window. X's stop, three ways:
  ATR 換算   X risk = NQ risk x (X ATR / NQ ATR); ATR = 1-minute true range smoothed over ~28 minutes, without the
             range across session gaps. Stop and target (m x X risk) are checked on X's own 1-minute bars.
  跟 NQ 出場  no stop on X: close X at the close of the minute the NQ trade ends in (stop, target or time exit),
             at the earliest one minute after entry. Results in units of the ATR-scaled X risk.
  X 兩根 K    X's own stop at the low (high) of its last 4 minutes, target m x that.
As in the NQ backtests: stop first when both are hit in one minute (an opening gap fills at the open), 120-minute
time exit, flat at the last minute before a hole longer than 30 minutes (TXF session ends). The NQ breakout's
entry minute only checks its stop. One X position at a time (signals are skipped while X is in a trade), cost per
trade in X points (ES 0.5, TXF 2; NQ 1). The NQ result of the same signal comes from the same 1-minute engine.
方向一致 = share of trades where X and NQ both made or both lost money (before costs); corr = correlation of the
per-trade R of X and NQ.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import th_sweep as tw
import ma_position as mp
import mix_range as mr
import mix_breakout as mb
import txf_check as tx

NQ_PATH = os.environ.get('NQ_DATA', os.path.join(ss.DATA_DIR, 'NQ_1m_databento.csv'))
NQ_TH, NQ_COST = 10.0, 1.0
XS = {'es': ('ES', 4.0, 0.5), 'txf': ('TXF', 30.0, 2.0)}
HOLD = 120
WARM = 3000                                   # minutes before ATR / Trend Judge count
MIN = np.timedelta64(1, 'm')
GAP = np.timedelta64(30, 'm')
TPE = 'Asia/Taipei'


class Minutes:
    """1-minute bars as arrays: bar start (UTC), OHLC, last index before a hole, ATR, Trend Judge spread."""

    def __init__(self, one, bad=None):
        self.T = one.index.values.astype('datetime64[ns]')
        self.O, self.H, self.L, self.C = (one[c].values.astype(float) for c in ('open', 'high', 'low', 'close'))
        n = len(self.T); d = np.diff(self.T)
        gap_after = np.r_[d > GAP, True]
        nxt = np.empty(n, int); last = n - 1
        for j in range(n - 1, -1, -1):
            if gap_after[j]: last = j
            nxt[j] = last
        self.nxt = nxt
        pc = np.r_[np.nan, self.C[:-1]]; pc[np.r_[True, d > GAP]] = np.nan
        hl = self.H - self.L
        tr = np.where(np.isnan(pc), hl, np.maximum(hl, np.maximum(np.abs(self.H - pc), np.abs(self.L - pc))))
        self.atr = pd.Series(tr).ewm(alpha=1 / 28, adjust=False).mean().values
        aF = 1 - (1 - 2 / 1131) ** 12; aS = 1 - (1 - 2 / 1131) ** 4
        f = np.empty(n); s = np.empty(n); f[0] = s[0] = self.C[0]
        for j in range(1, n):
            f[j] = f[j - 1] + aF * (self.C[j] - f[j - 1]); s[j] = s[j - 1] + aS * (self.C[j] - s[j - 1])
        self.spread = f - s
        self.ok = np.ones(n, bool) if bad is None else ~np.asarray(bad)
        self.ok[:WARM] = False

    def closed_by(self, t):
        """Index of the last bar that has closed by time t (bar start <= t - 1 minute)."""
        return int(np.searchsorted(self.T, np.datetime64(t, 'ns') - MIN, 'right')) - 1

    def run(self, k, stop, tgt, first, last, entry_minute_stop_only=False):
        """Exit price and index: stop first, a gap through the stop / target fills at the open."""
        for q in range(first, last + 1):
            if (self.L[q] <= stop) if k == 1 else (self.H[q] >= stop):
                if entry_minute_stop_only and q == first: return stop, q
                return (min(stop, self.O[q]) if k == 1 else max(stop, self.O[q])), q
            if entry_minute_stop_only and q == first: continue
            if (self.H[q] >= tgt) if k == 1 else (self.L[q] <= tgt):
                return (max(tgt, self.O[q]) if k == 1 else min(tgt, self.O[q])), q
        return self.C[last], last


def nq_signals(NQ):
    """Remi Superb's two NQ alerts (all of them, before one-at-a-time): time of the NQ entry, side, price, stop."""
    tw.TF = 2; tw.CACHE = os.path.join(ss.DATA_DIR, 'th_sweep_2m.pkl')
    s = tw.build(); df = rbs.prepared('NQ', 2)
    s = pd.concat([s, mp.features(s, df)], axis=1)
    sel = s[(s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.tjSlow < 3) & (s.spread > NQ_TH)].sort_values('i')
    h, l, c = df.high.values, df.low.values, df.close.values
    lm = df.last_min.values.astype('datetime64[ns]'); t2 = df.datetime.values.astype('datetime64[ns]')
    rows = []
    for i, k, d in zip(sel.i.values, sel.side.values, sel.date.values):
        stop = min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])
        je = NQ.closed_by(lm[i] + MIN)
        rows.append(dict(kind='Trend', t=lm[i] + MIN, side=k, px=c[i], stop=stop, je=je, first=je + 1, brk=False, date=d))
    mr.TH = NQ_TH; mb.COST = NQ_COST
    B = mr.load()
    hb, lb, ob, hole, evt = B['h'], B['l'], B['o'], B['hole'], B['evt']
    n = len(hb)
    for s0, f, top, bot in mb.causal_boxes(B, 30, grace=2):
        H = top - bot
        if H <= 0: continue
        bu, bd, mid = top + 0.1 * H, bot - 0.1 * H, (top + bot) / 2
        for j in range(f + 1, min(f + mb.AGE, n - 1) + 1):        # same scan as mix_breakout.breakouts
            if hole[j]: break
            up, dn = hb[j] >= bu, lb[j] <= bd
            if not (up or dn): continue
            if (up and dn) or evt[j]: break
            k = 1 if up else -1
            lvl = bu if k == 1 else bd
            px = max(ob[j], bu) if k == 1 else min(ob[j], bd)
            if (px - mid) * k <= 0: break
            a = int(np.searchsorted(NQ.T, t2[j], 'left')); b = NQ.closed_by(lm[j] + MIN)
            jt = next((q for q in range(a, b + 1) if ((NQ.H[q] >= lvl) if k == 1 else (NQ.L[q] <= lvl))), b)
            rows.append(dict(kind='MIX', t=NQ.T[jt] + MIN, side=k, px=px, stop=mid, je=jt, first=jt, brk=True, date=B['date'][j]))
            break
    return pd.DataFrame(rows).sort_values('t', kind='stable').reset_index(drop=True)


def nq_trade(NQ, g, m):
    """NQ's own result of signal g with target m: gross R and exit index."""
    k, risk = g.side, (g.px - g.stop) * g.side
    last = min(g.je + HOLD, NQ.nxt[g.je])
    if g.first > last: return 0.0, g.je
    px, q = NQ.run(k, g.stop, g.px + k * m * risk, g.first, last, entry_minute_stop_only=g.brk)
    return (px - g.px) * k / risk, q


def x_trade(X, NQ, g, m, mode, jx, nq_exit):
    """X's result for signal g entered at X's close of minute jx: gross points, X risk (points), exit index."""
    k = g.side; Px = X.C[jx]
    jn = NQ.closed_by(g.t)
    rx = (g.px - g.stop) * k * X.atr[jx] / NQ.atr[jn]               # ATR-scaled X risk
    last = min(jx + HOLD, X.nxt[jx])
    if mode == 'X 兩根 K':
        w = slice(max(jx - 3, 0), jx + 1)
        w = [q for q in range(w.start, w.stop) if X.T[q] >= X.T[jx] - 3 * MIN]
        stop = min(X.L[q] for q in w) if k == 1 else max(X.H[q] for q in w)
        rx = (Px - stop) * k
        if not rx > 0: return None
    else:
        stop = Px - k * rx
    if jx + 1 > last: return 0.0, rx, jx
    if mode == '跟 NQ 出場':
        q = X.closed_by(NQ.T[nq_exit] + MIN)
        q = min(max(q, jx + 1), last)
        return (X.C[q] - Px) * k, rx, q
    px, q = X.run(k, stop, Px + k * m * rx, jx + 1, last)
    return (px - Px) * k, rx, q


def et_bucket(t):
    e = pd.Timestamp(t, tz='UTC').tz_convert(ss.NY); mm = e.hour * 60 + e.minute
    return '美股 09:30-16' if 570 <= mm < 960 else '亞洲 20-03' if (mm >= 1200 or mm < 180) else '歐洲 03-09:30' if mm < 570 else '收盤後 16-20'


def tw_bucket(t):
    w = pd.Timestamp(t, tz='UTC').tz_convert(TPE); mm = w.hour * 60 + w.minute
    if 525 <= mm < 825: return '台指日盤 08:45-13:45'
    return '台指夜盤·美股盤中' if et_bucket(t) == '美股 09:30-16' else '台指夜盤·其他'


def evaluate(sig, X, NQ, cost, m, mode, delay=0, need_x_trend=None, kinds=('Trend', 'MIX'), allow=None):
    busy = -1; rows = []
    for g in sig.itertuples():
        if g.kind not in kinds: continue
        if allow is not None and not allow(g.t): continue
        te = np.datetime64(g.t, 'ns') + delay * MIN
        jx = X.closed_by(te)
        if jx < 0 or X.T[jx] < te - 3 * MIN or not X.ok[jx]: continue
        if jx <= busy: continue
        if need_x_trend is not None and not (X.spread[jx] * g.side > need_x_trend): continue
        rn, qn = nq_trade(NQ, g, m)
        res = x_trade(X, NQ, g, m, mode, jx, qn)
        if res is None: continue
        gross, rx, q = res
        busy = q
        rows.append(dict(t=g.t, kind=g.kind, side=g.side, date=g.date, gross=gross, rx=rx, xr=gross / rx, xnet=(gross - cost) / rx,
                         rn=rn, nnet=rn - NQ_COST / ((g.px - g.stop) * g.side), rnq=(g.px - g.stop) * g.side))
    return pd.DataFrame(rows)


def line(t, split):
    if len(t) == 0: return '   0 筆'
    a = t.date.values < split
    eq = np.cumsum(t.xnet.values); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq))
    both = (t.gross != 0) & (t.rn != 0)
    agree = (np.sign(t.gross[both]) == np.sign(t.rn[both])).mean()
    corr = np.corrcoef(t.xr, t.rn)[0, 1] if len(t) > 2 else np.nan
    return (f'{len(t):4d} 筆  勝率 {100 * (t.gross > 0).mean():4.1f}%  每筆 {t.xnet.mean():+.3f}R（前 {t.xnet[a].mean():+.3f} 後 {t.xnet[~a].mean():+.3f}）'
            f'  合計 {t.xnet.sum():+6.1f}R  回撤 {dd:5.1f}R | NQ 同訊號 {t.nnet.mean():+.3f}R | 方向一致 {100 * agree:4.1f}%  corr {corr:+.2f}'
            f' | 停損中位數 NQ {t.rnq.median():.1f} / X {t.rx.median():.2f} 點')


def corr_table(NQ, X, bucket):
    a = pd.Series(np.log(NQ.C), index=pd.DatetimeIndex(NQ.T, tz='UTC'))
    b = pd.Series(np.log(X.C[X.ok]), index=pd.DatetimeIndex(X.T[X.ok], tz='UTC'))
    j = pd.concat([a, b], axis=1, join='inner'); j.columns = ['nq', 'x']
    full = j.reindex(pd.date_range(j.index[0], j.index[-1], freq='1min'))
    out = {}
    for hmin in (2, 30, 120):
        r = full.diff(hmin)
        r = r[(r.index.hour * 60 + r.index.minute) % hmin == 0].dropna()
        bk = pd.Series([bucket(t) for t in r.index.values], index=r.index)
        out[hmin] = {k: (r.nq[bk == k].corr(r.x[bk == k]), (bk == k).sum()) for k in sorted(bk.unique())}
        out[hmin]['全部'] = (r.nq.corr(r.x), len(r))
    return out


def main():
    sym = sys.argv[1].lower(); paths = sys.argv[2:]
    name, xth, cost = XS[sym]
    rbs.DATA['NQ'] = NQ_PATH
    NQ = Minutes(rbs.load1('NQ'))
    if sym == 'txf':
        one = tx.read_sql_1m(paths); X = Minutes(one, tx.roll_mask(one.index))
        bucket = tw_bucket
    else:
        one = pd.read_csv(paths[0], parse_dates=['datetime']).set_index('datetime').sort_index(); X = Minutes(one)
        bucket = et_bucket
    sig = nq_signals(NQ)
    lo, hi = max(NQ.T[WARM], X.T[WARM]), min(NQ.T[-1], X.T[-1])
    sig = sig[(sig.t >= lo) & (sig.t <= hi)].reset_index(drop=True)
    days = sorted(sig.date.unique()); split = days[len(days) // 2]

    print(f'######## 依 NQ 訊號做 {name}：{days[0]} .. {days[-1]}，前 / 後 分界 {split}，{name} 每筆扣 {cost:g} 點（NQ 扣 {NQ_COST:g}）')
    print(f'NQ 訊號（還沒一次一筆）：Trend {(sig.kind == "Trend").sum()} 個、MIX {(sig.kind == "MIX").sum()} 個')
    ex = np.array([(lambda jx, te: jx >= 0 and X.T[jx] >= te - 3 * MIN and X.ok[jx])(X.closed_by(g.t), np.datetime64(g.t, 'ns'))
                   for g in sig.itertuples()])
    bk = np.array([bucket(t) for t in sig.t.values])
    print(f'可以在 {name} 下單的比例：{100 * ex.mean():.1f}%  ' + '  '.join(f'{k} {100 * ex[bk == k].mean():.0f}%（{(bk == k).sum()} 個）' for k in sorted(set(bk))))

    print(f'\n######## NQ 跟 {name} 的報酬相關係數（對數報酬，不重疊取樣）')
    ct = corr_table(NQ, X, bucket)
    for hmin, d in ct.items():
        print(f'  {hmin:>3} 分鐘：' + '  '.join(f'{k} {v[0]:+.2f}（{v[1]}）' for k, v in d.items()))

    print('\n######## NQ 自己做（1 分 K 引擎，一次一筆，同期間）')
    for kinds, nm in ((('Trend',), 'Trend'), (('MIX',), 'MIX'), (('Trend', 'MIX'), '合起來')):
        for m in (1.0, 2.0, 3.0):
            busy = -1; r = []; w = []
            for g in sig.itertuples():
                if g.kind not in kinds or g.je <= busy: continue
                rn, qn = nq_trade(NQ, g, m); busy = qn; r.append(rn - NQ_COST / ((g.px - g.stop) * g.side)); w.append(rn > 0)
            r = np.array(r)
            print(f'  {nm:<6} {m:g}R  {len(r):4d} 筆  勝率 {100 * np.mean(w):4.1f}%  每筆 {r.mean():+.3f}R  合計 {r.sum():+6.1f}R')

    MODES = ('ATR 換算', '跟 NQ 出場', 'X 兩根 K')
    for mode in MODES:
        print(f'\n######## {name}：{mode}')
        for kinds, nm in ((('Trend',), 'Trend'), (('MIX',), 'MIX'), (('Trend', 'MIX'), '合起來')):
            for m in (1.0, 2.0, 3.0):
                t = evaluate(sig, X, NQ, cost, m, mode, kinds=kinds)
                print(f'  {nm:<6} {m:g}R  ' + line(t, split))

    print(f'\n######## {name}：分時段（3R，合起來）')
    for mode in ('ATR 換算', '跟 NQ 出場'):
        t = evaluate(sig, X, NQ, cost, 3.0, mode)
        tb = np.array([bucket(v) for v in t.t.values])
        for k in sorted(set(tb)):
            print(f'  {mode:<8} {k:<18} ' + line(t[tb == k], split))

    print(f'\n######## {name}：多空分開（3R，ATR 換算）')
    for kinds, nm in ((('Trend',), 'Trend'), (('MIX',), 'MIX'), (('Trend', 'MIX'), '合起來')):
        t = evaluate(sig, X, NQ, cost, 3.0, 'ATR 換算', kinds=kinds)
        for sd, snm in ((1, '多'), (-1, '空')):
            print(f'  {nm:<6} {snm}  ' + line(t[t.side == sd], split))

    print(f'\n######## {name}：再加「{name} 自己的 Trend Judge 也同向（差值 > {xth:g}）」（ATR 換算）')
    for kinds, nm in ((('Trend',), 'Trend'), (('MIX',), 'MIX'), (('Trend', 'MIX'), '合起來')):
        for m in (2.0, 3.0):
            t = evaluate(sig, X, NQ, cost, m, 'ATR 換算', need_x_trend=xth, kinds=kinds)
            print(f'  {nm:<6} {m:g}R  ' + line(t, split))

    print(f'\n######## {name}：晚 1 分鐘進場（ATR 換算）')
    for kinds, nm in ((('Trend',), 'Trend'), (('MIX',), 'MIX'), (('Trend', 'MIX'), '合起來')):
        for m in (2.0, 3.0):
            t = evaluate(sig, X, NQ, cost, m, 'ATR 換算', delay=1, kinds=kinds)
            print(f'  {nm:<6} {m:g}R  ' + line(t, split))

    if sym == 'txf':
        night = lambda t: tw_bucket(np.datetime64(t, 'ns')) != '台指日盤 08:45-13:45'
        for c2 in (2.0, 4.0):
            print(f'\n######## TXF：只做台指夜盤，成本 {c2:g} 點')
            for mode, xt in (('ATR 換算', None), ('跟 NQ 出場', None), ('ATR 換算', xth)):
                for m in (2.0, 3.0):
                    nm = mode + ('＋TXF 自己同向' if xt else '')
                    print(f'  {nm:<16} {m:g}R  ' + line(evaluate(sig, X, NQ, c2, m, mode, need_x_trend=xt, allow=night), split))
        print('\n######## TXF：只做台指夜盤，ATR 換算 3R，逐月（R，成本 2 / 4 點）')
        t2 = evaluate(sig, X, NQ, 2.0, 3.0, 'ATR 換算', allow=night)
        mo = pd.to_datetime(t2.date).dt.strftime('%Y-%m')
        cost4 = t2.xnet - 2.0 / t2.rx
        g = pd.DataFrame({'n': t2.groupby(mo).size(), 'c2': t2.xnet.groupby(mo).sum(), 'c4': cost4.groupby(mo).sum(),
                          'nq': t2.nnet.groupby(mo).sum()})
        print(g.round(1).to_string())
        print(f'  賺錢月份：成本 2 點 {(g.c2 > 0).sum()}/{len(g)}，成本 4 點 {(g.c4 > 0).sum()}/{len(g)}，NQ 同訊號 {(g.nq > 0).sum()}/{len(g)}')

    for c2 in ((1.0, 4.0) if sym == 'txf' else (0.25, 1.0)):
        print(f'\n######## {name}：成本改成 {c2:g} 點（ATR 換算，合起來）')
        for m in (2.0, 3.0):
            print(f'  {m:g}R  ' + line(evaluate(sig, X, NQ, c2, m, 'ATR 換算'), split))


if __name__ == '__main__':
    main()
