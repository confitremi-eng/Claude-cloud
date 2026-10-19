"""When do QQQ 1-minute original triangles (30, 0, 8, 1) work? Split by things known at the signal.

  cd indicators/backtest
  python3 -I rbs/qqq_3008_when.py [--check]      # --check: also (25 / 35, 0, 8, 1) and the real QQQ candles
  python3 -I rbs/qqq_3008_when.py --gex [8,13]    # the ZeroGEX months: direction against the gamma flip, room to the wall (EMA list)

Prompted by 2026-10-19: QQQ gapped up ~1.3%, dipped under the opening range low in the first half hour, and the
buy triangle there ran ~3R. Every original signal (no filter), each on its own (signal close entry, two-bar stop,
60-bar exit or the session end, 1 NQ point cost), split by
  開盤後幾分鐘   minutes from 09:30 ET to the signal close
  跳空           today's open vs the previous close, %, on the trade's side (+ = gap the trade's way)
  當天已走       signal close vs today's open, %, on the trade's side
  開盤區間       the first 15 / 30 minutes' high and low: signal after price broke the far side and came back
                 (buy: went under the low, now back above it), still beyond it, inside, or beyond the near side
  Trend Judge    QQQ (threshold 20 NQ points = QQQ 0.5) and NQ 2m against the trade: same / MIX / against
Main data: NQ cash-session bars (the QQQ stand-in), the Databento year; check: ZeroGEX's real QQQ candles (73 days)
and the neighbouring settings (25 / 35, 0, 8, 1). 前 / 後 = the two halves of the dates.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import strong_stage as sg
import gex_qqq as gq
import qqq_3008 as q3
import gex_trend as gt


def day_feats(df, s):
    et = (df.datetime + pd.Timedelta(minutes=1)).dt.tz_convert(ss.NY)          # bar close time
    day = et.dt.date.values
    mins = (et.dt.hour * 60 + et.dt.minute - 570).values
    o, h, l, c = df.open.values, df.high.values, df.low.values, df.close.values
    g = pd.DataFrame({'day': day, 'o': o, 'h': h, 'l': l, 'c': c, 'mins': mins})
    first_open = g.groupby('day').o.transform('first').values
    last_close = g.groupby('day').c.last()
    prev_close = pd.Series(last_close.shift(1).values, index=last_close.index).reindex(day).values
    lo_sofar = g.groupby('day').l.cummin().values
    hi_sofar = g.groupby('day').h.cummax().values
    out = {}
    for orm in (15, 30):
        inside = g.mins <= orm
        orh = g.h.where(inside).groupby(g.day).transform('max').values
        orl = g.l.where(inside).groupby(g.day).transform('min').values
        out[orm] = (orh, orl)
    i = s.i.values; k = s.side.values; ci = c[i]
    f = pd.DataFrame(index=s.index)
    f['mins'] = mins[i]
    f['gap'] = (first_open[i] - prev_close[i]) / prev_close[i] * 100 * k
    f['moved'] = (ci - first_open[i]) / first_open[i] * 100 * k
    for orm, (orh, orl) in out.items():
        far = np.where(k == 1, orl[i], orh[i]); near = np.where(k == 1, orh[i], orl[i])
        swept = np.where(k == 1, lo_sofar[i] < orl[i], hi_sofar[i] > orh[i])
        beyond_far = np.where(k == 1, ci < orl[i], ci > orh[i])
        beyond_near = np.where(k == 1, ci > orh[i], ci < orl[i])
        st = np.where(mins[i] <= orm, '區間還沒成形',
             np.where(beyond_far, '還在區間外（逆向那邊）',
             np.where(swept & ~beyond_far & ~beyond_near, '假突破後收回區間',
             np.where(beyond_near, '已突破順向那邊', '一直在區間內'))))
        f[f'or{orm}'] = st
    return f


def build(df, H, stage, nd):
    s = mm.trend_signals(df, H, 1, stage, 8)
    s['qtj'] = np.sign(s.dir.values) * s.side.values
    s['nq'] = q3.nq_rel(df, s, nd)
    return pd.concat([s, day_feats(df, s)], axis=1)


def report(s, cost, split, title):
    R = lambda y, nm: print(f'   {nm:<26} ' + mm.row_ind(y, cost, split))
    print(f'\n  ## {title}')
    print(f'   {"":<26}   筆數   1R 勝率 每筆   2R 勝率 每筆   3R 勝率 每筆')
    R(s, '全部')
    print('   開盤後（分鐘）')
    for lo, hi in ((0, 30), (30, 60), (60, 120), (120, 270), (270, 391)):
        R(s[(s.mins > lo) & (s.mins <= hi)], f'{lo}–{hi}')
    print('   跳空（順著交易方向，%）')
    for lo, hi in ((-99, -0.5), (-0.5, -0.15), (-0.15, 0.15), (0.15, 0.5), (0.5, 99)):
        R(s[(s.gap >= lo) & (s.gap < hi)], f'{"" if lo == -99 else format(lo, "+g")}～{"" if hi == 99 else format(hi, "+g")}%')
    print('   當天已走（從開盤，順著交易方向，%）')
    for lo, hi in ((-99, -0.5), (-0.5, 0), (0, 0.5), (0.5, 99)):
        R(s[(s.moved >= lo) & (s.moved < hi)], f'{"" if lo == -99 else format(lo, "+g")}～{"" if hi == 99 else format(hi, "+g")}%')
    for orm in (15, 30):
        print(f'   開盤 {orm} 分鐘區間')
        for st in ('區間還沒成形', '假突破後收回區間', '還在區間外（逆向那邊）', '一直在區間內', '已突破順向那邊'):
            R(s[s[f'or{orm}'] == st], st)
    print('   Trend Judge')
    for v, nm in ((1, '同向'), (0, 'MIX'), (-1, '逆向')):
        R(s[s.qtj == v], f'QQQ {nm}')
    for v, nm in ((1, '同向'), (0, 'MIX'), (-1, '逆向')):
        R(s[s.nq == v], f'NQ 2m {nm}')
    print('   組合（像 10/19 那筆）')
    early = s.mins <= 60; gapw = s.gap >= 0.5; sw = s.or15 == '假突破後收回區間'
    R(s[early & gapw], '開盤 60 分內 + 順向跳空 ≥ 0.5%')
    R(s[sw & gapw], '假突破收回（15 分）+ 順向跳空 ≥ 0.5%')
    R(s[early & sw], '開盤 60 分內 + 假突破收回')
    R(s[early & sw & gapw], '三個都有')
    R(s[early & (s.gap >= 0.15)], '開盤 60 分內 + 順向跳空 ≥ 0.15%')
    R(s[early & (s.gap < -0.15)], '開盤 60 分內 + 逆向跳空')


def run(name, one, cost, th, st, nd, start, end, stages=(30,)):
    tdm = mm.minute_trend(one); H = mm.hourly(one, True)
    df = mm.chart(one, tdm, 1, th, st)
    print(f'\n################ {name}')
    for stage in stages:
        s = build(df, H, stage, nd)
        s = s[(s.date >= start) & (s.date <= end)]
        d = sorted(s.date.unique()); split = d[len(d) // 2]
        for side, nm in ((1, '買'), (-1, '賣')):
            report(s[s.side == side], cost, split, f'({stage}, 0, 8, 1) {nm}：{d[0]} .. {d[-1]}，每筆扣 {cost:g}')


def gex_check(emas=(8,), cost_nq=1.0):
    """The ZeroGEX months: (30, 0, EMA, 1) by the trade's direction against QQQ's gamma flip and the room to the wall,
    on NQ cash-session bars and on ZeroGEX's real QQQ candles; then the setup (QQQ 順勢 + 朝 flip 走) one at a time."""
    one_nq = mm.load_market('qqq', []); one_q = gq.real_qqq()
    days = sorted(set(one_q.index.tz_convert(ss.NY).date))
    srcs = (('NQ 代替', one_nq, 1.0, 20.0, 40.0, '2026-06-29', '2026-10-14'),
            ('QQQ 實際 K 棒', one_q, 0.024, 0.5, 1.0, str(days[3]), str(days[-1])))
    for nm, one, cost, th, st, start, end in srcs:
        tdm = mm.minute_trend(one); H = mm.hourly(one, True); df = mm.chart(one, tdm, 1, th, st)
        for ema in emas:
            s = mm.trend_signals(df, H, 1, 30, ema); s = s[(s.date >= start) & (s.date <= end)].copy()
            s = pd.concat([s, gt.feats(df, s)], axis=1); s = s[s.QQQ_flip.notna()]
            d = sorted(s.date.unique()); split = d[len(d) // 2]
            R = lambda y, lab: print(f'   {lab:<26} ' + mm.row_ind(y, cost, split))
            print(f'\n################ (30, 0, {ema}, 1) × QQQ gamma flip（{nm}，{d[0]} .. {d[-1]}，{len(d)} 天，每筆扣 {cost:g}）')
            print(f'   {"":<26}   筆數   1R 勝率 每筆   2R 勝率 每筆   3R 勝率 每筆')
            tr = np.sign(s.dir) * s.side > 0; tw = s.flip_d < 0
            for side, sn in ((1, '買'), (-1, '賣')):
                z = s.side == side
                print(f'  ## {sn}（朝 flip 走 = {"買在 flip 下面" if side == 1 else "賣在 flip 上面"}）')
                R(s[z], '全部'); R(s[z & tw], '朝 flip 走'); R(s[z & ~tw], '離開 flip')
                R(s[z & tr], 'QQQ 順勢'); R(s[z & tr & tw], 'QQQ 順勢 + 朝 flip 走'); R(s[z & tr & ~tw], 'QQQ 順勢 + 離開 flip')
                R(s[z & (s.room_R < 1)], '到牆不到 1 倍停損'); R(s[z & tw & (s.room_R >= 1)], '朝 flip 走 + 到牆 ≥ 1 倍')
            print('  ## 買賣合起來')
            R(s[tr & tw], 'QQQ 順勢 + 朝 flip 走')
            yrs = len(d) / 252
            for Rr in (1.0, 2.0, 3.0):
                t = ss.seq(s[tr & tw].sort_values('i'), Rr)
                n = t[f'r{Rr:g}'].values - cost / t.risk.values; eq = np.cumsum(n)
                dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq) if len(eq) else 0
                print(f'   一次一筆 {Rr:g}R：{len(t)} 筆  勝率 {100 * (n > 0).mean():4.1f}%  每筆 {n.mean():+.3f}R  合計 {n.sum():+5.1f}R  回撤 {dd:4.1f}R')


def main():
    if '--gex' in sys.argv:
        k = sys.argv.index('--gex')
        emas = tuple(int(x) for x in sys.argv[k + 1].split(',')) if len(sys.argv) > k + 1 else (8,)
        gex_check(emas)
        return
    nd = sg.nq2m_dir()
    run('QQQ 1 分 K（NQ 美股盤代替，一年）', mm.load_market('qqq', []), 1.0, 20.0, 40.0, nd, '2025-10-20', '2026-10-14')
    if '--check' in sys.argv:
        run('QQQ 1 分 K（NQ 代替）：附近的參數', mm.load_market('qqq', []), 1.0, 20.0, 40.0, nd, '2025-10-20', '2026-10-14', (25, 35))
        one = gq.real_qqq(); days = sorted(set(one.index.tz_convert(ss.NY).date))
        run('QQQ 1 分 K（ZeroGEX 的 QQQ 實際 K 棒）', one, 0.024, 0.5, 1.0, nd, str(days[3]), '2026-10-16')


if __name__ == '__main__':
    main()
