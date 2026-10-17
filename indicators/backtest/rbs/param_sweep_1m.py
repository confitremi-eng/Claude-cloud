"""1-minute parameter search on NQ as a stand-in for QQQ (the Databento year).

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/param_sweep_1m.py qqq     # QQQ chart: cash-session bars only
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/param_sweep_1m.py nq      # all NQ bars (all day, or cash-session signals)

Charts
  qqq  NQ bars cut to what a QQQ chart shows (weekdays 09:30-16:00 ET, NYSE holidays out), and everything computed
       on those bars only: signals, EMA, ATR, Trend Judge (EMAs fed the cash-session closes), 1-hour EMA20 on stock
       hourly bars (09:30, 10:30, ...); flat at the close every day
  nq   the 24-hour NQ chart; signals all day, or only those in the cash session
Signals: the original rule with stage N (階段) and EMA E on the close (Ema number), EMA check on or off, i.e. the
(N, 0, E, 1) / (N, 0, E, 0) settings. Filter = none, or Remi Superb's: Trend Judge 有趨勢 (spread > TH NQ points),
last complete 1-hour close on the trade's side of its EMA20, stop >= 1 ATR, close within D ATR of the 15-second
EMA1130, data / open / close / Globex windows avoided. Exits: entry at the signal close, stop at the extreme of the
signal bar and the one before, fixed R target, stop first when both are in one bar, 60-bar time exit, flat before a
data hole; one position at a time; 1 point cost (also 0.5). For QQQ divide NQ points by about 41.
Picks on 2025-10 .. 2026-05 (前) and checks on 2026-06 .. 10 (後).
Prints
  1. the starting point (30, 0, 13, 1) under each filter and target
  2. which filter / target is the most robust: how many of the 54 signal settings make money in both halves
  3. the best settings picked on the first half, with their second half
  4. stage x EMA grids for the three most robust filters, and with no filter
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import itertools
import numpy as np
import pandas as pd
from numba import njit
import rbs
import setup_study as ss

STAGES = (10, 15, 20, 25, 30, 35, 40, 50, 60)
EMAS = (5, 8, 13, 21, 34)
TARGETS = np.array([1.0, 1.5, 2.0, 3.0])
THS = (10.0, 15.0, 20.0, 30.0)
THS_QQQ = (10.0, 20.0, 30.0, 40.0)
DISTS = (3.0, 4.0, 5.0, 7.0, np.inf)
HOURS = ('全天', '美股盤')
HORIZON = 60


@njit(cache=True)
def sig_nb(h, l, c, lo, hi, ema, ema_on, stage):
    n = len(c); B = np.zeros(n, np.int8); S = np.zeros(n, np.int8)
    armB = False; armS = False; refH = np.nan; refL = np.nan
    for i in range(stage, n):
        newLow = l[i] < lo[i]; newHigh = h[i] > hi[i]
        trigB = armB and c[i] > refH
        trigS = armS and c[i] < refL
        if trigB and ((not ema_on) or c[i] > ema[i]): B[i] = 1
        if trigS and ((not ema_on) or c[i] < ema[i]): S[i] = 1
        if trigB: armB = False
        elif newLow:
            armB = True; refH = h[i]
        if trigS: armS = False
        elif newHigh:
            armS = True; refL = l[i]
    return B, S


@njit(cache=True)
def outcomes_nb(idx, side, h, l, c, nxt, horizon, targets):
    m = len(idx); T = len(targets)
    R = np.full((m, T), np.nan); X = np.zeros((m, T), np.int64); risk = np.zeros(m)
    for q in range(m):
        i = idx[q]; k = side[q]
        if k == 1: stop = min(l[i - 1], l[i])
        else: stop = max(h[i - 1], h[i])
        rk = (c[i] - stop) * k; risk[q] = rk
        end = min(i + horizon, nxt[i])
        if rk <= 0 or end <= i: continue
        for t in range(T):
            Rt = targets[t]; tgt = c[i] + k * Rt * rk; res = np.nan; ex = end
            for j in range(i + 1, end + 1):
                hit_stop = l[j] <= stop if k == 1 else h[j] >= stop
                if hit_stop:
                    res = -1.0; ex = j; break
                hit_tgt = h[j] >= tgt if k == 1 else l[j] <= tgt
                if hit_tgt:
                    res = Rt; ex = j; break
            if np.isnan(res): res = (c[end] - c[i]) * k / rk
            R[q, t] = res; X[q, t] = ex
    return R, X, risk


@njit(cache=True)
def seq_nb(idx, x):
    keep = np.zeros(len(idx), np.bool_); busy = -1
    for q in range(len(idx)):
        if idx[q] >= busy:
            keep[q] = True; busy = x[q]
    return keep


NYSE_CLOSED = {'2025-11-27', '2025-12-25', '2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25',
               '2026-06-19', '2026-07-03', '2026-09-07'}
EARLY_CLOSE = {'2025-11-28', '2025-12-24'}                  # NYSE closes at 13:00


def qqq_minutes():
    """NQ 1-minute bars cut to what a QQQ chart shows: weekdays 09:30-16:00 ET (13:00 on early-close days),
    NYSE holidays out."""
    one = rbs.load1('NQ')
    et = one.index.tz_convert(ss.NY)
    m = et.hour * 60 + et.minute; d = et.strftime('%Y-%m-%d')
    end = np.where(np.isin(d, list(EARLY_CLOSE)), 780, 960)
    return one[(et.weekday < 5) & (m >= 570) & (m < end) & ~np.isin(d, list(NYSE_CLOSED))]


def qqq_trend(one):
    """Trend Judge EMAs fed only the cash-session closes, one step per minute, the way Remi Superb 1m runs on QQQ."""
    seg = rbs.segments(one.index); parts = []
    for s in np.unique(seg):
        c = one.close[seg == s]
        ef = c.ewm(alpha=rbs.A_FAST, adjust=False).mean(); es = c.ewm(alpha=rbs.A_SLOW, adjust=False).mean()
        parts.append(pd.DataFrame({'diff': ef - es, 'emaF': ef, 'emaS': es}))
    return pd.concat(parts)


def qqq_hourly(one):
    """1-hour bars of a stock chart (09:30, 10:30, ... 15:30-16:00), close vs EMA20, usable once the hour is done."""
    et = one.index.tz_convert(ss.NY)
    k = (et.hour * 60 + et.minute - 570) // 60
    g = pd.DataFrame({'c': one.close.values, 'key': et.normalize() + pd.to_timedelta(570 + 60 * k, unit='min'),
                      't': one.index + pd.Timedelta(minutes=1)})
    hb = g.groupby('key').agg(c=('c', 'last'), t=('t', 'last')).sort_values('t')
    he = hb.c.ewm(span=20, adjust=False).mean()
    return pd.DataFrame({'t': hb.t.reset_index(drop=True), 'h1': np.sign(hb.c - he).values})


def chart_frame(chart):
    if chart == 'nq':
        return rbs.prepared('NQ', 1), ss.hourly()
    one = qqq_minutes()
    df = rbs.trend_judge(rbs.bars(one, 1), qqq_trend(one), 1, 'NQ')
    df['seg'] = rbs.segments(pd.DatetimeIndex(df.datetime))
    day = df.datetime.dt.tz_convert(ss.NY).dt.date
    warm = {d for _, g in day.groupby(df.seg) for d in sorted(g.unique())[:rbs.WARM_DAYS]}
    df['tradable'] = ~day.isin(warm).values
    return df, qqq_hourly(one)


def bar_arrays(chart='nq'):
    df, H = chart_frame(chart)
    h, l, c = df.high.values, df.low.values, df.close.values
    nxt, atr = ss.bar_context(df, 1)
    start = df.datetime.dt.tz_convert(ss.NY); entry = (df.datetime + pd.Timedelta(minutes=1)).dt.tz_convert(ss.NY)
    ms = (start.dt.hour * 60 + start.dt.minute).values; me = (entry.dt.hour * 60 + entry.dt.minute).values
    wd = entry.dt.weekday.values; fomc = np.isin(entry.dt.date.astype(str).values, list(ss.FOMC))
    evt = (((wd < 5) & (((me >= 508) & (me < 540)) | ((me >= 598) & (me < 615)))) | (fomc & (me >= 838) & (me < 900))
           | ((me >= 570) & (me < 600)) | ((me >= 945) & (me < 975)) | ((me >= 1005) & (me < 1020)) | ((me >= 1080) & (me < 1110)))
    h1 = pd.merge_asof(pd.DataFrame({'t': df.datetime + pd.Timedelta(minutes=1)}), H, on='t', direction='backward').h1.values
    return dict(df=df, h=h, l=l, c=c, nxt=nxt, atr=atr, evt=evt, rth=(ms >= 570) & (ms < 960), h1=h1,
                diff=df.tj_diff.values, emaS=df.emaS.values, date=start.dt.date.astype(str).values,
                month=start.dt.strftime('%Y-%m').values, tradable=df.tradable.values)


def signal_table(A, N, E, ema_on, ema_cache, roll_cache):
    h, l, c = A['h'], A['l'], A['c']
    if N not in roll_cache:
        roll_cache[N] = (pd.Series(l).rolling(N).min().shift().values, pd.Series(h).rolling(N).max().shift().values)
    if E not in ema_cache:
        ema_cache[E] = pd.Series(c).ewm(span=E, adjust=False).mean().values
    lo, hi = roll_cache[N]
    B, S = sig_nb(h, l, c, lo, hi, ema_cache[E], ema_on, N)
    idx = np.where((B == 1) | (S == 1))[0]
    idx = idx[(idx >= 15) & A['tradable'][idx]]
    side = np.where(B[idx] == 1, 1, -1).astype(np.int64)
    R, X, risk = outcomes_nb(idx, side, h, l, c, A['nxt'], HORIZON, TARGETS)
    ok = (risk > 0) & ~np.isnan(R[:, 0])
    idx, side, R, X, risk = idx[ok], side[ok], R[ok], X[ok], risk[ok]
    atr = A['atr']
    return dict(i=idx, side=side, R=R, X=X, risk=risk, spread=A['diff'][idx] * side, h1=A['h1'][idx],
                risk_atr=risk / atr[idx - 1], slow=(c[idx] - A['emaS'][idx]) * side / atr[idx],
                evt=A['evt'][idx], rth=A['rth'][idx], date=A['date'][idx], month=A['month'][idx])


def evaluate(T, th, dist, hours, t, cost):
    if th is None: m = np.ones(len(T['i']), np.bool_)                        # 不過濾：原始訊號
    else: m = (T['spread'] > th) & (T['h1'] == T['side']) & (T['risk_atr'] >= 1.0) & (T['slow'] < dist) & ~T['evt']
    if hours == '美股盤': m &= T['rth']
    sel = np.where(m)[0]
    keep = sel[seq_nb(T['i'][sel], T['X'][sel, t])]
    r = T['R'][keep, t]; net = r - cost / T['risk'][keep]
    if len(net) == 0: return None
    a = T['date'][keep] < ss.SPLIT
    eq = np.cumsum(net); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq))
    mo = pd.Series(net).groupby(T['month'][keep]).sum()
    return dict(n=len(net), win=(r > 0).mean(), net=net.mean(), A=net[a].mean() if a.any() else np.nan,
                B=net[~a].mean() if (~a).any() else np.nan, nA=int(a.sum()), nB=int((~a).sum()), tot=net.sum(), dd=dd,
                mpos=int((mo > 0).sum()), mn=len(mo))


def fmt(x):
    return (f'{x["n"]:5d} 筆  勝率 {100 * x["win"]:4.1f}%  每筆 {x["net"]:+.3f}R（前 {x["A"]:+.3f} 後 {x["B"]:+.3f}）'
            f'  一年 {x["tot"]:+6.1f}R  回撤 {x["dd"]:5.1f}R  賺錢月 {x["mpos"]}/{x["mn"]}')


def filt_name(r):
    return f'{r.hours} 不過濾' if r.th < 0 else f'{r.hours} 門檻 {r.th:g} 距離 {r.dist:g}'


def grid(G, hours, th, dist, R):
    g = G[(G.cost == 1.0) & (G.hours == hours) & (G.th == th) & (G.dist == dist) & (G.R == R)]
    print(f'\n  {filt_name(g.iloc[0])} {R:g}R')
    print('    階段\\EMA' + ''.join(f'{e:>22}' for e in EMAS) + f'{"關":>22}')
    for N in STAGES:
        cells = []
        for e, on in [(e, True) for e in EMAS] + [(0, False)]:
            x = g[(g.N == N) & (g.E == e) & (g.on == on)]
            cells.append(f'{x.net.iloc[0]:+.3f}({x.A.iloc[0]:+.2f}/{x.B.iloc[0]:+.2f}){x.n.iloc[0]:>4d}' if len(x) else '-')
        print(f'    {N:>8} ' + ''.join(f'{v:>22}' for v in cells))


def main():
    chart = sys.argv[1] if len(sys.argv) > 1 else 'nq'
    hours_list, ths = (HOURS, THS) if chart == 'nq' else (('美股盤',), THS_QQQ)
    A = bar_arrays(chart)
    days = len(set(A['date'][A['tradable']]))
    ema_cache, roll_cache, tables = {}, {}, {}
    for N, E, on in itertools.product(STAGES, EMAS, (True, False)):
        if not on and E != EMAS[0]: continue                       # EMA off: E does not matter
        tables[(N, E if on else 0, on)] = signal_table(A, N, E, on, ema_cache, roll_cache)
    filters = [(None, np.inf)] + list(itertools.product(ths, DISTS))
    rows = []
    for (N, E, on), T in tables.items():
        for (th, dist), hours, ti in itertools.product(filters, hours_list, range(len(TARGETS))):
            for cost in (1.0, 0.5):
                x = evaluate(T, th, dist, hours, ti, cost)
                if x: rows.append(dict(N=N, E=E, on=on, th=-1.0 if th is None else th, dist=dist, hours=hours, R=TARGETS[ti], cost=cost, **x))
    G = pd.DataFrame(rows)
    G['label'] = G.apply(lambda r: f'({r.N}, 0, {r.E if r.on else "-"}, {int(r.on)})', axis=1)
    print(f'NQ 1 分 K（代替 QQQ）{"，只留美股盤的 K 棒（QQQ 圖）" if chart == "qqq" else "，全天的 K 棒"}，{days} 個交易日；一次一筆')

    print('\n######## 1. 起點 (30, 0, 13, 1)，扣 1 點')
    g = G[(G.N == 30) & (G.E == 13) & G.on & (G.cost == 1.0)]
    for _, r in g.sort_values(['hours', 'th', 'dist', 'R']).iterrows():
        print(f'  {filt_name(r)} {r.R:g}R  {fmt(r)}')

    print('\n######## 2. 哪一種過濾 / 目標最穩：54 組訊號參數裡，前後半年都賺的有幾組（扣 1 點，前後各至少 40 筆）')
    g = G[G.cost == 1.0].copy()
    g['both'] = (g.A > 0) & (g.B > 0) & (g.nA >= 40) & (g.nB >= 40)
    k = g.groupby(['hours', 'th', 'dist', 'R']).agg(both=('both', 'sum'), med=('net', 'median'), cnt=('net', 'size')).reset_index()
    k = k.sort_values(['both', 'med'], ascending=False)
    for _, r in k.head(12).iterrows():
        x = G[(G.N == 30) & (G.E == 13) & G.on & (G.cost == 1.0) & (G.hours == r.hours) & (G.th == r.th) & (G.dist == r.dist) & (G.R == r.R)]
        print(f'  {filt_name(r)} {r.R:g}R：{int(r.both):2d}/{int(r.cnt)} 組前後都賺，每筆中位數 {r.med:+.3f}R'
              f'；起點 {x.net.iloc[0]:+.3f}R（前 {x.A.iloc[0]:+.3f} 後 {x.B.iloc[0]:+.3f}）{x.n.iloc[0]} 筆')

    for cost in (1.0, 0.5):
        print(f'\n######## 3. 前半年挑（每筆淨 R，前半年至少 80 筆），看後半年；扣 {cost:g} 點')
        for hours in hours_list:
            g = G[(G.cost == cost) & (G.hours == hours) & (G.nA >= 80)].sort_values('A', ascending=False)
            print(f'  {hours}：前半年最好的 12 組')
            for _, r in g.head(12).iterrows():
                print(f'    {r.label:<14} {filt_name(r)} {r.R:g}R  {fmt(r)}')
            print(f'  {hours}：前半年排名和後半年排名的相關 {g.A.rank().corr(g.B.rank()):+.2f}；'
                  f'前半年 > 0 的 {(g.A > 0).sum()} 組裡，後半年也 > 0 的 {((g.A > 0) & (g.B > 0)).sum()} 組（全部 {len(g)} 組）')

    print('\n######## 4. 階段 × EMA（每筆淨 R，全年 (前 / 後) 筆數；扣 1 點；EMA 關閉放在最右欄）：第 2 節最穩的 3 種，加上不過濾')
    for _, r in k.head(3).iterrows():
        grid(G, r.hours, r.th, r.dist, r.R)
    grid(G, hours_list[-1], -1.0, np.inf, 2.0)
    G.to_pickle(os.path.join(ss.DATA_DIR, f'param_sweep_1m_{chart}.pkl'))


if __name__ == '__main__':
    main()
