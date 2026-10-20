"""Autotrade with both NQ 2-minute and 5-minute v3 sharing one MNQ position (the Databento year).

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 -I rbs/combo_2m5m.py

Each chart's TradingView strategy runs on its own (v3 defaults, one trade at a time: 2 minutes 3R, 5 minutes 2R,
trend signals + MIX breakout, Friday cut-off, no MIX New York 16-20). autotrade takes a trade only when it is flat;
while it holds one chart's trade, the other chart's entries and exits are ignored ("whoever enters first owns the
position"). Entry / exit times are refined to the 1-minute bar (MIX stop entries, stop / target hits). Same-minute
ties go to 2 minutes. Results in points for a fixed 2 MNQ (1 point cost per trade), since autotrade does not size
by R; R is shown too.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import market_matrix as mm
import mix_opt as mo

COST, MNQ_USD, QTY = 1.0, 2.0, 2


def v3_trades(C, R, one):
    """mix_opt.sim2 with v3 defaults, keeping entry / exit times."""
    tw = (C.df.datetime + pd.Timedelta(minutes=C.tf)).dt.tz_convert('Asia/Taipei')
    late = ((tw.dt.weekday == 5) & (tw.dt.hour * 60 + tw.dt.minute >= 120)).values
    mix = {j: (k, px, st) for j, k, px, st, info in mo.breaks(C, mo.boxes(C)) if info['sess'] != '收盤後 16-20'}
    h, l, c = C.h, C.l, C.c
    t0 = C.df.datetime.values; lastm = pd.DatetimeIndex(C.df.last_min).values
    holeb = np.r_[False, (C.df.datetime.diff() > pd.Timedelta(minutes=30)).values[1:]]
    trad = C.df.tradable.values
    oh, ol, oi = one.high.values, one.low.values, one.index.values
    step = pd.Timedelta(minutes=1).to_timedelta64()
    close_t = lambda j: lastm[j] + step

    def touch(j, px, up):
        """End of the first 1-minute bar inside chart bar j that reaches px."""
        a, b = np.searchsorted(oi, t0[j]), np.searchsorted(oi, lastm[j], side='right')
        hit = np.nonzero(oh[a:b] >= px)[0] if up else np.nonzero(ol[a:b] <= px)[0]
        return oi[a + hit[0]] + step if len(hit) else close_t(j)

    out = []; pos = 0
    for j in range(len(c)):
        if pos != 0 and j > vb:
            hs = (l[j] <= vs) if pos == 1 else (h[j] >= vs)
            ht = (h[j] >= vt) if pos == 1 else (l[j] <= vt)
            if hs or ht or j - vb >= 60 or C.halt[j] or holeb[j]:
                if hs or ht:
                    px = vs if hs else vt
                    xt = touch(j, px, (pos == 1) != hs)
                elif holeb[j]:
                    px, xt = c[j - 1], close_t(j - 1)
                else:
                    px, xt = c[j], close_t(j)
                out.append((kind, pos, ve, px, abs(ve - vs), et, xt, C.date[vb])); pos = 0
        if not trad[j] or late[j] or C.halt[j]:
            continue
        if pos == 0 and j in mix:
            k, px, st = mix[j]
            pos, ve, vs, vt, vb, kind = k, px, st, px + R * (px - st), j, 'MIX'
            et = touch(j, px, k == 1)
            if (pos == 1 and l[j] <= vs) or (pos == -1 and h[j] >= vs):
                out.append((kind, pos, ve, vs, abs(ve - vs), et, close_t(j), C.date[j])); pos = 0
        if pos == 0 and j in C.trend:
            k, st, kd = C.trend[j]
            pos, ve, vs, vt, vb, kind, et = k, c[j], st, c[j] + R * (c[j] - st), j, kd, close_t(j)
    t = pd.DataFrame(out, columns=['kind', 'side', 'entry', 'exit', 'risk', 'et', 'xt', 'date'])
    t['tf'] = C.tf
    t['R'] = (t.exit - t.entry) * t.side / t.risk
    t['net'] = t.R - COST / t.risk                     # R after cost, like mix_opt
    t['pts'] = (t.exit - t.entry) * t.side - COST      # points per contract after cost
    return t


def combine(a, b):
    """First come owns the position; ties to the first frame (2 minutes)."""
    t = pd.concat([a.assign(pri=0), b.assign(pri=1)]).sort_values(['et', 'pri'], kind='stable')
    keep, busy = [], np.datetime64('1970-01-01')
    for r in t.itertuples():
        if r.et >= busy:
            keep.append(True); busy = r.xt
        else:
            keep.append(False)
    t = t.assign(taken=keep)
    return t[t.taken].drop(columns=['pri', 'taken']).reset_index(drop=True), t[~t.taken]


def line(t, years, split):
    if len(t) == 0:
        return '   0'
    p = t.pts.values; eq = np.cumsum(p); dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
    mo_ = pd.Series(p).groupby(t.date.str[:7].values).sum()
    a = t.date.values < split
    usd = QTY * MNQ_USD
    return (f'{len(t) / years:5.0f} 筆/年  勝率 {100 * (t.R > 0).mean():4.1f}%  每年 {p.sum() / years:+7.0f} 點'
            f'（2 口 {usd * p.sum() / years:+7,.0f} 美元）  回撤 {dd:5.0f} 點（{usd * dd:,.0f} 美元）'
            f'  前/後 {p[a].sum() / years * 2:+.0f}/{p[~a].sum() / years * 2:+.0f} 點/年'
            f'  賺錢月份 {(mo_ > 0).sum()}/{len(mo_)}  每年 {t.net.sum() / years:+.0f}R')


def main():
    one = mm.load_market('nq', [])
    tdm = mm.minute_trend(one); H = mm.hourly(one, False)
    C2, C5 = mo.Ctx(2, one, tdm, H), mo.Ctx(5, one, tdm, H)
    t2, t5 = v3_trades(C2, 3.0, one), v3_trades(C5, 2.0, one)
    years, split = C2.years, C2.split
    both, lost = combine(t2, t5)
    print(f'NQ v3，MNQ 固定 {QTY} 口，每筆扣 {COST:g} 點成本，{years:.2f} 年，前/後半以 {split} 分')
    print(f'  {"只做 2 分（現在）":<22}' + line(t2, years, split))
    print(f'  {"只做 5 分":<22}' + line(t5, years, split))
    print(f'  {"2 + 5 分，共用倉位":<22}' + line(both, years, split))
    for tf in (2, 5):
        x = both[both.tf == tf]; y = lost[lost.tf == tf]
        print(f'    其中 {tf} 分：做了 {len(x) / years:.0f} 筆/年 {x.pts.sum() / years:+.0f} 點；'
              f'被另一張圖占住沒做 {len(y) / years:.0f} 筆/年（那些單自己 {y.pts.sum() / years:+.0f} 點）')
    for kd in ('趨勢', 'MIX'):
        x = both[both.kind == kd]
        print(f'    {kd}：{len(x) / years:.0f} 筆/年 {x.pts.sum() / years:+.0f} 點')
    # how often both charts would hold a position at the same time if traded separately
    ov = sum(((t5.et < r.xt) & (t5.xt > r.et)).any() for r in t2.itertuples())
    print(f'  2 分的單裡，同時間 5 分也有持倉的：{ov / years:.0f} 筆/年（{100 * ov / max(len(t2), 1):.0f}%）')


if __name__ == '__main__':
    main()
