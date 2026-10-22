"""Score the marks of another TradingView indicator from a chart export (e.g. the big red sell triangles), treated as
sells (or buys) at the mark bar's close.

  cd indicators/backtest
  python3 -I rbs/tv_mark_check.py "CME_MINI_NQ1!, 2_xxxxx.csv" [column number, default 6] [sell|buy]

Each mark on its own: stop at the two-bar extreme (mark bar and the one before, 1 tick beyond), targets 1R / 1.5R / 2R / 3R,
60-bar limit, 1 point cost. Split by the Trend Judge spread of the export's v3 column (TJ 差值, with / against the trade)
and by session; compared with v3's own tradable sells / buys in the same export (可交易 Sell / Buy).
"""
import sys
import numpy as np
import pandas as pd

COST = 1.0
RS = (1.0, 1.5, 2.0, 3.0)


def score(h, l, c, idx, side, stops=None):
    rows = []
    for n, i in enumerate(idx):
        if i < 1 or i + 1 >= len(c): continue
        e = c[i]; st = stops[n] if stops is not None else ((max(h[i - 1], h[i]) + 0.25) if side < 0 else (min(l[i - 1], l[i]) - 0.25))
        risk = (st - e) * side * -1
        if risk <= 0: continue
        out = {}
        for R in RS:
            tp = e + side * R * risk; r = None
            for j in range(i + 1, min(i + 61, len(c))):
                if (h[j] >= st) if side < 0 else (l[j] <= st): r = -1.0; break
                if (l[j] <= tp) if side < 0 else (h[j] >= tp): r = R; break
            if r is None: r = (c[min(i + 60, len(c) - 1)] - e) * side / risk
            out[R] = r
        rows.append(dict(i=i, risk=risk, **{f'r{R:g}': out[R] for R in RS}))
    return pd.DataFrame(rows)


def line(lab, t):
    if not len(t): print(f'   {lab:<26}   0'); return
    print(f'   {lab:<26}{len(t):5d}' + ''.join(f'{100 * (t[f"r{R:g}"] >= R - 1e-9).mean():6.0f}%' for R in RS)
          + ''.join(f'{(t[f"r{R:g}"] - COST / t.risk).mean():+7.2f}R' for R in (1.0, 2.0, 3.0)) + f'{t.risk.median():7.0f}點')


def main():
    path = sys.argv[1]; col = int(sys.argv[2]) - 1 if len(sys.argv) > 2 else 5
    side = 1 if len(sys.argv) > 3 and sys.argv[3] == 'buy' else -1
    r = pd.read_csv(path)
    names = list(r.columns)
    h, l, c = r.high.values, r.low.values, r.close.values
    tw = pd.DatetimeIndex(pd.to_datetime(r.time, unit='s', utc=True)).tz_convert('Asia/Taipei')
    marks = np.flatnonzero(pd.to_numeric(r.iloc[:, col], errors='coerce').fillna(0).values != 0)
    tj = pd.to_numeric(r[[n for n in names if n.startswith('TJ 差值')][0]], errors='coerce').values
    print(f'{path.split("/")[-1]}：{tw[0]:%Y-%m-%d} .. {tw[-1]:%Y-%m-%d}（台北），第 {col + 1} 欄「{names[col]}」{len(marks)} 個，當{"買" if side > 0 else "賣"}訊算')
    print(f'   {"":<26}{"筆":>5}' + ''.join(f'{f"{R:g}R":>7}' for R in RS) + ''.join(f'{f"{R:g}R 每筆":>8}' for R in (1.0, 2.0, 3.0)) + f'{"停損中位":>8}')
    t = score(h, l, c, marks, side); t['tj'] = tj[t.i.values] * side
    m = tw[t.i.values].hour * 60 + tw[t.i.values].minute
    line('全部', t)
    line('TJ 順勢（同方向 > 10）', t[t.tj > 10]); line('TJ 中性（±10）', t[t.tj.abs() <= 10]); line('TJ 逆勢（反方向 > 10）', t[t.tj < -10])
    line('TJ 強順勢（> 35）', t[t.tj > 35])
    line('台北 21:30–04:00（美股盤）', t[(m >= 1290) | (m < 240)]); line('台北 06:00–21:30（亞歐盤）', t[(m >= 360) & (m < 1290)])
    v = names.index('可交易 Sell' if side < 0 else '可交易 Buy')
    vi = np.flatnonzero(pd.to_numeric(r.iloc[:, v], errors='coerce').fillna(0).values != 0)
    line(f'對照：v3 {names[v]}', score(h, l, c, vi, side))
    both = sorted(set(marks) & set(vi)); print(f'   和 v3 同一根：{len(both)} 個')


if __name__ == '__main__':
    main()
