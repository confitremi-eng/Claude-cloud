"""Where do TXF 3- and 5-minute charts have trading value with the Remi Superb rules? (TXFR1 2024-01 .. 2026-09)

  cd indicators/backtest
  python3 -I rbs/txf_tf.py data_TXFR1_2024.sql data_TXFR1_2025.sql data_TXFR1_2026.sql [--tf 3,5]
  python3 -I rbs/txf_tf.py ...sql --candidates     # the three positive-looking 3m groups, year by year

Trend signals = filtered alerts on the chart: Trend Judge 有趨勢 (spread > 30 points), 1-hour EMA20 side (clock
hours), stop >= 1 ATR, close - 15 s EMA1130 <= 3 ATR, New York event windows avoided; two-bar stop, 60-bar time
exit, flat before a session break; front-month roll days skipped. Split by the indicator's trend minutes, TXF
session (day 08:45-13:45, night with / without the US cash session), side, Trend Judge strength (> 60), calendar
year; signal settings (20, 0, 8, 1) and (35, 0, 8, 1). MIX breakout = 60-minute MIX box, first 10% break within 60
minutes, stop order, stop at the middle. Costs: 2 points (optimistic) and 4 points (tax + fees + slippage, closer
to real). Signals on their own; the best ones also one position at a time, per year.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import mix_range as mr
import mix_breakout as mb
import market_matrix as mm
import trend_follow as tfw

TH, ST = 30.0, 60.0
COSTS = (2.0, 4.0)


def sess_of(df, i, tf):
    t = (df.datetime + pd.Timedelta(minutes=tf)).values[i]
    tw = pd.DatetimeIndex(t).tz_localize('UTC').tz_convert('Asia/Taipei'); m = tw.hour * 60 + tw.minute
    et = pd.DatetimeIndex(t).tz_localize('UTC').tz_convert(ss.NY); me = et.hour * 60 + et.minute
    return np.where((m >= 525) & (m <= 825), '日盤 08:45–13:45',
                    np.where((me >= 570) & (me < 960), '夜盤·美股盤中', '夜盤·其他'))


def row(y, split):
    if len(y) == 0: return '   0'
    a = y.date.values < split; out = []
    for R in (1.0, 2.0, 3.0):
        r = y[f'r{R:g}'].values; nn = r - COSTS[0] / y.risk.values
        out.append(f'{100 * (r > 0).mean():4.1f}% {nn.mean():+.3f}')
    r3 = y['r3'].values; n2 = r3 - COSTS[0] / y.risk.values; n4 = r3 - COSTS[1] / y.risk.values
    ok = '✓' if (n2[a].mean() > 0 and n2[~a].mean() > 0) else '✗'
    return f'{len(y):5d}  ' + '  '.join(out) + f'   3R 前/後 {n2[a].mean():+.2f}/{n2[~a].mean():+.2f} {ok}  成本 4 點 3R {n4.mean():+.3f}'


def run(tf, one, tdm, H, years):
    df = mm.chart(one, tdm, tf, TH, ST)
    split_all = None
    print(f'\n################ TXF {tf} 分 K（每筆成本 2 點；最後一欄是 4 點）')
    print(f'{"":<26}   筆數   1R 勝率 每筆   2R 勝率 每筆   3R 勝率 每筆')
    best = {}
    for stage in (20, 35):
        s = mm.trend_signals(df, H, tf, stage, 8)
        F = s[mm.filt(s, TH)].copy()
        d = sorted(s.date.unique()); split = d[len(d) // 2]; split_all = split
        F['sess'] = sess_of(df, F.i.values, tf)
        F['year'] = F.date.str[:4]
        print(f'\n  ## 訊號 ({stage}, 0, 8, 1)：原版 {len(s)} 個，過濾後 {len(F)} 個')
        rows = [('全部', F.side != 0)]
        for lo, hi in ((0, 60), (60, 120), (120, 180), (180, 300), (300, 10 ** 6), (0, 180), (60, 180)):
            rows.append((f'趨勢 {lo}–{hi if hi < 10 ** 6 else "以上"} 分', (F.tm >= lo) & (F.tm < hi)))
        for k in ('日盤 08:45–13:45', '夜盤·美股盤中', '夜盤·其他'):
            rows.append((k, F.sess == k))
        rows += [('作多', F.side == 1), ('做空', F.side == -1), ('強趨勢（> 60）', F.spread > ST)]
        for y_ in sorted(F.year.unique()):
            rows.append((f'{y_} 年', F.year == y_))
        for nm, m in rows:
            print(f'   {nm:<24} ' + row(F[m], split))
        best[stage] = F
    # MIX breakout
    print('\n  ## MIX 區間突破（60 分鐘區間，掛突破單）')
    mr.TF, mr.TH, mb.COST = tf, TH, COSTS[0]
    rbs._cache[('NQ', tf)] = df
    B = mr.load(); W = max(1, round(60 / tf)); boxes = mb.causal_boxes(B, W, grace=max(0, round(4 / tf)))
    for hold in (max(1, round(120 / tf)), 60):
        mr.HOLD = hold
        bo = {R: mb.breakouts(B, boxes, R, max_age=W, entry='stop') for R in (1.0, 2.0, 3.0)}
        M = bo[1.0][['i', 'side', 'risk', 'date']].copy()
        for R in (1.0, 2.0, 3.0): M[f'r{R:g}'] = bo[R]['R'].values
        M['sess'] = sess_of(df, M.i.values, tf)
        print(f'   {"持有 " + str(hold) + " 根":<24} ' + row(M, split_all))
        if hold == 60:
            for k in ('日盤 08:45–13:45', '夜盤·美股盤中', '夜盤·其他'):
                print(f'   　{k:<22} ' + row(M[M.sess == k], split_all))
    mr.HOLD = 60
    rbs._cache.pop(('NQ', tf), None)
    # one at a time for a few candidates
    print('\n  ## 一次一筆（每年，成本 2 點 / 4 點）')
    h, l = df.high.values, df.low.values
    nohalt = np.zeros(len(df), bool)
    for stage, F in best.items():
        for nm, m in (('全部', F.side != 0), ('趨勢 60–180 分', (F.tm >= 60) & (F.tm < 180)), ('趨勢 0–180 分', F.tm < 180),
                      ('夜盤', F.sess != '日盤 08:45–13:45'), ('夜盤，趨勢 0–180 分', (F.sess != '日盤 08:45–13:45') & (F.tm < 180))):
            z = F[m]
            ce = {int(i): (int(k), (min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])), '趨勢') for i, k in zip(z.i, z.side)}
            for R in (2.0, 3.0):
                t2 = tfw.simulate(df, ce, {}, R, COSTS[0], nohalt)
                t4 = t2.assign(net=t2.R - COSTS[1] / t2.risk)
                print(f'   ({stage},0,8,1) {nm:<16} {R:g}R  ' + tfw.seq_line(t2, years) + f'  | 4 點：每筆 {t4.net.mean():+.3f}R 每年 {t4.net.sum() / years:+.1f}R')


def candidates(one, tdm, H):
    """The three 3-minute groups that looked positive, year by year (each signal on its own, and one at a time)."""
    tf = 3
    df = mm.chart(one, tdm, tf, TH, ST)
    h, l = df.high.values, df.low.values
    nohalt = np.zeros(len(df), bool)
    s20 = mm.trend_signals(df, H, tf, 20, 8); F20 = s20[mm.filt(s20, TH)].copy()
    s35 = mm.trend_signals(df, H, tf, 35, 8); F35 = s35[mm.filt(s35, TH)].copy()
    F35['sess'] = sess_of(df, F35.i.values, tf)
    groups = [('(20,0,8,1) 趨勢 60–120 分', F20[(F20.tm >= 60) & (F20.tm < 120)]),
              ('(35,0,8,1) 趨勢 300 分以上', F35[F35.tm >= 300]),
              ('(35,0,8,1) 夜盤·美股盤中', F35[F35.sess == '夜盤·美股盤中'])]
    print('\n######## TXF 3 分 K 的三組候選，逐年（3R；各自獨立 / 一次一筆；成本 2 點、4 點）')
    for nm, z in groups:
        print(f'  ## {nm}')
        ce = {int(i): (int(k), (min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])), '趨勢') for i, k in zip(z.i, z.side)}
        t = tfw.simulate(df, ce, {}, 3.0, COSTS[0], nohalt)
        for y_ in ('2024', '2025', '2026'):
            zy = z[z.date.str[:4] == y_]; ty = t[t.date.str[:4] == y_]
            if len(zy) == 0: continue
            r = zy.r3.values
            n2 = r - COSTS[0] / zy.risk.values; n4 = r - COSTS[1] / zy.risk.values
            print(f'     {y_}  {len(zy):3d} 筆  勝率 {100 * (r > 0).mean():4.1f}%  每筆 {n2.mean():+.3f}R（4 點 {n4.mean():+.3f}R）'
                  f'  | 一次一筆 {len(ty):3d} 筆 合計 {ty.net.sum():+5.1f}R（4 點 {(ty.R - COSTS[1] / ty.risk).sum():+5.1f}R）')


def main():
    args = sys.argv[1:]
    if '--candidates' in args:
        args.remove('--candidates')
        one = mm.load_market('txf', args); tdm = mm.minute_trend(one); H = mm.hourly(one, False)
        candidates(one, tdm, H)
        return
    tfs = [3, 5]
    if '--tf' in args:
        k = args.index('--tf'); tfs = [int(x) for x in args[k + 1].split(',')]; del args[k:k + 2]
    one = mm.load_market('txf', args)
    tdm = mm.minute_trend(one); H = mm.hourly(one, False)
    years = (one.index[-1] - one.index[0]).days / 365.25
    print(f'TXF：{one.index[0]:%Y-%m-%d} .. {one.index[-1]:%Y-%m-%d}（{years:.1f} 年）')
    for tf in tfs:
        run(tf, one, tdm, H, years)


if __name__ == '__main__':
    main()
