"""How often does each v3 setup reach 1R / 1.5R / 2R / 3R before its stop? (one at a time, 60-bar limit)

  cd indicators/backtest
  python3 -I rbs/hit_rates.py

Remi: how far a trade runs is luck; reaching 1.5R is skill. Hit rate = share of trades whose target at that R is
reached before the stop (and within 60 bars / before the halt). v3 as now (FOMC days off, junk time off, stop >= 0.95
ATR, 2m trend 0-400, 5m 0-180, 3m 90-120). NQ setups: the v3 year (2025-10 .. 2026-10) and the four years before.
NQ RTH 1m (QQQ setting), five years. GEX setup: 2026-06-29 .. 10-14 only (ZeroGEX data).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import gex_params as gp

RS = (1.0, 1.5, 2.0, 3.0)
SPLIT = oc.YEARS[3][2]


def line(lab, rates, n):
    print(f'   {lab:<26} ' + '  '.join(f'{R:g}R {100 * r:3.0f}%' for R, r in zip(RS, rates)) + f'   （{n} 筆）')


def main():
    one = oc.load(); M = oc.Market(one)
    for tf, cap, lo in ((2, 400, 0), (3, 120, 90), (5, 180, 0)):
        C = M.ctx(tf); df = C.df; th = df.thr.values
        ny = pd.DatetimeIndex(df.datetime) + pd.Timedelta(minutes=tf); ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY)
        m = np.asarray(ny.hour * 60 + ny.minute); junk = (m >= 720) & (m <= 785)
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm >= lo) & (s.tm < cap) & ~s.date.isin(ss.FOMC) & ~junk[s.i]]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not junk[x[0]]] if tf != 3 else []
        res = {}
        for R in RS:
            t = oc.sim(C, T, mix, R, R)
            for kind in ('趨勢', 'MIX'):
                for per, z in (('v3 那年', t[(t.kind == kind) & (t.date > SPLIT)]), ('前 4 年', t[(t.kind == kind) & (t.date <= SPLIT)])):
                    res.setdefault((kind, per), []).append(((z.R >= R - 1e-9).mean(), len(z)))
        print(f'\nNQ {tf}m')
        for (kind, per), v in res.items():
            if v[0][1]: line(f'{kind}（{per}）', [a for a, _ in v], v[0][1])
    df, t = oc.nq_rth(one, detail=True)
    print('\nNQ RTH 1m（QQQ 做法）')
    for per, z in (('v3 那年', t[t.date > SPLIT]), ('前 4 年', t[t.date <= SPLIT])):
        line(f'趨勢（{per}）', [(z[f"r{R:g}"] >= R - 1e-9).mean() for R in RS], len(z))
    one_q = mm.load_market('qqq', []); tdm = mm.minute_trend(one_q); H = mm.hourly(one_q, True)
    dq = mm.chart(one_q, tdm, 1, 20.0, 40.0)
    y = gp.setup_rows(dq, H, 35, 8, '2026-06-29', '2026-10-14')
    print('\nGEX setup（NQ RTH 1m，每筆單獨算）')
    line('2026-06-29 .. 10-14', [(y[f"r{R:g}"] >= R - 1e-9).mean() for R in RS], len(y))


if __name__ == '__main__':
    main()
