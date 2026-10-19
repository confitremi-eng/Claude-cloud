"""NQ 1-minute trades: does a 2-minute signal at the same time help, what do the 1-minute-only winners look like,
and are signals better early in a Trend Judge trend (1 / 2 / 3 / 5 minutes)?

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/one_minute.py

Signals = Remi Superb filtered alerts on each chart with its defaults: Trend Judge 有趨勢 (spread > 10 in the
trade's direction), last complete 1-hour close on the trade's side of its EMA20, stop >= 1 ATR, close - 15-second
EMA1130 <= 3 ATR, event windows avoided. Raw signal = the original indicator's signal without the filter.
Outcome of each chart's own trade (setup_study.py): entry at the signal close, two-bar stop, fixed R, 60-bar
time exit, 1 point cost. Signals are counted on their own (no one-at-a-time), so groups can be compared.
前 / 後 = before / after 2026-06-01.
  1. 2-minute filtered alerts with / without a 1-minute filtered alert in the same direction inside the same
     2-minute bar; 1-minute filtered alerts by what the 2-minute chart shows: a filtered alert in the same
     2-minute bar, only a raw signal there, a filtered alert in the 2-minute bar before or after, nothing
  2. 1-minute filtered alerts with no 2-minute signal (raw or filtered) in the same or the neighbouring 2-minute
     bars: winners against losers (2R), and net R by quintile of what is known at the entry
  3. filtered alerts by the age of the Trend Judge trend run (minutes since the 1-minute Trend Judge state
     turned UP / DOWN, a MIX minute or a turn ends the run) and by what came before the run (MIX or the
     opposite trend), on 1 / 2 / 3 / 5 minutes
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import th_sweep as tw
import ma_position as mp

TH = 10.0
TFS = (1, 2, 3, 5)
TARGETS = (1.0, 1.5, 2.0, 3.0)
AGE_BINS = [0, 15, 30, 60, 120, 240, 10 ** 6]
AGE_LABELS = ['0–15 分', '15–30 分', '30–60 分', '1–2 小時', '2–4 小時', '4 小時以上']
GRACE = 10                                      # MIX minutes inside a trend leg that do not end it
AFTER = ('MIX ≥ 30 分之後', 'MIX < 30 分、方向反轉', 'MIX < 30 分、同方向再起')


def signals(tf):
    tw.TF = tf
    tw.CACHE = os.path.join(ss.DATA_DIR, 'th_sweep_2m.pkl' if tf == 2 else f'NQ_1m_databento_th_sweep_{tf}m.pkl')
    s = tw.build()
    df = rbs.prepared('NQ', tf)
    s = pd.concat([s, mp.features(s, df)], axis=1)
    lm = pd.DatetimeIndex(df.last_min.values[s.i]).tz_localize('UTC')
    s['tlast'] = lm                                            # the signal bar's last minute
    s['tclose'] = lm + pd.Timedelta(minutes=1)
    s['filt'] = (s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.tjSlow < 3) & (s.spread > TH)
    s['tf'] = tf
    return s.sort_values('i').reset_index(drop=True)


def trend_runs(grace=GRACE):
    """Per minute: Trend Judge state (threshold TH) and the current trend leg: same-direction minutes with MIX gaps
    of up to `grace` minutes merged. For each leg: start minute, the MIX minutes right before it, and the direction
    of the leg before (opposite = a turn, same = the trend resumes)."""
    d = rbs._cache[('tdm', 'NQ')]['diff']
    v = d.values; n = len(v)
    st = np.where(np.isnan(v), 0, np.where(v > TH, 1, np.where(v < -TH, -1, 0)))
    start = np.full(n, -1); mixlen = np.zeros(n, int); prevdir = np.zeros(n, int)
    legdir = 0; legstart = -1; zeros = 0; lastleg = 0; ml = 0; pdir = 0
    for j in range(n):
        s = st[j]
        if s == 0:
            zeros += 1
            if legdir != 0 and zeros > grace:                  # the leg has ended
                lastleg = legdir; legdir = 0; legstart = -1
        else:
            if s != legdir:                                     # a new leg starts
                if legdir != 0: lastleg = legdir               # a turn inside the grace time
                pdir = lastleg; ml = zeros; legdir = s; legstart = j
            zeros = 0
        start[j] = legstart if s != 0 else -1
        mixlen[j] = ml; prevdir[j] = pdir
    return pd.DatetimeIndex(d.index), st, start, mixlen, prevdir


def add_age(s, runs):
    idx, st, start, mixlen, prevdir = runs
    j = idx.get_indexer(s.tlast); jj = np.maximum(j, 0)
    ok = (j >= 0) & (st[jj] == s.side.values) & (start[jj] >= 0)
    s['age'] = np.where(ok, jj - start[jj], np.nan)
    s['mixlen'] = np.where(ok, mixlen[jj], np.nan)
    turn = prevdir[jj] == -s.side.values
    s['after'] = np.where(~ok, '', np.where(mixlen[jj] >= 30, 'MIX ≥ 30 分之後',
                                            np.where(turn, 'MIX < 30 分、方向反轉', 'MIX < 30 分、同方向再起')))
    return s


def net(y, R):
    return y[f'r{R:g}'].values - ss.COST / y.risk.values


def row(y, Rs=TARGETS):
    if len(y) == 0: return '   0 筆'
    a = y.date.values < ss.SPLIT
    parts = []
    for R in Rs:
        nn = net(y, R)
        parts.append(f'{R:g}R {100 * (y[f"r{R:g}"] > 0).mean():4.1f}% {nn.mean():+.3f}（{nn[a].mean():+.2f}/{nn[~a].mean():+.2f}）')
    return f'{len(y):5d} 筆  ' + '  '.join(parts)


def sorted_times(y):
    return {sd: np.sort(y.tclose.values[y.side.values == sd].astype('datetime64[ns]').astype(np.int64)) for sd in (1, -1)}


def any_in(times, lo, hi):
    """Earliest time in (lo, hi] or None."""
    k = np.searchsorted(times, lo, 'right')
    return times[k] if k < len(times) and times[k] <= hi else None


def wait_trades(M, y, df1, t_entry):
    """1-minute trades of signals y entered later (at t_entry, ns) with the 1-minute signal's own stop."""
    h, l = df1.high.values, df1.low.values
    rows = []
    for (i, k, d), te in zip(zip(y.i.values, y.side.values, y.date.values), t_entry):
        je = M.closed_by(np.datetime64(int(te), 'ns'))
        if je < 0 or M.T[je].astype(np.int64) != te - 60 * 10 ** 9: continue
        stop = min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])
        P = M.C[je]; risk = (P - stop) * k
        if not risk > 0: continue
        last = min(je + 60, M.nxt[je]); r = {}
        for R in TARGETS:
            px, _ = M.run(k, stop, P + k * R * risk, je + 1, last) if je + 1 <= last else (P, je)
            r[f'r{R:g}'] = (px - P) * k / risk
        rows.append(dict(risk=risk, date=d, **r))
    return pd.DataFrame(rows)


