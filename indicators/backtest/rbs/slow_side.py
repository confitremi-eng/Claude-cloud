"""Remi's 15 s rule (2026-10-21): with-trend signals on the trend side of the 15 s EMA1130 are taken; a signal already past
the 15 s line is taken only if, earlier in the same trend, a signal inside the line was stopped out.

  cd indicators/backtest
  python3 -I rbs/slow_side.py

Inside = close on the trade's side of the 15 s line (buy above, sell below); past = the other side (v3 already caps it at
3 ATR). Trend = a run of Trend Judge on one side: 'run' = continuous (any MIX bar starts a new one), 'leg' = since the last
bar on the opposite side (MIX in between does not reset). v3 as now (2m trend 0-400, 5m 0-180 + daily SMA5, stop >= 0.95
ATR, FOMC days off, junk time off, one at a time, MIX unchanged, no re-entry). Per year: win rate / R; trend trades split.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import daily_sma5 as d5


def runs(tj, mode):
    d = np.sign(tj).astype(int); rid = np.zeros(len(d), int); cur = 0; last = 0
    for j in range(len(d)):
        if mode == 'run':
            if d[j] == 0 or j == 0 or d[j] != d[j - 1]: cur += 1
        else:
            if d[j] != 0 and d[j] != last: cur += 1
            if d[j] != 0: last = d[j]
        rid[j] = cur
    return rid


def sim(C, trend, mix, R, inside, rid, rule):
    df = C.df; h, l, c = C.h, C.l, C.c
    holeb = np.r_[False, (df.datetime.diff() > pd.Timedelta(minutes=30)).values[1:]]
    trad = df.tradable.values
    tr = {int(i): int(k) for i, k in zip(trend.i, trend.side)}
    mx = {j: (k, px, st) for j, k, px, st, _ in mix}
    out = []; pos = 0; stopped = set(); skipped = 0
    for j in range(len(c)):
        if pos != 0 and j > vb:
            hs = (l[j] <= vs) if pos == 1 else (h[j] >= vs)
            ht = (h[j] >= vt) if pos == 1 else (l[j] <= vt)
            if hs or ht or j - vb >= 60 or C.halt[j] or holeb[j]:
                px = vs if hs else vt if ht else (c[j - 1] if holeb[j] else c[j])
                risk = abs(ve - vs); out.append((d0, (px - ve) * pos / risk - oc.COST / risk, kind, ins))
                if hs and kind == '趨勢' and ins: stopped.add((rid[vb], pos))
                pos = 0
        if not trad[j] or C.halt[j] or C.late[j]: continue
        if pos == 0 and j in mx:
            k, px, st = mx[j]
            pos, ve, vs, vt, vb, d0, kind, ins = k, px, st, px + R * (px - st), j, C.date[j], 'MIX', None
            if (pos == 1 and l[j] <= vs) or (pos == -1 and h[j] >= vs):
                out.append((d0, -1.0 - oc.COST / abs(px - st), kind, ins)); pos = 0
        if pos == 0 and j in tr:
            k = tr[j]
            if rule and not inside[j] and (rid[j], k) not in stopped:
                skipped += 1; continue
            st = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j])
            pos, ve, vs, vt, vb, d0, kind, ins = k, c[j], st, c[j] + R * (c[j] - st), j, C.date[j], '趨勢', bool(inside[j])
    t = pd.DataFrame(out, columns=['date', 'net', 'kind', 'inside']); t['R'] = t.net
    return t, skipped


def main():
    one = oc.load(); M = oc.Market(one); D = d5.daily(one)
    for tf, R, cap in ((2, 3.0, 400), (5, 2.0, 180)):
        C = M.ctx(tf); df = C.df; th = df.thr.values; c = df.close.values
        dt = pd.DatetimeIndex(df.datetime); dt = dt.tz_localize('UTC') if dt.tz is None else dt
        ny = (dt + pd.Timedelta(minutes=tf)).tz_convert(ss.NY)
        m = np.asarray(ny.hour * 60 + ny.minute); junk = (m >= 720) & (m <= 785)
        sma = D.sma.reindex((dt.tz_convert(ss.NY) + pd.Timedelta(hours=6)).normalize()).values
        S = M.tdm['emaS'].reindex(pd.DatetimeIndex(df.last_min)).values
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < cap) & ~s.date.isin(ss.FOMC) & ~junk[s.i]]
        if tf == 5: T = T[np.sign(c[T.i.values] - sma[T.i.values]) == T.side.values]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not junk[x[0]] and (tf != 5 or (x[2] - sma[x[0]]) * x[1] > 0)]
        side = np.zeros(len(c), int); side[T.i.values] = T.side.values
        inside = (c - S) * side > 0
        print(f'\nNQ {tf}m（{R:g}R）每年：勝率 / 合計 R')
        print(f'   {"":<34}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in oc.YEARS))
        for lab, mode, rule in (('v3 現在', 'run', False), ('15s 規則（趨勢 = 連續同向）', 'run', True), ('15s 規則（趨勢 = 到反向為止）', 'leg', True)):
            rid = runs(df.tj_dir.values, mode)
            t, sk = sim(C, T, mix, R, inside, rid, rule)
            print(f'   {lab:<34}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+5.0f}R' for z in (t[(t.date >= a) & (t.date <= b)] for nm, a, b in oc.YEARS)) + (f'   擋掉 {sk / 5:.0f} 個 / 年' if rule else ''))
            if not rule:
                y = t[(t.kind == '趨勢') & (t.date > oc.YEARS[3][2])]; o = t[(t.kind == '趨勢') & (t.date <= oc.YEARS[3][2])]
                for lab2, z, zo in (('15s 內', y[y.inside == True], o[o.inside == True]), ('超過 15s', y[y.inside == False], o[o.inside == False])):
                    print(f'      v3 趨勢單 {lab2}：v3 那年 {len(z)} 筆 勝 {100 * (z.R > 0).mean():.0f}% 每筆 {z.net.mean():+.2f}R；前 4 年 勝 {100 * (zo.R > 0).mean():.0f}% 每筆 {zo.net.mean():+.2f}R')


if __name__ == '__main__':
    main()
