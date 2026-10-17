"""Two contracts per signal on NQ 2 minutes (the Databento year): split targets, breakeven, two positions.

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/two_lots.py [門檻]

Signals: the filtered alerts (有趨勢 with the given Trend Judge threshold, default 10; 1-hour trend;
stop >= 1 ATR; data / open / close / Globex windows avoided), from th_sweep.py's cache.
Entry at the signal close, stop at the extreme of the signal bar and the one before, 60-bar time exit,
flat before a data hole, stop first when stop and target are in the same bar, 1 point cost per contract.
R is per signal (both contracts together, one contract's risk = 1R); so 2 contracts at 2R = 2 x the 1-lot result.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import th_sweep as tw


def leg(h, l, c, i, k, stop, R, end, be_after=None):
    """One contract: target R (None = time exit only). be_after: once price reaches this R, stop -> entry.
    Returns (R result, exit bar, bar where be_after was reached or None)."""
    e = c[i]; risk = (e - stop) * k; st = stop; hit = None
    for j in range(i + 1, end + 1):
        if (l[j] <= st) if k == 1 else (h[j] >= st):
            return (st - e) * k / risk, j, hit
        if R is not None and ((h[j] >= e + R * risk) if k == 1 else (l[j] <= e - R * risk)):
            return R, j, hit
        if be_after is not None and hit is None and ((h[j] >= e + be_after * risk) if k == 1 else (l[j] <= e - be_after * risk)):
            hit = j; st = e                       # from the next bar on
    return (c[end] - e) * k / risk, end, hit


def trade(h, l, c, i, k, stop, end, plan):
    """plan: list of (target R, move this leg's stop to entry once this R is reached)."""
    out = []; ex = i
    for n, (R, be) in enumerate(plan):
        r, x, _ = leg(h, l, c, i, k, stop, R, end, be)
        out.append(r); ex = max(ex, x)
    return out, ex


PLANS = {
    '1 口 2R（基準）': [(2.0, None)],
    '2 口都 2R': [(2.0, None), (2.0, None)],
    '1R + 2R': [(1.0, None), (2.0, None)],
    '1R + 2R，到 1R 第二口保本': [(1.0, None), (2.0, 1.0)],
    '1R + 3R': [(1.0, None), (3.0, None)],
    '1R + 3R，到 1R 第二口保本': [(1.0, None), (3.0, 1.0)],
    '2R + 3R': [(2.0, None), (3.0, None)],
    '1R + 不設目標（60 根出場），到 1R 保本': [(1.0, None), (None, 1.0)],
}


def main():
    th = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    s = tw.build()
    df = rbs.prepared('NQ', tw.TF)
    h, l, c = df.high.values, df.low.values, df.close.values
    nxt, _ = ss.bar_context(df, tw.TF)
    sel = s[(s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.spread > th)].sort_values('i')
    days = s.attrs['days']
    print(f'2 分 K，門檻 {th:g}，避開事件時段，{len(sel)} 個訊號，{days} 個交易日；R 是每個訊號兩口合計（1 口的風險 = 1R），扣每口 1 點')
    for name, plan in PLANS.items():
        rows = []; busy = -1
        for q in sel.itertuples():
            if q.i < busy: continue                  # one signal at a time
            i, k = q.i, q.side
            stop = min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])
            end = min(i + ss.HORIZON, nxt[i])
            rs, ex = trade(h, l, c, i, k, stop, end, plan)
            busy = ex
            rows.append((q.date, k, sum(rs) - len(rs) * ss.COST / q.risk, rs))
        t = pd.DataFrame(rows, columns=['date', 'side', 'net', 'legs'])
        eq = t.net.cumsum().values; dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
        a = t.date < ss.SPLIT
        win = (t.net > 0).mean()
        print(f'  {name:<26} {len(t):5d} 筆  賺錢的比例 {100 * win:4.1f}%  每筆 {t.net.mean():+.3f}R（前 {t.net[a].mean():+.3f} 後 {t.net[~a].mean():+.3f}）'
              f'  一年 {t.net.sum():+6.1f}R  回撤 {dd:5.1f}R  報酬/回撤 {t.net.sum() / dd:4.1f}'
              f'  | 多 {t.net[t.side == 1].mean():+.3f} 空 {t.net[t.side == -1].mean():+.3f}')

    # two independent 1-lot positions at a time (2R each)
    for R in (2.0,):
        open_ex = []; rows = []
        for q in sel.itertuples():
            open_ex = [x for x in open_ex if x > q.i]
            if len(open_ex) >= 2: continue
            i, k = q.i, q.side
            stop = min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])
            end = min(i + ss.HORIZON, nxt[i])
            r, x, _ = leg(h, l, c, i, k, stop, R, end)
            open_ex.append(x); rows.append((q.date, r - ss.COST / q.risk))
        t = pd.DataFrame(rows, columns=['date', 'net'])
        eq = t.net.cumsum().values; dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
        a = t.date < ss.SPLIT
        print(f'  {"最多同時 2 筆（各 1 口 2R）":<26} {len(t):5d} 筆  賺錢的比例 {100 * (t.net > 0).mean():4.1f}%  每筆 {t.net.mean():+.3f}R（前 {t.net[a].mean():+.3f} 後 {t.net[~a].mean():+.3f}）'
              f'  一年 {t.net.sum():+6.1f}R  回撤 {dd:5.1f}R  報酬/回撤 {t.net.sum() / dd:4.1f}')


if __name__ == '__main__':
    main()