def part1(S, M):
    print('\n######## 1. 1 分 K 跟 2 分 K 同時出訊號（勝率 % / 每筆淨 R（前 / 後））')
    s1, s2 = S[1], S[2]
    df1 = rbs.prepared('NQ', 1)
    F2, R2 = sorted_times(s2[s2.filt]), sorted_times(s2)
    W, AHEAD = 4 * 60 * 10 ** 9, 3 * 60 * 10 ** 9
    t1 = s1.tclose.values.astype('datetime64[ns]').astype(np.int64)
    kf = np.array([any_in(F2[sd], t - W - 1, t) is not None for t, sd in zip(t1, s1.side.values)])
    kr = np.array([any_in(R2[sd], t - W - 1, t) is not None for t, sd in zip(t1, s1.side.values)])
    fut = np.array([any_in(F2[sd], t, t + AHEAD) or 0 for t, sd in zip(t1, s1.side.values)])
    s1['g2'] = np.select([kf, kr, fut > 0], ['A', 'B', 'C1'], 'C2')
    s1['t2fut'] = fut
    f1 = s1[s1.filt]
    print('\n  ## 1 分 K 過濾訊號（1 分 K 收盤進場、1 分 K 的停損），依進場當下 2 分 K 已經出現的訊號')
    print('   A 2m 已有同向過濾訊號（4 分鐘內）  ' + row(f1[f1.g2 == 'A']))
    print('   B 2m 只有同向原始訊號（4 分鐘內）  ' + row(f1[f1.g2 == 'B']))
    print('   C 2m 還沒有訊號               ' + row(f1[f1.g2.isin(['C1', 'C2'])]))
    print('     其中 C1 之後 3 分鐘內 2m 才出過濾訊號（事後才知道）  ' + row(f1[f1.g2 == 'C1']))
    print('     其中 C2 之後也沒有                           ' + row(f1[f1.g2 == 'C2']))
    print('   全部                         ' + row(f1))
    c1 = f1[f1.g2 == 'C1']
    print('\n  ## 實際做得到的「等 2 分 K 確認再進」：C1 在 2m 確認那一分鐘收盤進場，停損仍用 1 分 K 訊號的停損')
    print('   等 2m 確認（1m 停損）   ' + row(wait_trades(M, c1, df1, c1.t2fut.values)))
    print('   同一批，1m 收盤就進     ' + row(c1))
    print('   對照：2m 過濾訊號自己的交易，見下面')

    print('\n  ## 2 分 K 過濾訊號（2 分 K 自己的交易），依 2m 收盤時 1 分 K 已經出現的訊號（4 分鐘內）')
    F1, R1 = sorted_times(s1[s1.filt]), sorted_times(s1)
    f2 = s2[s2.filt]
    t2 = f2.tclose.values.astype('datetime64[ns]').astype(np.int64)
    k1f = np.array([any_in(F1[sd], t - W - 1, t) is not None for t, sd in zip(t2, f2.side.values)])
    k1r = np.array([any_in(R1[sd], t - W - 1, t) is not None for t, sd in zip(t2, f2.side.values)])
    print('   1m 已有同向過濾訊號   ' + row(f2[k1f]))
    print('   1m 只有同向原始訊號   ' + row(f2[~k1f & k1r]))
    print('   1m 沒有訊號         ' + row(f2[~k1f & ~k1r]))
    print('   全部 2m 過濾訊號     ' + row(f2))
    return s1


