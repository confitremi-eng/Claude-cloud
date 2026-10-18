"""Enter at the signal's stop with a limit order instead of at the signal close (Remi Superb filtered alerts, 2 minutes).

  cd indicators/backtest
  python3 rbs/limit_entry.py DATA.csv 門檻 成本
  e.g. python3 rbs/limit_entry.py data/ES_1m_databento.csv 4 0.5
       python3 rbs/limit_entry.py data/NQ_1m_databento.csv 10 1

Signals = Remi Superb's filtered alerts on the 2-minute chart (有趨勢 spread > 門檻, 1-hour EMA20 on the trade's
side, stop >= 1 ATR, close - 15-second EMA1130 <= 3 ATR, event windows avoided). R0 = signal close - two-bar stop.
Every variant is simulated on the 1-minute bars after the signal bar closes, so all of them are compared alike:
  市價（現在）  enter at the signal close, stop at the two-bar extreme, target m x R0
  掛單 a / b    limit order a x R0 back from the signal close (a = 1: at the original stop), new stop b x R0
                beyond the limit, target m x (b x R0) from the limit; the order waits W minutes
Fill: a 1-minute bar trades at the limit (touch) or one tick through it; a bar opening beyond the limit fills at
the open. In the fill minute only the stop is checked (the target may have printed before the fill); after that
the stop comes first when both are hit in one minute. Stops and targets hit by an opening gap fill at the open.
Exit after 120 minutes, or at the last minute before a hole longer than 30 minutes (a waiting order is cancelled
there too). One order or position at a time: a signal that arrives while an order waits or a trade is open is
skipped. The same cost per trade (points) for every variant. 前 / 後 = the two halves of the file by date.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import th_sweep as tw
import ma_position as mp

HOLD = 120                      # 1-minute bars after entry
TICK = 0.25
GAP = np.timedelta64(30, 'm')
VARIANTS = [                    # name, a (limit offset in R0), b (new stop in R0), W (minutes), fill through (ticks)
    ('市價（現在）', None, None, None, 0),
    ('掛停損點，停損再 1R', 1.0, 1.0, 60, 0),
    ('掛停損點，停損再 1R（穿價成交）', 1.0, 1.0, 60, 1),
    ('掛停損點，停損再 1R，等 20 分', 1.0, 1.0, 20, 0),
    ('掛停損點，停損再 1R，等 120 分', 1.0, 1.0, 120, 0),
    ('掛停損點，停損再 0.5R', 1.0, 0.5, 60, 0),
    ('掛一半，停損不變', 0.5, 0.5, 60, 0),
]


def minutes():
    one = rbs.load1('NQ')
    T = one.index.values.astype('datetime64[ns]')
    n = len(T)
    gap_after = np.r_[np.diff(T) > GAP, True]
    nxt = np.empty(n, int); last = n - 1
    for j in range(n - 1, -1, -1):
        if gap_after[j]: last = j
        nxt[j] = last
    return T, one.open.values, one.high.values, one.low.values, one.close.values, nxt


def signals_sel(th):
    tw.TF = 2
    s = tw.build()
    df = rbs.prepared('NQ', 2)
    s = pd.concat([s, mp.features(s, df)], axis=1)
    m = (s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.tjSlow < 3) & (s.spread > th)
    s = s[m].sort_values('i').reset_index(drop=True)
    h, l, c = df.high.values, df.low.values, df.close.values
    i, k = s.i.values, s.side.values
    s['P0'] = c[i]
    s['S0'] = np.where(k == 1, np.minimum(l[i - 1], l[i]), np.maximum(h[i - 1], h[i]))
    s['R0'] = (s.P0 - s.S0) * k
    s['tclose'] = (pd.DatetimeIndex(df.last_min.values[i]) + pd.Timedelta(minutes=1)).values.astype('datetime64[ns]')
    return s


def main():
    path, th, cost = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    rbs.DATA['NQ'] = path                              # the research code reads 'NQ'
    tag = os.path.splitext(os.path.basename(path))[0]
    tw.CACHE = os.path.join(ss.DATA_DIR, 'th_sweep_2m.pkl' if 'NQ_1m_databento' in tag else f'{tag}_th_sweep_2m.pkl')
    s = signals_sel(th)
    T, O, H, L, C, nxt = minutes()
    s['j0'] = np.searchsorted(T, s.tclose.values, 'left')
    d = sorted(s.date.unique()); split = d[len(d) // 2]

    def exit_px(k, stop, tgt, jf, jl, skip_first):
        for j in range(jf, jl + 1):
            if (L[j] <= stop) if k == 1 else (H[j] >= stop):
                return (min(stop, O[j]) if k == 1 else max(stop, O[j])), j
            if skip_first and j == jf: continue
            if (H[j] >= tgt) if k == 1 else (L[j] <= tgt):
                return (max(tgt, O[j]) if k == 1 else min(tgt, O[j])), j
        return C[jl], jl

    def market(k, P0, R0, j0, m):
        jl = min(j0 + HOLD - 1, nxt[j0])
        px, jx = exit_px(k, P0 - k * R0, P0 + k * m * R0, j0, jl, False)
        return P0, px, jx, R0

    def limit(k, P0, R0, j0, m, a, b, W, thr):
        P = P0 - k * a * R0; risk = b * R0; stop = P - k * risk; tgt = P + k * m * risk
        jw = min(j0 + W - 1, nxt[j0])
        for j in range(j0, jw + 1):
            if (L[j] <= P - thr * TICK) if k == 1 else (H[j] >= P + thr * TICK):
                F = min(P, O[j]) if k == 1 else max(P, O[j])
                if (F - stop) * k <= 0:                        # opened beyond the new stop too
                    return F, F, j, risk
                jl = min(j + HOLD - 1, nxt[j])
                px, jx = exit_px(k, stop, tgt, j, jl, True)
                return F, px, jx, risk
        return None, None, jw, risk

    print(f'{tag}：{d[0]} .. {d[-1]}，2 分 K，門檻 {th:g}，成本 {cost:g} 點，前 / 後 分界 {split}，'
          f'過濾後訊號 {len(s)} 個，停損中位數 {s.R0.median():.2f} 點')
    for m in (1.0, 2.0, 3.0):
        # the market-entry result of every signal on its own, to see which signals a limit order catches
        base_r = np.array([(lambda F, px, jx, rk: ((px - F) * k - cost) / rk)(*market(k, P0, R0, j0, m))
                           for k, P0, R0, j0 in zip(s.side.values, s.P0.values, s.R0.values, s.j0.values)])
        print(f'\n## 目標 {m:g}R（新停損距離的倍數）')
        for name, a, b, W, thr in VARIANTS:
            busy = -1; rows = []
            for q, (k, P0, R0, j0, dt) in enumerate(zip(s.side.values, s.P0.values, s.R0.values, s.j0.values, s.date.values)):
                if j0 <= busy: continue
                F, px, jx, rk = market(k, P0, R0, j0, m) if a is None else limit(k, P0, R0, j0, m, a, b, W, thr)
                busy = jx
                rows.append((q, k, dt, F is not None, np.nan if F is None else (px - F) * k, rk))
            t = pd.DataFrame(rows, columns=['q', 'k', 'date', 'fill', 'gross', 'risk'])
            f = t[t.fill]
            pts = f.gross - cost; r = pts / f.risk
            eq = np.cumsum(pts.values); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)) if len(eq) else 0.0
            a_ = f.date.values < split
            mm = lambda v: v.mean() if len(v) else np.nan
            line = (f'  {name:<22} 訊號 {len(t):4d}  成交 {len(f):4d}（{100 * len(f) / max(len(t), 1):3.0f}%）  勝率 {100 * mm(f.gross.values > 0):4.1f}%'
                    f'  每筆 {mm(r.values):+.3f}R（前 {mm(r.values[a_]):+.3f} 後 {mm(r.values[~a_]):+.3f}）'
                    f'  合計 {pts.sum():+7.1f} 點  回撤 {dd:6.1f} 點  多 {mm(r.values[f.k.values == 1]):+.3f} 空 {mm(r.values[f.k.values == -1]):+.3f}')
            if a is not None:
                br = base_r[t.q.values]
                line += f'  | 市價結果：有成交的 {mm(br[t.fill.values]):+.3f}R、沒成交的 {mm(br[~t.fill.values]):+.3f}R'
            print(line)


if __name__ == '__main__':
    main()
