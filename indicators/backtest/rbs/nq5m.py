"""When is NQ 5 / 10 / 15 minutes worth trading with the Remi Superb rules? (Databento year)

  cd indicators/backtest
  python3 -I rbs/nq5m.py [分鐘 ...]        # default 5; e.g. python3 -I rbs/nq5m.py 10 15
  python3 -I rbs/nq5m.py 10 15 --stages   # shorter 「階段」 on 10 / 15 minutes

Trend signals = the filtered alerts on the chart (Trend Judge 有趨勢 > 10, 1-hour EMA20 side, stop >= 1 ATR,
close - 15 s EMA1130 <= 3 ATR, event windows avoided; two-bar stop, 60-bar time exit like the indicator, 1 point cost),
split by the indicator's trend minutes, New York session, side, Trend Judge strength (強 > 35) and target.
MIX breakout = MIX box of 60 (or 120) minutes, first 10% break within the same time, stop order, stop at the middle,
time exit after 2 hours or 60 bars.
Combinations one position at a time, against NQ 2 minutes (v3) for reference. 前 / 後 = the two halves of the dates.
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

COST, TH, ST = 1.0, 10.0, 35.0


def session(df, i, tf):
    e = (df.datetime + pd.Timedelta(minutes=tf)).dt.tz_convert(ss.NY).values[i]
    m = pd.DatetimeIndex(e).hour * 60 + pd.DatetimeIndex(e).minute
    return np.select([(m >= 570) & (m < 960), (m >= 1200) | (m < 180), m < 570], ['美股盤 09:30–16', '亞洲盤 20–03', '歐洲盤 03–09:30'], '收盤後 16–20')


def run(tf, one, tdm, H, years):
    df = mm.chart(one, tdm, tf, TH, ST)
    s = mm.trend_signals(df, H, tf)
    F = s[mm.filt(s, TH)].copy()
    d = sorted(s.date.unique()); split = d[len(d) // 2]
    F['sess'] = session(df, F.i.values, tf)
    F['strong'] = F.spread > ST
    print(f'\n################ NQ {tf} 分 K：{one.index[0]:%Y-%m-%d} .. {one.index[-1]:%Y-%m-%d}，過濾後的趨勢訊號 {len(F)} 個（原版訊號 {len(s)} 個），每筆扣 1 點')
    print(f'{"":<24}   筆數   1R 勝率 每筆   2R 勝率 每筆   3R 勝率 每筆')
    print('\n######## 1. 趨勢訊號（各自獨立）')
    rows = [('全部', F.side != 0)]
    for lo, hi in ((0, 60), (60, 120), (120, 180), (180, 240), (240, 360), (360, 10 ** 6), (0, 120), (0, 180), (0, 360)):
        rows.append((f'趨勢 {lo}–{hi if hi < 10 ** 6 else "以上"} 分', (F.tm >= lo) & (F.tm < hi)))
    for k in ('美股盤 09:30–16', '亞洲盤 20–03', '歐洲盤 03–09:30', '收盤後 16–20'):
        rows.append((k, F.sess == k))
    rows += [('作多', F.side == 1), ('做空', F.side == -1), ('強趨勢（差值 > 35）', F.strong), ('一般趨勢（10–35）', ~F.strong)]
    for nm, m in rows:
        print(f'   {nm:<22} ' + mm.row_ind(F[m], COST, split))

    print('\n######## 2. MIX 區間突破（掛突破單）')
    mr.TF, mr.TH, mb.COST = tf, TH, COST
    rbs._cache[('NQ', tf)] = df
    B = mr.load()
    for box_min in (60, 120):
        W = max(1, round(box_min / tf)); bx = mb.causal_boxes(B, W, grace=max(0, round(4 / tf)))
        for hold in (max(1, round(120 / tf)), 60):
            mr.HOLD = hold
            bo = {R: mb.breakouts(B, bx, R, max_age=W, entry='stop') for R in (1.0, 2.0, 3.0)}
            if len(bo[1.0]) == 0: continue
            M = bo[1.0][['i', 'side', 'risk', 'date']].copy()
            for R in (1.0, 2.0, 3.0): M[f'r{R:g}'] = bo[R]['R'].values
            print(f'   {"區間 " + str(box_min) + " 分，持有 " + str(hold) + " 根":<22} ' + mm.row_ind(M, COST, split))
    mr.HOLD = 60
    W = max(1, round(60 / tf)); boxes = mb.causal_boxes(B, W, grace=max(0, round(4 / tf)))

    print('\n######## 3. 一次一筆（每年）')
    h, l = df.high.values, df.low.values
    et = (df.datetime + pd.Timedelta(minutes=tf)).dt.tz_convert(ss.NY)
    halt = ((et.dt.hour * 60 + et.dt.minute) == 1020).values
    mix = {}
    hb, lb, ob, hole, evt = B['h'], B['l'], B['o'], B['hole'], B['evt']; n = len(hb)
    for s0, fm, top, bot in boxes:
        Hh = top - bot
        if Hh <= 0: continue
        bu, bd, mid = top + 0.1 * Hh, bot - 0.1 * Hh, (top + bot) / 2
        for j in range(fm + 1, min(fm + W, n - 1) + 1):
            if hole[j]: break
            up, dn = hb[j] >= bu, lb[j] <= bd
            if not (up or dn): continue
            if (up and dn) or evt[j]: break
            k = 1 if up else -1
            mix[j] = (k, max(ob[j], bu) if k == 1 else min(ob[j], bd), mid)
            break
    rbs._cache.pop(('NQ', tf), None)
    def ce(z):
        return {int(i): (int(k), (min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])), '趨勢') for i, k in zip(z.i, z.side)}
    combos = [('趨勢全部', ce(F), {}), ('趨勢 0–120 分', ce(F[F.tm < 120]), {}), ('趨勢 0–180 分', ce(F[F.tm < 180]), {}),
              ('MIX 突破', {}, mix), ('趨勢 0–180 分 + MIX', ce(F[F.tm < 180]), mix), ('趨勢全部 + MIX', ce(F), mix)]
    for R in (1.0, 2.0, 3.0):
        for nm, c_, m_ in combos:
            t = tfw.simulate(df, c_, m_, R, COST, halt)
            print(f'   {R:g}R {nm:<18} ' + tfw.seq_line(t, years))


def stages(tf, one, tdm, H, years):
    """Shorter 「階段」 so the swing spans about as long as 20 bars on 2 minutes, with EMA 8 or scaled."""
    df = mm.chart(one, tdm, tf, TH, ST)
    h, l = df.high.values, df.low.values
    et = (df.datetime + pd.Timedelta(minutes=tf)).dt.tz_convert(ss.NY)
    halt = ((et.dt.hour * 60 + et.dt.minute) == 1020).values
    print(f'\n######## NQ {tf} 分 K，換「階段」（過濾條件同上，各自獨立；一次一筆每年）')
    print(f'{"":<24}   筆數   1R 勝率 每筆   2R 勝率 每筆   3R 勝率 每筆')
    for stage in sorted({max(2, round(40 / tf)), max(2, round(80 / tf)), max(2, round(120 / tf)), 10, 20}):
        for ema in (8, max(2, round(16 / tf))):
            s = mm.trend_signals(df, H, tf, stage, ema)
            F = s[mm.filt(s, TH)]
            if len(F) == 0: continue
            d = sorted(s.date.unique()); split = d[len(d) // 2]
            print(f'   ({stage}, 0, {ema}, 1) 全部        ' + mm.row_ind(F, COST, split))
            G = F[F.tm < 180]
            if len(G): print(f'   ({stage}, 0, {ema}, 1) 趨勢 0–180  ' + mm.row_ind(G, COST, split))
            for R in (2.0, 3.0):
                ce = {int(i): (int(k), (min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])), '趨勢') for i, k in zip(F.i, F.side)}
                print(f'      一次一筆 {R:g}R 全部     ' + tfw.seq_line(tfw.simulate(df, ce, {}, R, COST, halt), years))


def main():
    tfs = [int(a) for a in sys.argv[1:] if a != '--stages'] or [5]
    one = mm.load_market('nq', [])
    tdm = mm.minute_trend(one); H = mm.hourly(one, False)
    years = (one.index[-1] - one.index[0]).days / 365.25
    for tf in tfs:
        if '--stages' in sys.argv:
            stages(tf, one, tdm, H, years)
        else:
            run(tf, one, tdm, H, years)


if __name__ == '__main__':
    main()