def part2(s1):
    print('\n######## 2. 進場當下 2 分 K 還沒有訊號的 1 分 K 過濾訊號（上面的 C）：贏的跟輸的差在哪（2R）')
    y = s1[s1.filt & s1.g2.isin(['C1', 'C2'])].copy()
    y['et'] = (y.tclose.dt.tz_convert(ss.NY).dt.hour * 60 + y.tclose.dt.tz_convert(ss.NY).dt.minute)
    y['n2'] = net(y, 2.0); win = y.r2 > 0
    feats = [('spread', 'Trend Judge 差值（點）'), ('age', '趨勢已持續（分）'), ('mixlen', '趨勢前的 MIX 長度（分）'),
             ('tjSlow', '離 15 秒 EMA1130（ATR）'), ('tjFast', '離 5 秒 EMA1130（ATR）'), ('ema20', '離 1m EMA20（ATR）'),
             ('ema50', '離 1m EMA50（ATR）'), ('risk_atr', '停損（ATR）'), ('risk', '停損（點）'), ('bar_atr', '訊號 K 長度（ATR）')]
    print(f'  {len(y)} 筆，2R 勝率 {100 * win.mean():.1f}%，每筆 {y.n2.mean():+.3f}R')
    print(f'  {"":<22}{"贏的中位數":>10}{"輸的中位數":>10}')
    for c, nm in feats:
        print(f'  {nm:<22}{y[c][win].median():>10.2f}{y[c][~win].median():>10.2f}')
    print('\n  依五分位（每筆淨 R，前 / 後）')
    a = y.date.values < ss.SPLIT
    for c, nm in feats:
        q = pd.qcut(y[c].rank(method='first'), 5, labels=False)
        cells = []
        for b in range(5):
            m = (q == b).values
            cells.append(f'{y[c][m].min():.1f}–{y[c][m].max():.1f}: {y.n2[m].mean():+.2f}({y.n2[m & a].mean():+.2f}/{y.n2[m & ~a].mean():+.2f})')
        print(f'  {nm:<20} ' + ' | '.join(cells))
    print('\n  依前面是 MIX 還是反轉、依時段（每筆淨 R）')
    for nm, g in (('前面', y.after), ('時段', pd.cut(y.et, [0, 180, 570, 960, 1200, 1440], right=False,
                                                     labels=['亞洲 00-03', '歐洲 03-09:30', '美股 09:30-16', '收盤後 16-20', '亞洲 20-24']))):
        for lab, z in y.groupby(g, observed=True):
            if len(z): print(f'   {nm} {str(lab):<14} {row(z, (2.0, 3.0))}')


