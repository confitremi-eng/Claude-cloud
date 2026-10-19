"""QQQ 1-minute original signals (35, 0, 8, 1) by the SPY / QQQ gamma regime from ZeroGEX (2026-06-29 onward).

  cd indicators/backtest
  python3 rbs/zerogex_fetch.py "../../ZEROGEX API.txt"      # first: download the ZeroGEX history
  python3 -I rbs/gex_qqq.py [階段,EMA]                 # default 35,8; e.g. 35,13

Remi's observation: when SPY and QQQ gamma are both positive the QQQ 1m original signals work; when both are
negative the original Sell works.
Signals: (35, 0, 8, 1) on QQQ 1 minute, every original signal (the orange triangles) and the ones v3 keeps (ETF
filter: Trend Judge 0.5, 1-hour EMA20, stop >= 1 ATR, distance 7 ATR, events, NQ 2m not opposite). Signal close
entry, two-bar stop, 60-bar time exit or the session end. Two price sources:
  QQQ（NQ 代替）  NQ cash-session bars, the stand-in of every earlier QQQ study; cost 1 NQ point
  QQQ 實際       ZeroGEX's own QQQ 1-minute candles (first 3 sessions are warm-up); cost 2.4 cents
Gamma regime of each symbol, read at the minute before the signal bar closes (known at the entry):
  flip     price above / below ZeroGEX's gamma flip (every minute)
  net GEX  sign of ZeroGEX's net GEX (sampled every 30 minutes, the last sample before the signal); only shown when
           the samples cover the period (the frame API is slow, about 5 s a call). On the first 98 SPY samples the
           sign matched price-vs-flip 93% of the time and net GEX at spot 99%, so 'flip' stands in for it
  開盤     the flip regime at 09:30, the same for the whole day
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import strong_stage as sg

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZG = os.path.join(HERE, 'data', 'zerogex')
NS = lambda t: pd.DatetimeIndex(t).values.astype('datetime64[ns]').astype(np.int64)


def zg_minute(sym):
    m = pd.read_csv(os.path.join(ZG, f'{sym}_minute.csv'))
    m['ts'] = pd.to_datetime(m.ts, utc=True)
    return m.sort_values('ts').reset_index(drop=True)


def zg_frames(sym):
    p = os.path.join(ZG, f'{sym}_frames.csv')
    if not os.path.exists(p): return None
    f = pd.read_csv(p); f['ts'] = pd.to_datetime(f.ts, utc=True)
    return f.dropna(subset=['net_gex']).sort_values('ts').reset_index(drop=True)


def lookup(ts_known, table, col_fn, max_gap_min):
    """Value of the last row at or before each time (same day, at most max_gap_min old), else nan."""
    t = NS(table.ts); k = np.searchsorted(t, ts_known, 'right') - 1
    ok = (k >= 0)
    k2 = np.where(ok, k, 0)
    age = (ts_known - t[k2]) / 6e10
    v = col_fn(table).values[k2].astype(float)
    return np.where(ok & (age <= max_gap_min) & (age >= 0), v, np.nan)


def regimes(df, s):
    """Gamma regime of SPY and QQQ for each signal (+1 / -1 / nan), three ways."""
    known = NS(pd.DatetimeIndex(df.last_min.values[s.i]).tz_localize('UTC'))      # start of the signal bar's last minute
    out = {}
    for sym in ('SPY', 'QQQ'):
        m = zg_minute(sym)
        flip = lambda x: np.sign(x.close - x.gamma_flip)
        out[f'{sym}_flip'] = lookup(known, m, flip, 5)
        first = m.groupby(m.ts.dt.tz_convert(ss.NY).dt.date).head(1)
        out[f'{sym}_open'] = lookup(known, first, flip, 24 * 60)
        same_day = pd.DatetimeIndex(known).tz_localize('UTC').tz_convert(ss.NY).date
        od = pd.DatetimeIndex(first.ts).tz_convert(ss.NY).date
        k = np.searchsorted(NS(first.ts), known, 'right') - 1
        out[f'{sym}_open'] = np.where((k >= 0) & (od[np.maximum(k, 0)] == same_day), out[f'{sym}_open'], np.nan)
        fr = zg_frames(sym)
        out[f'{sym}_gex'] = lookup(known, fr, lambda x: np.sign(x.net_gex), 31) if fr is not None else np.full(len(s), np.nan)
    return pd.DataFrame(out, index=s.index)


def real_qqq():
    m = zg_minute('QQQ').dropna(subset=['open', 'high', 'low', 'close'])
    one = m.set_index('ts')[['open', 'high', 'low', 'close']].astype(float)
    one = one[~one.index.duplicated()]
    one['bad'] = False
    return one


def table(s, cost, split, label):
    R = lambda y, nm: print(f'   {nm:<26} ' + mm.row_ind(y, cost, split))
    print(f'\n  ## {label}')
    print(f'   {"":<26}   筆數   1R 勝率 每筆   2R 勝率 每筆   3R 勝率 每筆')
    R(s, '全部')
    for nm in ('flip', 'gex', 'open'):
        a, b = s[f'SPY_{nm}'], s[f'QQQ_{nm}']
        if a.isna().mean() > 0.2: continue                                 # net GEX samples only cover part of the period
        lab = {'flip': '價格 vs gamma flip（當下）', 'gex': 'net GEX 正負（當下）', 'open': '價格 vs gamma flip（開盤）'}[nm]
        print(f'   — {lab}')
        both_p, both_n = (a > 0) & (b > 0), (a < 0) & (b < 0); mix = (a * b < 0)
        for gn, g in (('都正', both_p), ('都負', both_n), ('一正一負', mix)):
            R(s[g], f'{gn}（{g.sum()}）')
            R(s[g & (s.side == 1)], f'　{gn}，買')
            R(s[g & (s.side == -1)], f'　{gn}，賣')


def seq_rows(s, cost, years_frac, split):
    def line(y, R):
        t = ss.seq(y.sort_values('i'), R)
        if len(t) == 0: return '   0'
        n = t[f'r{R:g}'].values - cost / t.risk.values; eq = np.cumsum(n)
        dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
        mo = pd.Series(n).groupby(t.date.str[:7].values).sum()
        return (f'{len(t):4d} 筆  勝率 {100 * (n > 0).mean():4.1f}%  每筆 {n.mean():+.3f}R  合計 {n.sum():+6.1f}R  回撤 {dd:5.1f}R'
                f'  每月 ' + ' '.join(f'{v:+.0f}' for v in mo.values))
    a, b = s.SPY_flip, s.QQQ_flip
    both_p, both_n = (a > 0) & (b > 0), (a < 0) & (b < 0)
    rule = (both_p) | (both_n & (s.side == -1))
    print('  一次一筆（Remi 的規則：都正做買賣、都負只做賣、其他不做；用當下的 flip）')
    for R in (1.0, 2.0, 3.0):
        print(f'   {R:g}R 原版全部            ' + line(s, R))
        print(f'   {R:g}R 原版 + GEX 規則      ' + line(s[rule], R))
        print(f'   {R:g}R v3                  ' + line(s[s.v3], R))
        print(f'   {R:g}R v3 + GEX 規則        ' + line(s[s.v3 & rule], R))


def run(name, one, cost, th, st, nd, start, end, stage=35, ema=8):
    tdm = mm.minute_trend(one); H = mm.hourly(one, True)
    df = mm.chart(one, tdm, 1, th, st)
    s = mm.trend_signals(df, H, 1, stage, ema)
    late = s.date.values > '2026-10-14'                                    # no NQ data after this: NQ 2m filter off
    s['v3'] = mm.filt(s, th, 7.0) & (sg.nq_ok(df, s, nd) | late)
    s = s[(s.date >= start) & (s.date <= end)].copy()
    s = pd.concat([s, regimes(df, s)], axis=1)
    d = sorted(s.date.unique()); split = d[len(d) // 2]
    print(f'\n################ ({stage}, 0, {ema}, 1) {name}：{d[0]} .. {d[-1]}（{len(d)} 天），原版訊號 {len(s)} 個、v3 留下 {int(s.v3.sum())} 個，'
          f'每筆扣 {cost:g}；前 / 後 = 前後各半的日期')
    have = s.SPY_flip.notna() & s.QQQ_flip.notna()
    print(f'  有 gamma 資料的訊號 {have.mean():.0%}')
    table(s, cost, split, f'原版 ({stage}, 0, {ema}, 1) 全部')
    table(s[s.v3], cost, split, 'v3 留下的')
    seq_rows(s, cost, None, split)


def main():
    stage, ema = (int(x) for x in (sys.argv[1] if len(sys.argv) > 1 else '35,8').split(','))
    nd = sg.nq2m_dir()
    m = zg_minute('QQQ')
    start = str(m.ts.dt.tz_convert(ss.NY).dt.date.min()); end = '2026-10-14'
    run('QQQ 1 分 K（NQ 美股盤代替）', mm.load_market('qqq', []), 1.0, 20.0, 40.0, nd, start, end, stage, ema)
    one = real_qqq()
    days = sorted(set(one.index.tz_convert(ss.NY).date))
    run('QQQ 1 分 K（ZeroGEX 的 QQQ 實際 K 棒）', one, 0.024, 0.5, 1.0, nd, str(days[3]), str(days[-1]), stage, ema)


if __name__ == '__main__':
    main()
