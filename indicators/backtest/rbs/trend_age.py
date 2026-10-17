"""Trend age: what the 4-hour filter removes, and raw signals once the trend leg is old (NQ 2 minutes).

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/trend_age.py

Trend age = time since the latest Trend Judge trend run began (UP / 強UP or DOWN / 強Down with the 一般 threshold
10), counted in chart bars (trading time; 30 bars = 1 hour). It keeps counting through MIX and resets when a new
trend run starts in either direction. The grace version ignores MIX gaps of up to 30 minutes in the same direction.
For a filtered alert (Trend Judge already on its side) the strict age equals the bars since that run began.
Prints
  1. the filtered alerts (Remi Superb defaults) by trend age; what the 4-hour filter removes from the
     one-at-a-time sequence: winners / losers, R, both halves
  2. raw signals of the original indicator (no filter) by trend age and by the Trend Judge state at the signal,
     1R / 1.5R / 2R / 3R
  3. combined: filtered alerts (3R) while the trend is young, raw signals once it is older than T hours,
     one position at a time across both
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import th_sweep as tw
import ma_position as mp
import streak_study as st

TH = 10.0
TARGETS = (1.0, 1.5, 2.0, 3.0)
BPH = 30                                          # 2-minute bars per hour
BUCKETS = [0, 1, 2, 3, 4, 6, 8, 12, 24, 10 ** 6]


def leg_start(d, grace=0):
    """Trend Judge state (TH) and, per bar, the bar where the latest trend run began."""
    n = len(d)
    state = np.where(np.isnan(d), 0, np.where(d > TH, 1, np.where(d < -TH, -1, 0)))
    start = np.full(n, -1); cur = -1; lastdir = 0; lasttrend = -10 ** 9
    for j in range(n):
        sj = state[j]
        if sj != 0:
            prev = state[j - 1] if j else 0
            if sj != prev and not (sj == lastdir and j - lasttrend - 1 <= grace):
                cur = j
            lastdir = sj; lasttrend = j
        start[j] = cur
    return state, start


def net(y, R):
    return y[f'r{R:g}'].values - ss.COST / y.risk.values


def bucket_label(h):
    return pd.cut(h, BUCKETS, right=False, labels=[f'{a}–{b} 小時' if b < 10 ** 6 else f'{a} 小時以上' for a, b in zip(BUCKETS[:-1], BUCKETS[1:])])


def part1(b):
    print('\n######## 1. 過濾快訊依趨勢時間（訊號各自獨立）')
    for lab, y in b.groupby(bucket_label(b.age_h), observed=True):
        a = y.date.values < ss.SPLIT; n3 = net(y, 3.0); n2 = net(y, 2.0)
        print(f'  {str(lab):<12} {len(y):4d} 筆  3R 勝率 {100 * (y.r3 > 0).mean():4.1f}% 每筆 {n3.mean():+.3f}（前 {n3[a].mean():+.3f} 後 {n3[~a].mean():+.3f}）'
              f'  2R 勝率 {100 * (y.r2 > 0).mean():4.1f}% 每筆 {n2.mean():+.3f}')
    print('\n  4 小時濾網從原本的交易序列拿掉了什麼（一次一筆）')
    for R in (3.0, 2.0):
        t = st.seq_trades(b, R)
        print(f'\n  {R:g}R 原本：{st.summary(t)}')
        for nm, m in (('保留（≤ 4 小時）', t.age_h <= 4), ('拿掉（> 4 小時）', t.age_h > 4)):
            y = t[m]; w = y.win.values; a = y.date.values < ss.SPLIT; full = (y[f'r{R:g}'].values >= R).sum()
            print(f'    {nm:<12} {len(y):4d} 筆：賺 {w.sum():3d} 筆（{y.net[w].sum():+6.1f}R，其中打到 {R:g}R 目標 {full} 筆）'
                  f'  虧 {(~w).sum():3d} 筆（{y.net[~w].sum():+6.1f}R）  勝率 {100 * w.mean():4.1f}%  合計 {y.net.sum():+6.1f}R'
                  f'（前 {y.net[a].sum():+6.1f} 後 {y.net[~a].sum():+6.1f}）')
        print(f'    只做 ≤ 4 小時（重新排序列）：{st.summary(st.seq_trades(b[b.age_h <= 4], R))}')


def part2(raw, ages):
    print('\n######## 2. 原始指標（不過濾）的訊號，依趨勢時間')
    for gname, age_col in ages:
        print(f'\n  趨勢時間定義：{gname}')
        for vname, v in (('完全不過濾', raw.side != 0), ('只加停損 ≥ 1 ATR', raw.risk_atr >= 1.0)):
            y0 = raw[v]
            print(f'   {vname}（{len(y0)} 個訊號）')
            for lab, y in y0.groupby(bucket_label(y0[age_col]), observed=True):
                a = y.date.values < ss.SPLIT
                cells = '  '.join(f'{R:g}R {100 * (y[f"r{R:g}"] > 0).mean():4.1f}% {net(y, R).mean():+.3f}' for R in TARGETS)
                n1 = net(y, 1.0); n2 = net(y, 2.0)
                print(f'    {str(lab):<12} {len(y):4d} 筆  {cells}  | 1R 前 {n1[a].mean():+.3f} 後 {n1[~a].mean():+.3f}  2R 前 {n2[a].mean():+.3f} 後 {n2[~a].mean():+.3f}')
    print('\n  依訊號當下 Trend Judge 狀態（完全不過濾，嚴格定義的趨勢時間）')
    for sname, sm in (('順勢（TJ 跟訊號同方向）', raw['align'] == 1), ('逆勢（TJ 跟訊號反方向）', raw['align'] == -1), ('TJ 是 MIX', raw['align'] == 0)):
        for aname, am in (('趨勢 ≤ 4 小時', raw.age_h <= 4), ('趨勢 > 4 小時', raw.age_h > 4)):
            y = raw[sm & am]; a = y.date.values < ss.SPLIT
            if len(y) == 0: continue
            cells = '  '.join(f'{R:g}R {100 * (y[f"r{R:g}"] > 0).mean():4.1f}% {net(y, R).mean():+.3f}' for R in TARGETS)
            n1 = net(y, 1.0)
            print(f'    {sname:<16} {aname:<10} {len(y):4d} 筆  {cells}  | 1R 前 {n1[a].mean():+.3f} 後 {n1[~a].mean():+.3f}')


def seq_mixed(rows):
    """rows: DataFrame with i, r, x, risk, date, month, mode; one position at a time."""
    rows = rows.sort_values('i'); keep = []; busy = -1
    for q, (i, x) in enumerate(zip(rows.i.values, rows.x.values)):
        if i >= busy: keep.append(q); busy = x
    t = rows.iloc[keep].copy()
    t['net'] = t.r.values - ss.COST / t.risk.values; t['win'] = t.net.values > 0
    return t


def part3(b, raw):
    print('\n######## 3. 組合：趨勢 ≤ T 小時做過濾快訊（3R），> T 小時改做原始訊號（一次一筆）')
    base = st.seq_trades(b, 3.0); print(f'  只做過濾快訊（全部）        {st.summary(base)}')
    for T in (3, 4, 6, 8):
        fl = b[b.age_h <= T].assign(r=lambda y: y.r3, x=lambda y: y.x3, mode='趨勢')
        t_fl = seq_mixed(fl[['i', 'r', 'x', 'risk', 'date', 'month', 'mode']])
        print(f'\n  T = {T} 小時；只做過濾快訊 ≤ T        {st.summary(t_fl)}')
        for vname, v in (('原始', raw.side != 0), ('原始 + 停損 ≥ 1 ATR', raw.risk_atr >= 1.0)):
            for Rr in (1.0, 1.5, 2.0):
                rg = raw[v & (raw.age_h > T)].assign(r=lambda y: y[f'r{Rr:g}'], x=lambda y: y[f'x{Rr:g}'], mode='盤整')
                cols = ['i', 'r', 'x', 'risk', 'date', 'month', 'mode']
                t_rg = seq_mixed(rg[cols]); t = seq_mixed(pd.concat([fl[cols], rg[cols]]))
                part = '  '.join(f'{m} {(t["mode"] == m).sum()} 筆 {t.net[t["mode"] == m].sum():+.1f}R' for m in ('趨勢', '盤整'))
                print(f'    + {vname} {Rr:g}R：單獨 {st.summary(t_rg)}')
                print(f'      合起來 {st.summary(t)}  （{part}）')


def main():
    s = tw.build()
    df = rbs.prepared('NQ', tw.TF)
    s = pd.concat([s, mp.features(s, df), st.context(df, s)], axis=1)
    d = df.tj_diff.values
    state, start = leg_start(d, 0)
    _, start_g = leg_start(d, 15)
    i = s.i.values
    s['age_h'] = np.where(start[i] >= 0, (i - start[i] + 1) / BPH, np.nan)
    s['age_g'] = np.where(start_g[i] >= 0, (i - start_g[i] + 1) / BPH, np.nan)
    s['align'] = state[i] * s.side.values
    raw = s.dropna(subset=['age_h']).sort_values('i')
    b = raw[(raw.side == raw.h1) & (raw.risk_atr >= 1.0) & ~ss.EVT(raw) & (raw.spread > TH) & (raw.tjSlow < 3)].copy()
    print(f'NQ 2 分 K {s.date.min()} .. {s.date.max()}：原始訊號 {len(raw)} 個，過濾快訊 {len(b)} 個（門檻 {TH:g}）')
    print(f'檢查：過濾快訊的趨勢時間 = 這段趨勢已持續的根數 → {np.allclose(b.age_h * BPH, b.since)}')
    part1(b)
    part2(raw, (('嚴格（MIX 就重新算）', 'age_h'), ('寬限 30 分鐘內的 MIX', 'age_g')))
    part3(b, raw)


if __name__ == '__main__':
    main()