def part3(S):
    print('\n######## 3. 趨勢剛開始的時候：過濾訊號依「趨勢已持續多久」（勝率 % / 每筆淨 R（前 / 後））')
    for tf in TFS:
        y = S[tf][S[tf].filt & S[tf].age.notna()]
        print(f'\n  ## {tf} 分 K（{len(y)} 筆，另有 {int((S[tf].filt & S[tf].age.isna()).sum())} 筆對不到趨勢時間）')
        lab = pd.cut(y.age, AGE_BINS, right=False, labels=AGE_LABELS)
        for l in AGE_LABELS:
            print(f'   {l:<8} ' + row(y[lab == l]))
        for aft in AFTER:
            print(f'   {aft}：')
            for l in AGE_LABELS:
                print(f'   {l:<8} ' + row(y[(lab == l) & (y.after == aft)]))


def part4(S):
    print('\n######## 4. 只做「趨勢已持續 30–120 分鐘」的過濾訊號：換 MIX 容許時間、一次一筆的一年結果')
    for grace in (5, 10, 20):
        runs = trend_runs(grace)
        print(f'\n  ## 中途 MIX ≤ {grace} 分鐘不算中斷')
        for tf in TFS:
            y = add_age(S[tf].copy(), runs)
            y = y[y.filt].sort_values('i')
            w = (y.age >= 30) & (y.age < 120)
            print(f'   {tf}m 30–120 分 ' + row(y[w]))
            print(f'   {tf}m 其他時間   ' + row(y[~w & y.age.notna()]))
            if grace == 10:
                for R in (2.0, 3.0):
                    for nm, z in (('全部', y), ('30–120 分', y[w])):
                        t = ss.seq(z, R); nn = net(t, R); a = t.date.values < ss.SPLIT
                        eq = np.cumsum(nn); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)) if len(eq) else 0
                        mo = pd.Series(nn).groupby(t.month.values).sum()
                        print(f'     一次一筆 {R:g}R {nm:<8} {len(t):4d} 筆  勝率 {100 * (t[f"r{R:g}"] > 0).mean():4.1f}%  每筆 {nn.mean():+.3f}R'
                              f'  一年 {nn.sum():+6.1f}R（前 {nn[a].sum():+5.1f} 後 {nn[~a].sum():+5.1f}）  回撤 {dd:4.1f}R  賺錢月份 {(mo > 0).sum()}/{len(mo)}')


def main():
    import nq_follow as nf
    S = {tf: signals(tf) for tf in TFS}
    M = nf.Minutes(rbs.load1('NQ'))
    runs = trend_runs()
    for tf in TFS:
        S[tf] = add_age(S[tf], runs)
    print('資料：' + '，'.join(f'{tf}m 原始 {len(S[tf])} / 過濾 {int(S[tf].filt.sum())}' for tf in TFS))
    s1 = part1(S, M)
    S[1] = s1
    part2(s1)
    part3(S)
    part4(S)


if __name__ == '__main__':
    main()
