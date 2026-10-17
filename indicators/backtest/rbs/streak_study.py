"""Losing streaks of the optimized Remi Superb setup on NQ 2 minutes (the Databento year).

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/streak_study.py

Setup (Remi Superb defaults after the 2026-10-17 optimisation): 有趨勢 with Trend Judge 一般 threshold 10,
1-hour EMA20 on the trade's side, stop >= 1 ATR, close - 15-second EMA1130 <= 3 ATR, data / open / close /
Globex windows avoided (Asia kept), one position at a time, 1 point cost, 3R (and 2R).
Prints
  1. losing streaks: length counts, the longest, what independent trades with the same win rate give
     (4,000 shuffles), a runs test, and the win rate after a win / after 1, 2, 3, 4+ losses
  2. market context at entry in quintiles over all qualifying signals (independent), both halves:
     Trend Judge (bars since the trend began, share of MIX in the last hour, state changes, spread slope,
     spread pullback from its peak, n-th signal of the trend), chop (efficiency ratio, choppiness index,
     ADX, 1-hour range in ATR), recent raw signals, slow-line slope, volatility, session
  3. trades inside long losing streaks vs the rest, and the longest streaks one by one
  4. filters and circuit breakers on the same trade sequence: both halves, longest streak, drawdown
  5. exits when Trend Judge turns (to MIX or to the other side) while in the trade
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import th_sweep as tw
import ma_position as mp
from remi_export import signals

TH = 10.0
RS = (3.0, 2.0)


def context(df, s):
    """Market context at each signal bar, from data up to that bar only."""
    h, l, c = df.high.values, df.low.values, df.close.values
    n = len(c)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    rma = lambda x: pd.Series(x).ewm(alpha=1 / 14, adjust=False).mean().values
    atr = rma(tr)
    roll = lambda x, m, f: getattr(pd.Series(x).rolling(m), f)().values
    F = {}
    absd = np.abs(np.r_[np.nan, np.diff(c)])
    for m in (10, 30):
        F[f'er{m}'] = np.abs(c - np.r_[np.full(m, np.nan), c[:-m]]) / roll(absd, m, 'sum')
    for m in (14, 30):
        F[f'chop{m}'] = 100 * np.log10(roll(tr, m, 'sum') / (roll(h, m, 'max') - roll(l, m, 'min'))) / np.log10(m)
    up = h - np.r_[np.nan, h[:-1]]; dn = np.r_[np.nan, l[:-1]] - l
    pdm = np.where((up > dn) & (up > 0), up, 0.0); ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pdi = 100 * rma(pdm) / atr; ndi = 100 * rma(ndm) / atr
    F['adx'] = rma(np.nan_to_num(100 * np.abs(pdi - ndi) / (pdi + ndi)))
    F['rng30'] = (roll(h, 30, 'max') - roll(l, 30, 'min')) / atr
    F['atr_rel'] = atr / pd.Series(atr).rolling(720).mean().values          # vs the last day (720 x 2m)
    d = df.tj_diff.values
    state = np.where(np.isnan(d), 0, np.where(d > TH, 1, np.where(d < -TH, -1, 0)))
    F['mixfrac30'] = roll((state == 0).astype(float), 30, 'mean')
    F['flips60'] = roll(np.r_[0, (np.diff(state) != 0).astype(float)], 60, 'sum')
    runU = np.zeros(n, int); runD = np.zeros(n, int); pkU = np.full(n, np.nan); pkD = np.full(n, np.nan)
    for j in range(n):
        if state[j] == 1:
            runU[j] = runU[j - 1] + 1 if j else 1
            pkU[j] = max(pkU[j - 1], d[j]) if j and runU[j - 1] else d[j]
        if state[j] == -1:
            runD[j] = runD[j - 1] + 1 if j else 1
            pkD[j] = min(pkD[j - 1], d[j]) if j and runD[j - 1] else d[j]
    B, S = signals(df)
    anysig = pd.Series(((B == 1) | (S == 1)).astype(float))
    i = s.i.values; k = s.side.values
    out = pd.DataFrame(index=s.index)
    for key in ('er10', 'er30', 'chop14', 'chop30', 'adx', 'rng30', 'atr_rel', 'mixfrac30', 'flips60'):
        out[key] = F[key][i]
    out['since'] = np.where(k == 1, runU[i], runD[i])                       # bars since the trend began
    out['run_start'] = i - out.since.values + 1
    out['pullback'] = np.where(k == 1, pkU[i] - d[i], d[i] - pkD[i])         # spread below its peak (points)
    out['slope5'] = (d[i] - d[np.maximum(i - 5, 0)]) * k                     # spread change over 5 bars
    out['sig30'] = anysig.rolling(30).sum().shift(1).values[i]               # raw signals in the last hour
    opp = pd.Series((S == 1).astype(float)).rolling(30).sum().shift(1).values, \
          pd.Series((B == 1).astype(float)).rolling(30).sum().shift(1).values
    out['opp30'] = np.where(k == 1, opp[0][i], opp[1][i])
    emaS = df.emaS.values
    out['slowslope'] = (emaS[i] - emaS[np.maximum(i - 30, 0)]) * k / atr[i]
    m = s.et_min.values
    out['sess'] = np.select([(m >= 1200) | (m < 180), m < 570, m < 720, m < 960], ['1 亞洲 20-03', '2 歐洲 03-09:30',
                            '3 美早 09:30-12', '4 美午 12-16'], '5 收盤後 16-20')
    return out


def nth_in_run(b):
    """n-th qualifying signal of the same trend run (1 = first)."""
    nth = np.zeros(len(b), int); seen = {}
    for q, (side, start) in enumerate(zip(b.side.values, b.run_start.values)):
        key = (side, start); seen[key] = seen.get(key, 0) + 1; nth[q] = seen[key]
    return nth


def streaks(win):
    out = []; run = 0
    for w in win:
        if w:
            if run: out.append(run); run = 0
        else:
            run += 1
    if run: out.append(run)
    return np.array(out, int)


def seq_trades(b, R):
    t = ss.seq(b, R).copy()
    t['net'] = t[f'r{R:g}'].values - ss.COST / t.risk.values
    t['win'] = t.net.values > 0
    t['exit'] = t[f'x{R:g}'].values
    return t.reset_index(drop=True)


def summary(t):
    net = t.net.values; a = t.date.values < ss.SPLIT
    if len(t) == 0: return '   0 筆'
    eq = np.cumsum(net); dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
    st = streaks(t.win.values); mo = pd.Series(net).groupby(t.month.values).sum()
    return (f'{len(t):4d} 筆  勝率 {100 * t.win.mean():4.1f}%  每筆 {net.mean():+.3f}R（前 {net[a].mean():+.3f} 後 {net[~a].mean():+.3f}）'
            f'  一年 {net.sum():+6.1f}R  回撤 {dd:5.1f}R  最長連虧 {st.max() if len(st) else 0:2d}  賺錢月 {(mo > 0).sum()}/{len(mo)}')


def part1(b):
    print('\n######## 1. 連續虧損')
    for R in RS:
        t = seq_trades(b, R); w = t.win.values; st = streaks(w)
        print(f'\n  {R:g}R：{summary(t)}')
        cnt = pd.Series(st).value_counts().sort_index()
        print('  連虧長度分布：' + '，'.join(f'{k} 筆×{v}' for k, v in cnt.items()))
        rng = np.random.default_rng(7); mx = []; ge = {L: [] for L in (5, 8, 10)}
        for _ in range(4000):
            sp = streaks(rng.permutation(w)); mx.append(sp.max())
            for L in ge: ge[L].append((sp >= L).sum())
        mx = np.array(mx)
        print(f'  最長連虧：實際 {st.max()}；隨機排列（同樣勝率）中位數 {np.median(mx):.0f}、90% 區間 {np.quantile(mx, .05):.0f}–{np.quantile(mx, .95):.0f}'
              f'，實際 ≥ 隨機的機率 {(mx >= st.max()).mean():.0%}')
        for L in ge:
            print(f'  連虧 ≥ {L:2d} 筆的次數：實際 {(st >= L).sum():2d}，隨機平均 {np.mean(ge[L]):4.1f}（90% 區間 {np.quantile(ge[L], .05):.0f}–{np.quantile(ge[L], .95):.0f}）')
        n1, n2 = w.sum(), (~w).sum(); N = n1 + n2
        runs = 1 + (w[1:] != w[:-1]).sum(); er = 1 + 2 * n1 * n2 / N
        var = 2 * n1 * n2 * (2 * n1 * n2 - N) / (N * N * (N - 1))
        print(f'  連串檢定：輸贏交替 {runs} 次，隨機預期 {er:.0f}，z = {(runs - er) / np.sqrt(var):+.2f}（負的代表輸贏有成群出現的傾向）')
        before = np.zeros(len(w), int)
        for q in range(1, len(w)): before[q] = 0 if w[q - 1] else before[q - 1] + 1
        parts = []
        for lo, hi, nm in ((0, 0, '上一筆贏'), (1, 1, '連虧 1 後'), (2, 2, '連虧 2 後'), (3, 3, '連虧 3 後'), (4, 99, '連虧 4+ 後')):
            m = (before >= lo) & (before <= hi)
            parts.append(f'{nm} {m.sum()} 筆 勝率 {100 * w[m].mean():.1f}% 每筆 {t.net.values[m].mean():+.3f}R')
        print('  ' + '；'.join(parts))
        sameday = np.r_[False, t.date.values[1:] == t.date.values[:-1]]
        pl = np.r_[False, ~w[:-1]]
        print(f'  同一天、上一筆虧：{(sameday & pl).sum()} 筆 勝率 {100 * w[sameday & pl].mean():.1f}%；'
              f'同一天、上一筆贏：{(sameday & ~pl).sum()} 筆 勝率 {100 * w[sameday & ~pl].mean():.1f}%；當天第一筆：{(~sameday).sum()} 筆 勝率 {100 * w[~sameday].mean():.1f}%')


FEATS = [('since', '趨勢已持續幾根（2 分 K）'), ('mixfrac30', '近 1 小時 TJ 是 MIX 的比例'), ('flips60', '近 2 小時 TJ 狀態切換次數'),
         ('slope5', 'TJ 差值 5 根變化（順勢方向，點）'), ('pullback', 'TJ 差值離這段趨勢高點（點）'), ('nth', '這段趨勢的第幾個過濾訊號'),
         ('spread', 'TJ 差值（順勢方向，點）'), ('er10', '效率比 ER（10 根）'), ('er30', '效率比 ER（30 根）'), ('chop14', '盤整指數 CHOP（14）'),
         ('chop30', '盤整指數 CHOP（30）'), ('adx', 'ADX（14）'), ('rng30', '近 1 小時高低差 ÷ ATR'), ('sig30', '近 1 小時原始訊號數'),
         ('opp30', '近 1 小時反向訊號數'), ('slowslope', '15 秒 EMA1130 斜率（1 小時，ATR）'), ('atr_rel', 'ATR ÷ 近一天平均 ATR'),
         ('tjSlow', '離 15 秒 EMA1130（ATR）')]


def part2(b):
    print('\n######## 2. 進場當下的狀態，五等分（所有過濾後訊號各自獨立）')
    a = b.date.values < ss.SPLIT
    for key, nm in FEATS + [('sess', '時段')]:
        x = b[key]
        g = x if key in ('sess', 'nth') else pd.qcut(x, 5, duplicates='drop')
        if key == 'nth': g = x.clip(upper=4).map({1: '1', 2: '2', 3: '3', 4: '4+'})
        print(f'  {nm}')
        for lab, idx in b.groupby(g, observed=True).groups.items():
            y = b.loc[idx]; aa = y.date.values < ss.SPLIT
            n3 = y.r3.values - ss.COST / y.risk.values; n2 = y.r2.values - ss.COST / y.risk.values
            print(f'    {str(lab):<26} {len(y):4d} 筆  3R 勝率 {100 * (y.r3 > 0).mean():4.1f}% 每筆 {n3.mean():+.3f}（前 {n3[aa].mean():+.3f} 後 {n3[~aa].mean():+.3f}）'
                  f'  2R 每筆 {n2.mean():+.3f}')


def part3(b, R=3.0, L=6):
    print(f'\n######## 3. 長連虧（≥ {L} 筆，{R:g}R）裡的單 vs 其他')
    t = seq_trades(b, R); w = t.win.values
    lab = np.zeros(len(t), int); q = 0
    while q < len(t):
        if not w[q]:
            e = q
            while e < len(t) and not w[e]: e += 1
            if e - q >= L: lab[q:e] = 1
            q = e
        else:
            q += 1
    grp = {'長連虧裡的虧損': lab == 1, '其他虧損': (lab == 0) & ~w, '賺錢的單': w}
    keys = [k for k, _ in FEATS if k in t.columns]
    print('  ' + f'{"":<16}' + ''.join(f'{k:>10}' for k in keys))
    for nm, m in grp.items():
        print(f'  {nm:<14}{m.sum():4d}' + ''.join(f'{t[k].values[m].mean():10.2f}' for k in keys))
    print('  （數值是平均。since=趨勢持續根數，mixfrac30=近 1 小時 MIX 比例，flips60=近 2 小時 TJ 切換次數）')
    print(f'\n  最長的 8 段連虧：')
    segs = []; q = 0
    while q < len(t):
        if not w[q]:
            e = q
            while e < len(t) and not w[e]: e += 1
            segs.append((e - q, q, e)); q = e
        else:
            q += 1
    for ln, q0, q1 in sorted(segs, reverse=True)[:8]:
        y = t.iloc[q0:q1]
        print(f'    {ln:2d} 筆  {y.date.iloc[0]} .. {y.date.iloc[-1]}  多 {(y.side == 1).sum()} 空 {(y.side == -1).sum()}'
              f'  MIX 比例 {y.mixfrac30.mean():.2f}  切換 {y.flips60.mean():.1f}  趨勢持續 {y.since.median():.0f} 根  ER30 {y.er30.mean():.2f}'
              f'  CHOP30 {y.chop30.mean():.0f}  合計 {y.net.sum():+.1f}R')


def breakers(t, rule):
    """Pick the real trades out of the full sequence t (shadow trades keep running)."""
    keep = np.ones(len(t), bool); w = t.win.values; ex = t.exit.values; dates = t.date.values; ii = t.i.values
    if rule[0] == 'day':                      # after k losses in a row, no more trades that day
        k = rule[1]; run = 0; stop_day = None
        for q in range(len(t)):
            if stop_day == dates[q]: keep[q] = False
            else:
                if q and dates[q] != dates[q - 1]: run = 0
            if not keep[q]: continue
            run = 0 if w[q] else run + 1
            if run >= k: stop_day = dates[q]
    elif rule[0] == 'pause':                  # after k losses in a row, skip signals for n bars
        k, nbar = rule[1], rule[2]; run = 0; until = -1
        for q in range(len(t)):
            if ii[q] < until: keep[q] = False; continue
            run = 0 if w[q] else run + 1
            if run >= k: until = ex[q] + nbar; run = 0
    elif rule[0] == 'newtrend':               # after a loss, wait for a new Trend Judge trend run
        last_loss_exit = -1; rs = t.run_start.values
        for q in range(len(t)):
            if last_loss_exit >= 0 and rs[q] <= last_loss_exit: keep[q] = False
            if not w[q]: last_loss_exit = ex[q]
    elif rule[0] == 'shadow':                 # after a loss, only paper-trade until a paper trade wins
        armed = True
        for q in range(len(t)):
            keep[q] = armed
            if armed and not w[q]: armed = False
            elif not armed and w[q]: armed = True
    return t[keep]


def part4(b):
    print('\n######## 4. 過濾條件和停損機制（一次一筆）')
    F = {
        '基準': b.side != 0,
        '近 1 小時 MIX 比例 ≤ 0.2': b.mixfrac30 <= 0.2,
        '近 1 小時 MIX 比例 ≤ 0.5': b.mixfrac30 <= 0.5,
        '趨勢已持續 ≥ 15 根': b.since >= 15,
        '趨勢已持續 ≥ 30 根': b.since >= 30,
        '近 2 小時 TJ 切換 ≤ 2 次': b.flips60 <= 2,
        'TJ 差值 5 根內在擴大': b.slope5 > 0,
        'ER30 ≥ 0.2': b.er30 >= 0.2,
        'CHOP30 ≤ 55': b.chop30 <= 55,
        'ADX ≥ 20': b.adx >= 20,
        '每段趨勢只做前 2 個訊號': b.nth <= 2,
        '跳過每段趨勢第 1 個訊號': b.nth >= 2,
        '趨勢持續 ≤ 3 小時（90 根）': b.since <= 90,
        '趨勢持續 ≤ 4 小時（120 根）': b.since <= 120,
    }
    for R in RS:
        print(f'\n  {R:g}R')
        for nm, m in F.items():
            print(f'    {nm:<26} {summary(seq_trades(b[m], R))}')
        t = seq_trades(b, R)
        for rule, nm in ((('day', 2), '當天連虧 2 筆就停'), (('day', 3), '當天連虧 3 筆就停'), (('day', 4), '當天連虧 4 筆就停'),
                         (('pause', 3, 60), '連虧 3 筆暫停 2 小時'), (('pause', 4, 120), '連虧 4 筆暫停 4 小時'),
                         (('newtrend',), '虧損後等 TJ 新的一段趨勢'), (('shadow',), '虧損後先模擬，模擬贏了才恢復')):
            print(f'    {nm:<26} {summary(breakers(t, rule))}')


def part5(b, df, nxt):
    print('\n######## 5. 持倉中 Trend Judge 轉向就出場（收盤出場，一次一筆）')
    h, l, c = df.high.values, df.low.values, df.close.values; d = df.tj_diff.values
    conds = {'不提前出場（基準）': None, 'TJ 轉成反向趨勢': lambda v: v < -TH, 'TJ 轉回 MIX 或反向': lambda v: v <= TH,
             'TJ 差值跌破 0': lambda v: v <= 0}
    for R in RS:
        print(f'\n  {R:g}R')
        for nm, cond in conds.items():
            rows = []; busy = -1
            for q in b.itertuples():
                i = q.i
                if i < busy: continue
                k = q.side
                stop = min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])
                risk = (c[i] - stop) * k; end = min(i + ss.HORIZON, nxt[i])
                tgt = c[i] + k * R * risk; r = None; ex = end
                for j in range(i + 1, end + 1):
                    if (l[j] <= stop) if k == 1 else (h[j] >= stop): r = -1.0; ex = j; break
                    if (h[j] >= tgt) if k == 1 else (l[j] <= tgt): r = R; ex = j; break
                    if cond is not None and cond(d[j] * k): r = (c[j] - c[i]) * k / risk; ex = j; break
                if r is None: r = (c[end] - c[i]) * k / risk
                busy = ex
                rows.append((q.date, q.month, r - ss.COST / risk, ex - i))
            t = pd.DataFrame(rows, columns=['date', 'month', 'net', 'bars']); t['win'] = t.net > 0
            print(f'    {nm:<20} {summary(t)}  平均持有 {t.bars.mean():.1f} 根')


def main():
    s = tw.build()
    df = rbs.prepared('NQ', tw.TF)
    s = pd.concat([s, mp.features(s, df), context(df, s)], axis=1)
    b = s[(s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.spread > TH) & (s.tjSlow < 3)].sort_values('i').copy()
    b['nth'] = nth_in_run(b)
    nxt, _ = ss.bar_context(df, tw.TF)
    print(f'NQ 2 分 K，{s.date.min()} .. {s.date.max()}，門檻 {TH:g}、1h、停損 ≥ 1 ATR、離 15 秒 EMA1130 ≤ 3 ATR、避開事件時段：{len(b)} 個訊號')
    part1(b); part2(b); part3(b); part4(b); part5(b, df, nxt)


if __name__ == '__main__':
    main()
