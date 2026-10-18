"""2-minute win-rate matrix of the two Remi Superb alerts on NQ, ES and TXF: the filtered alerts (Trend) and the
MIX-box breakout (MIX), targets 1R / 1.5R / 2R / 3R.

  cd indicators/backtest
  python3 rbs/trend_mix_matrix.py nq data/NQ_1m_databento.csv
  python3 rbs/trend_mix_matrix.py es data/ES_1m_databento.csv
  python3 -I rbs/trend_mix_matrix.py txf data_TXFR1_2024.sql data_TXFR1_2025.sql data_TXFR1_2026.sql

Remi Superb defaults per symbol: Trend Judge 一般 threshold NQ 10, ES 4, TXF 30; cost per trade NQ 1, ES 0.5,
TXF 2 points.
  Trend = filtered alerts: spread > threshold in the trade's direction, last complete 1-hour close on the trade's
          side of its EMA20, stop >= 1 ATR, close - 15-second EMA1130 <= 3 ATR, event windows avoided; entry at
          the signal close, the two-bar stop, 60-bar time exit (setup_study.py).
  MIX   = MIX-box breakout: |spread| <= threshold for 60 minutes (blips of up to 4 minutes allowed) makes the box;
          the first break 10% of its height beyond it within the next 60 minutes is entered with a stop order,
          stop at the box middle, 2-hour time exit (mix_breakout.py).
Each kind one position at a time; 合起來 = both kinds, one position at a time. 勝率 = trades that made money
before costs; 每筆 = net R after costs. NQ / ES: Trend Judge from 1-minute closes (rbs.py), 前 / 後 split at
2026-06-01 like remi_superb.md; TXF: from the 1-minute TXFR1 dumps with the front-month roll skipped
(txf_check.py), split at the middle date, plus each calendar year.
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

SYM = {'nq': ('NQ', 10.0, 1.0), 'es': ('ES', 4.0, 0.5), 'txf': ('TXF', 30.0, 2.0)}
TARGETS = (1.0, 1.5, 2.0, 3.0)


def load(sym, paths):
    if sym == 'txf':
        df = tx.load_sql(paths)
        s = tx.build(df)
    else:
        rbs.DATA['NQ'] = paths[0]                      # the research code reads 'NQ'
        tag = os.path.splitext(os.path.basename(paths[0]))[0]
        tw.TF = 2
        tw.CACHE = os.path.join(ss.DATA_DIR, 'th_sweep_2m.pkl' if 'NQ_1m_databento' in tag else f'{tag}_th_sweep_2m.pkl')
        s = tw.build()
        df = rbs.prepared('NQ', 2)
        s = pd.concat([s, mp.features(s, df)], axis=1)
    rbs._cache[('NQ', 2)] = df                         # mix_range.load reads the chart through rbs.prepared
    return df, s


def trend_rows(s, th, R):
    b = s[(s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.tjSlow < 3) & (s.spread > th)].sort_values('i')
    r = b[f'r{R:g}'].values
    return pd.DataFrame(dict(i=b.i.values, x=b[f'x{R:g}'].values, side=b.side.values, risk=b.risk.values, R=r,
                             net=r - ss.COST / b.risk.values, date=b.date.values, month=b.month.values, kind='Trend'))


def stat(t, split):
    t = t.sort_values('i'); R = t.R.values; net = t.net.values; a = t.date.values < split; L = t.side.values == 1
    m = lambda v: v.mean() if len(v) else np.nan
    eq = np.cumsum(net); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)) if len(eq) else 0.0
    return dict(n=len(t), win=100 * m(R > 0), net=m(net), A=m(net[a]), B=m(net[~a]), tot=net.sum(), dd=dd,
                nL=L.sum(), winL=100 * m(R[L] > 0), netL=m(net[L]), nS=(~L).sum(), winS=100 * m(R[~L] > 0), netS=m(net[~L]))


def main():
    sym, paths = sys.argv[1].lower(), sys.argv[2:]
    name, th, cost = SYM[sym]
    ss.COST = cost; mb.COST = cost; mr.TH = th
    df, s = load(sym, paths)
    B = mr.load()
    boxes = mb.causal_boxes(B, 30, grace=2)                     # 60 minutes on 2 minutes
    days = sorted(set(B['date'][B['tradable']]))
    split = ss.SPLIT if sym != 'txf' else days[len(days) // 2]
    res = {}
    for R in TARGETS:
        tr = mb.seq_all(trend_rows(s, th, R))
        bo = mb.breakouts(B, boxes, R, max_age=mb.AGE, entry='stop'); bo['kind'] = 'MIX'
        mx = mb.seq_all(bo)
        both = mb.seq_all(pd.concat([trend_rows(s, th, R), bo[['i', 'x', 'side', 'risk', 'R', 'net', 'date', 'month', 'kind']]],
                                    ignore_index=True))
        res[R] = {'Trend': tr, 'MIX': mx, '合起來': both}

    print(f'######## {name} 2 分 K：{days[0]} .. {days[-1]}，門檻 {th:g}，每筆扣 {cost:g} 點，前 / 後 分界 {split}，MIX 區間 {len(boxes)} 個')
    print('              ' + ''.join(f'{R:>10g}R' for R in TARGETS))
    for kind in ('Trend', 'MIX', '合起來'):
        st = [stat(res[R][kind], split) for R in TARGETS]
        print(f'  {kind:<6} 勝率 ' + ''.join(f'{x["win"]:>10.1f}%' for x in st))
        print(f'  {kind:<6} 每筆 ' + ''.join(f'{x["net"]:>+10.3f}R' for x in st))
    print('  打平勝率    ' + ''.join(f'{100 / (1 + R):>10.1f}%' for R in TARGETS) + '（不扣成本）')
    for kind in ('Trend', 'MIX', '合起來'):
        print(f'\n  ## {kind}')
        for R in TARGETS:
            x = stat(res[R][kind], split)
            print(f'   {R:>3g}R  {x["n"]:4d} 筆  勝率 {x["win"]:4.1f}%  每筆 {x["net"]:+.3f}R（前 {x["A"]:+.3f} 後 {x["B"]:+.3f}）'
                  f'  合計 {x["tot"]:+6.1f}R  回撤 {x["dd"]:5.1f}R | 多 {x["nL"]:3d} 筆 {x["winL"]:4.1f}% {x["netL"]:+.3f}R'
                  f'  空 {x["nS"]:3d} 筆 {x["winS"]:4.1f}% {x["netS"]:+.3f}R')
    years = sorted({d[:4] for d in days})
    if sym == 'txf' and len(years) > 1:
        print('\n  ## 逐年每筆（R）')
        for kind in ('Trend', 'MIX', '合起來'):
            for R in TARGETS:
                t = res[R][kind]; y = t.date.str[:4]
                print(f'   {kind:<6} {R:>3g}R  ' + '  '.join(f'{yy} {len(t[y == yy]):3d} 筆 {t.net[y == yy].mean():+.3f}' for yy in years))


if __name__ == '__main__':
    main()
