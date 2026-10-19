"""Trend-continuation entries for strong Trend Judge trends (NQ 2 minutes, the Databento year), alone and added to
Remi Superb v3, plus what they would have done on Friday 2026-10-16 (ES, since the NQ file ends on the 14th).

  cd indicators/backtest
  python3 -I rbs/trend_follow.py

Trend = Trend Judge state on the 2-minute chart: 強 (|spread| > 35, ES 8) or 有趨勢 (> 10, ES 4); a sell needs DOWN.
  回檔碰快線   a bar reaches the 5-second EMA1130 (Trend Judge fast line) from the trend side and closes back on the
               trend side of it, after at least 5 bars that stayed off the line
  跌破前低     the close breaks the lowest low of the previous 20 bars (a buy: the highest high), and the bar before
               had not
Both: entry at the close, stop at the two-bar extreme (stop >= 1 ATR, as the filtered alerts, unless stated), last
complete 1-hour close on the trade's side of its EMA20, the New York event windows avoided; fixed R target, 60-bar
time exit, 1 point cost (ES 0.5). Each signal on its own for win rates; one position at a time for the year.
v3 + new entries: Remi Superb v3 on NQ 2m (trend signals 0-180 minutes + MIX breakout, 3R) with the new entries
taken whenever no position is open.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import market_matrix as mm

TARGETS = (1.0, 2.0, 3.0)


def frame(key, th, st):
    one = mm.load_market(key, [])
    tdm = mm.minute_trend(one)
    H = mm.hourly(one, False)
    df = mm.chart(one, tdm, 2, th, st)
    df['emaF'] = tdm['emaF'].reindex(pd.DatetimeIndex(df.last_min)).values
    nxt, atr = ss.bar_context(df, 2)
    t2 = df.datetime + pd.Timedelta(minutes=2)
    h1 = pd.merge_asof(pd.DataFrame({'t': t2}), H, on='t', direction='backward').h1.values
    e = t2.dt.tz_convert(ss.NY); me = (e.dt.hour * 60 + e.dt.minute).values; wd = e.dt.weekday.values
    fomc = np.isin(e.dt.date.astype(str).values, list(ss.FOMC))
    evt = (((wd < 5) & (((me >= 508) & (me < 540)) | ((me >= 598) & (me < 615)))) | (fomc & (me >= 838) & (me < 900))
           | ((me >= 570) & (me < 600)) | ((me >= 945) & (me < 975)) | ((me >= 1005) & (me < 1020)) | ((me >= 1080) & (me < 1110)))
    date = e.dt.date.astype(str).values
    return one, tdm, H, df, nxt, atr, h1, evt, date


def entries(df, nxt, atr, h1, evt, date, kind, strong, th, st, need_risk=True, look=20, away=5):
    h, l, c = df.high.values, df.low.values, df.close.values
    f = df.emaF.values; d = df.tj_diff.values; n = len(c)
    lim = st if strong else th
    down = d < -lim; up = d > lim
    rows = []
    if kind == '回檔碰快線':
        below = h < f; above = l > f                       # bar stayed off the fast line on the trend side
        rb = pd.Series(below.astype(int)).rolling(away).sum().shift(1).values == away
        ra = pd.Series(above.astype(int)).rolling(away).sum().shift(1).values == away
        sell = down & rb & (h >= f) & (c < f)
        buy = up & ra & (l <= f) & (c > f)
    else:
        ll = pd.Series(l).rolling(look).min().shift(1).values; hh = pd.Series(h).rolling(look).max().shift(1).values
        sell = down & (c < ll) & ~(np.r_[False, c[:-1] < ll[:-1]])
        buy = up & (c > hh) & ~(np.r_[False, c[:-1] > hh[:-1]])
    trad = df.tradable.values
    for i in np.where(sell | buy)[0]:
        if i < 30 or not trad[i] or evt[i]: continue
        k = 1 if buy[i] else -1
        if h1[i] != k: continue
        stop = min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])
        risk = (c[i] - stop) * k
        if not risk > 0: continue
        if need_risk and risk < atr[i - 1]: continue
        end = min(i + 60, nxt[i])
        if end <= i: continue
        rows.append([i, k, risk, date[i], date[i][:7], stop] + ss.outcome(h, l, c, i, k, stop, end))
    cols = ['i', 'side', 'risk', 'date', 'month', 'stop']
    for R in ss.TARGETS: cols += [f'r{R:g}', f'x{R:g}']
    return pd.DataFrame(rows, columns=cols)


def ind_line(y, cost):
    if len(y) == 0: return '   0'
    d = sorted(y.date.unique()); a = y.date.values < d[len(d) // 2]; out = []
    for R in TARGETS:
        r = y[f'r{R:g}'].values; nn = r - cost / y.risk.values
        out.append(f'{R:g}R {100 * (r > 0).mean():4.1f}% {nn.mean():+.3f}（{nn[a].mean():+.2f}/{nn[~a].mean():+.2f}）')
    return f'{len(y):5d} 筆  ' + '  '.join(out)


def seq_line(t, years):
    if len(t) == 0: return '   0'
    n = t.net.values; eq = np.cumsum(n); dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
    mo = pd.Series(n).groupby(t.date.str[:7].values).sum()
    d = sorted(t.date.unique()); a = t.date.values < d[len(d) // 2]
    return (f'{len(t) / years:5.0f} 筆/年  勝率 {100 * (t.R > 0).mean():4.1f}%  每筆 {n.mean():+.3f}R（前 {n[a].mean():+.3f} 後 {n[~a].mean():+.3f}）'
            f'  每年 {n.sum() / years:+6.1f}R  回撤 {dd:5.1f}R  賺錢月份 {(mo > 0).sum()}/{len(mo)}')


def simulate(df, close_entries, mix, R, cost, halt):
    """One position at a time. close_entries: {bar: (side, stop, kind)} entered at the close; mix: {bar: (side, px, mid)}."""
    h, l, c = df.high.values, df.low.values, df.close.values
    holeb = np.r_[False, (df.datetime.diff() > pd.Timedelta(minutes=30)).values[1:]]
    date = df.datetime.dt.tz_convert(ss.NY).dt.date.astype(str).values
    trad = df.tradable.values
    trades = []; pos = 0
    for j in range(len(c)):
        if pos != 0 and j > vb:
            hs = (l[j] <= vs) if pos == 1 else (h[j] >= vs)
            ht = (h[j] >= vt) if pos == 1 else (l[j] <= vt)
            if hs or ht or j - vb >= 60 or halt[j] or holeb[j]:
                px = vs if hs else vt if ht else (c[j - 1] if holeb[j] else c[j])
                trades.append((kind, pos, ve, px, abs(ve - vs), d0)); pos = 0
        if not trad[j]: continue
        if pos == 0 and j in mix and not halt[j]:
            k, px, mid = mix[j]
            pos, ve, vs, vt, vb, kind, d0 = k, px, mid, px + R * (px - mid), j, 'MIX', date[j]
            if (pos == 1 and l[j] <= vs) or (pos == -1 and h[j] >= vs):
                trades.append((kind, pos, ve, vs, abs(ve - vs), d0)); pos = 0
        if pos == 0 and j in close_entries and not halt[j]:
            k, stop, kd = close_entries[j]
            pos, ve, vs, vt, vb, kind, d0 = k, c[j], stop, c[j] + R * (c[j] - stop), j, kd, date[j]
    t = pd.DataFrame(trades, columns=['kind', 'side', 'entry', 'exit', 'risk', 'date'])
    t['R'] = (t.exit - t.entry) * t.side / t.risk
    t['net'] = t.R - cost / t.risk
    return t


def mix_dict(df, th, cost):
    B, boxes, _ = mm.mix_breaks(df, 2, th, cost)
    h, l, o, hole, evt = B['h'], B['l'], B['o'], B['hole'], B['evt']; n = len(h); out = {}
    for s0, fm, top, bot in boxes:
        Hh = top - bot
        if Hh <= 0: continue
        bu, bd, mid = top + 0.1 * Hh, bot - 0.1 * Hh, (top + bot) / 2
        for j in range(fm + 1, min(fm + 30, n - 1) + 1):
            if hole[j]: break
            up, dn = h[j] >= bu, l[j] <= bd
            if not (up or dn): continue
            if (up and dn) or evt[j]: break
            k = 1 if up else -1
            out[j] = (k, max(o[j], bu) if k == 1 else min(o[j], bd), mid)
            break
    rbs._cache.pop(('NQ', 2), None)
    return out


def main():
    cost, th, st = 1.0, 10.0, 35.0
    one, tdm, H, df, nxt, atr, h1, evt, date = frame('nq', th, st)
    years = (one.index[-1] - one.index[0]).days / 365.25
    h, l = df.high.values, df.low.values
    et = (df.datetime + pd.Timedelta(minutes=2)).dt.tz_convert(ss.NY)
    halt = ((et.dt.hour * 60 + et.dt.minute) == 1020).values
    print(f'NQ 2 分 K：{one.index[0]:%Y-%m-%d} .. {one.index[-1]:%Y-%m-%d}，每筆扣 1 點')
    print('\n######## 1. 新進場各自獨立（勝率 % / 每筆淨 R（前 / 後））')
    variants = {}
    for kind in ('回檔碰快線', '跌破前低'):
        for strong in (True, False):
            for need_risk in (True, False):
                nm = f'{kind}，{"強趨勢" if strong else "有趨勢"}{"" if need_risk else "，不限停損"}'
                y = entries(df, nxt, atr, h1, evt, date, kind, strong, th, st, need_risk)
                variants[nm] = y
                print(f'   {nm:<20} ' + ind_line(y, cost))
    print('\n######## 2. 單做（一次一筆）')
    for nm, y in variants.items():
        if '不限停損' in nm: continue
        for R in (2.0, 3.0):
            ce = {int(i): (int(k), s, '新') for i, k, s in zip(y.i, y.side, y.stop)}
            print(f'   {nm:<14} {R:g}R  ' + seq_line(simulate(df, ce, {}, R, cost, halt), years))

    print('\n######## 3. 加進 v3（NQ 2m：趨勢 0–180 分 + MIX 突破，3R），一次一筆')
    s = mm.trend_signals(df, H, 2)
    F = s[mm.filt(s, th) & (s.tm >= 0) & (s.tm < 180)]
    base = {int(i): (int(k), (min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])), '趨勢') for i, k in zip(F.i, F.side)}
    mix = mix_dict(df, th, cost)
    for R in (3.0,):
        t0 = simulate(df, base, mix, R, cost, halt)
        print(f'   v3 原本                  {R:g}R  ' + seq_line(t0, years))
        for nm, y in variants.items():
            if '不限停損' in nm: continue
            ce = dict(base)
            for i, k, sp in zip(y.i, y.side, y.stop):
                ce.setdefault(int(i), (int(k), sp, '新'))
            t = simulate(df, ce, mix, R, cost, halt)
            nn = t[t.kind == '新']
            print(f'   + {nm:<20} {R:g}R  ' + seq_line(t, years) + f'  | 新進場 {len(nn) / years:.0f} 筆/年 {nn.net.mean():+.3f}R')

    print('\n######## 3b. 跌破前低（強趨勢）細看：依趨勢已持續、依時段（各自獨立）')
    y = variants['跌破前低，強趨勢'].copy()
    y['tm'] = df.tmin.values[y.i.values]
    em = ((df.datetime + pd.Timedelta(minutes=2)).dt.tz_convert(ss.NY))
    m_ = (em.dt.hour * 60 + em.dt.minute).values[y.i.values]
    for nm, g in (('趨勢已持續', pd.cut(y.tm, [0, 60, 120, 180, 240, 360, 10 ** 6], right=False,
                                         labels=['0–60', '60–120', '120–180', '180–240', '240–360', '360 以上'])),
                  ('時段', pd.Series(np.select([(m_ >= 570) & (m_ < 960), (m_ >= 1200) | (m_ < 180), m_ < 570], ['美股盤', '亞洲盤', '歐洲盤'], '收盤後'), index=y.index))):
        for lab, z in y.groupby(g, observed=True):
            print(f'   {nm} {str(lab):<8} ' + ind_line(z, cost))

    print('\n######## 4. 週五 2026-10-16 的 ES（NQ 資料只到 10/14）')
    one_e, tdm_e, H_e, de, nxe, atre, h1e, evte, datee = frame('es', 4.0, 8.0)
    ete = (de.datetime + pd.Timedelta(minutes=2)).dt.tz_convert(ss.NY)
    for kind in ('回檔碰快線', '跌破前低'):
        for strong in (True, False):
            y = entries(de, nxe, atre, h1e, evte, datee, kind, strong, 4.0, 8.0)
            yf = y[y.date == '2026-10-16']
            print(f'   {kind}，{"強趨勢" if strong else "有趨勢"}：{len(yf)} 筆')
            for _, r in yf.iterrows():
                t = ete.iloc[int(r.i)]
                print(f'      {t:%H:%M} ET（台北 {(t + pd.Timedelta(hours=12)):%H:%M}）{"買" if r.side == 1 else "賣"}  停損 {r.risk:.2f} 點  1R {r.r1:+.1f}  2R {r.r2:+.1f}  3R {r.r3:+.1f}')


if __name__ == '__main__':
    main()
