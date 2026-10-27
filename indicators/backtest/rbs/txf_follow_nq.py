"""Trade TXF on NQ / QQQ signals? Mirror each NQ trade on TXF: same direction, enter at the TXF 1m close of the entry
minute, exit at the NQ trade's exit minute (stop / target / time, as the NQ strategy decides). The Databento year.

  cd indicators/backtest
  python3 -I rbs/txf_follow_nq.py <TXFR1 .sql dumps ...> --tv "TAIFEX_TXF1!, 1_xxxxx.csv"

Sources (combo_rth1m.py trade lists, today's filters): NQ 2m (24-hour, trend + super sells... here trend + MIX, 3R),
NQ RTH 1m (QQQ setting, 3R). Only trades whose entry and exit both fall inside one TXF session (Taipei day 08:45-13:45,
night 15:00-05:00) are mirrored. TXF cost 2 points per trade. Also TXF's own Remi TXF signals over the same months.
Per source: trades, NQ win rate, TXF win rate, TXF points total / per trade, by session. Then Remi TXF + the night
NQ 2m mirror on one shared position: win rate, points, drawdown, losing streak.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import market_matrix as mm
import mix_opt as mo
import combo_2m5m as cb
import combo_rth1m as cr
import txf_streaks as ts


def main():
    tx = ts.load(sys.argv[1:])
    txc = tx.close; txi = txc.index.values.astype('datetime64[ns]')
    one = mm.load_market('nq', []); one['bad'] = False
    tdm = mm.minute_trend(one); H = mm.hourly(one, False)
    C2 = mo.Ctx(2, one, tdm, H)
    o = cr.current_trend(C2, H, 2, 400); t2 = cb.v3_trades(C2, 3.0, one); mo.breaks = o
    t1 = cr.rth_trades(one)
    tpe = 'Asia/Taipei'

    def session(ts_):
        tw = ts_.tz_convert(tpe); m = tw.hour * 60 + tw.minute; d = tw.normalize()
        day = (m >= 525) & (m <= 825)
        night = (m >= 900) | (m <= 300)
        key = np.where(day, d.strftime('%Y-%m-%d') + ' 日', np.where(m >= 900, d.strftime('%Y-%m-%d') + ' 夜', (d - pd.Timedelta(days=1)).strftime('%Y-%m-%d') + ' 夜'))
        return np.where(day | night, key, ''), np.where(day, '日盤', '夜盤')

    def mirror(t, lab):
        et = pd.DatetimeIndex(pd.to_datetime(t.et, utc=True)); xt = pd.DatetimeIndex(pd.to_datetime(t.xt, utc=True))
        se, kind = session(et); sx, _ = session(xt)
        ok = (se != '') & (se == sx)
        a = np.searchsorted(txi, (et - pd.Timedelta(minutes=1)).values.astype('datetime64[ns]'), 'right') - 1   # last TXF minute bar ending by entry
        b = np.searchsorted(txi, (xt - pd.Timedelta(minutes=1)).values.astype('datetime64[ns]'), 'right') - 1
        good = ok & (a >= 0) & (b > a)
        # the TXF bar used must be within 2 minutes of the time (TXF was trading)
        lag_a = (et.values.astype('datetime64[ns]') - txi[np.maximum(a, 0)]).astype('timedelta64[m]').astype(int)
        good &= (lag_a <= 2)
        z = t[good].copy(); z['kind_s'] = kind[good]
        z['tx'] = (txc.values[b[good]] - txc.values[a[good]]) * z.side.values - 2.0
        print(f'\n{lab}：NQ 這段 {len(t)} 筆，台指有開盤、同一盤內進出的 {len(z)} 筆')
        for k, q in [('全部', z)] + list(z.groupby('kind_s')):
            print(f'   {k:<4} {len(q):4d} 筆  NQ 勝率 {100 * (q.R > 0).mean():3.0f}%  台指勝率 {100 * (q.tx > 0).mean():3.0f}%  '
                  f'台指合計 {q.tx.sum():+7.0f} 點  每筆 {q.tx.mean():+6.1f} 點  （小台 1 口 {50 * q.tx.sum():+,.0f} 元）')
        return z

    print(f'台指 1 分 K {tx.index[0]} .. {tx.index[-1]}；NQ {one.index[0]} .. {one.index[-1]}')
    m2 = mirror(t2, 'NQ 2m 的單照做在台指')
    mirror(t1, 'NQ RTH 1m（QQQ 1m）的單照做在台指')
    # TXF's own Remi TXF (trend + super sells, TJ 100 / stage 6 / EMA30 / 2R) over the overlap, for scale
    import txf_tf_super as tt, setup_study as ss
    d2 = mm.chart(tx, mm.minute_trend(tx), 2, 30.0, 60.0); d5 = mm.chart(tx, mm.minute_trend(tx), 5, 30.0, 60.0); Ht = mm.hourly(tx, False)
    s = mm.trend_signals(d2, Ht, 2, 20, 8); base = s[mm.filt(s, 30.0, 3.0) & (s.tm >= 60) & (s.tm < 120)].assign(kind='趨勢')
    x = mm.trend_signals(d2, Ht, 2, 6, 8); x = x[(x.side == -1) & ~ss.EVT(x) & (x.tm < 600) & (x.spread > 100) & ~x.i.isin(base.i)].assign(kind='超強')
    c5 = d5.close.values; e30 = pd.Series(c5).ewm(span=30, adjust=False).mean().values
    end5 = (pd.DatetimeIndex(d5.datetime) + pd.Timedelta(minutes=5)).values.astype('datetime64[ns]').astype(np.int64)
    end2 = (pd.DatetimeIndex(d2.datetime) + pd.Timedelta(minutes=2)).values.astype('datetime64[ns]').astype(np.int64)
    k = np.searchsorted(end5, end2[x.i.values], 'right') - 1
    x = x[c5[k] < e30[k]].copy(); x['x3'] = x['x2']; x['r3'] = x['r2']
    T = pd.concat([base, x]).sort_values('i'); T['tj_off'] = 0.0
    sess, tw = tt.sessions(d2, 2)
    r = ts.run(T, d2, sess, 'cool', 5)
    r = r[r.date >= str(one.index[0].date())]
    pts = (r.r3 * r.risk - 2.0)
    print(f'\n對照：Remi TXF 自己的訊號（同期間）{len(r)} 筆，勝率 {100 * (r.r3 > 0).mean():.0f}%，合計 {pts.sum():+.0f} 點，每筆 {pts.mean():+.1f} 點（小台 1 口 {50 * pts.sum():+,.0f} 元）')

    # one shared position: Remi TXF own + NQ 2m mirrored in the night session (first come; ties to Remi TXF)
    step = pd.Timedelta(minutes=2)
    dtm = pd.DatetimeIndex(d2.datetime); dtm = dtm.tz_localize('UTC') if dtm.tz is None else dtm
    own = pd.DataFrame({'src': 'Remi TXF', 'et': dtm[r.i.values] + step, 'xt': dtm[r.x3.values.astype(int)] + step, 'pts': pts.values, 'date': r.date.values})
    nq = m2[m2.kind_s == '夜盤']
    mir = pd.DataFrame({'src': 'NQ 2m 夜盤', 'et': pd.to_datetime(nq.et, utc=True).values, 'xt': pd.to_datetime(nq.xt, utc=True).values, 'pts': nq.tx.values, 'date': nq.date.values})
    mir['et'] = pd.to_datetime(mir.et, utc=True); mir['xt'] = pd.to_datetime(mir.xt, utc=True)
    def stats(lab, z):
        z = z.sort_values('et'); eq = np.cumsum(z.pts.values); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)) if len(z) else 0
        loss = (z.pts <= 0).values; best = cur = 0
        for v in loss:
            cur = cur + 1 if v else 0; best = max(best, cur)
        mo = z.groupby(pd.DatetimeIndex(z.et).strftime('%Y-%m')).pts.sum()
        print(f'   {lab:<28}{len(z):4d} 筆  勝率 {100 * (z.pts > 0).mean():3.0f}%  合計 {z.pts.sum():+7.0f} 點  每筆 {z.pts.mean():+5.1f}  回撤 {dd:5.0f} 點  最長連虧 {best:2d}  賺錢月份 {(mo > 0).sum()}/{len(mo)}  （小台 1 口 {50 * z.pts.sum():+,.0f} 元，回撤 {50 * dd:,.0f} 元）')
    print('\n######## 共用一個倉位（先進場的佔用，同分鐘讓 Remi TXF）')
    t = pd.concat([own.assign(pri=0), mir.assign(pri=1)]).sort_values(['et', 'pri'], kind='stable')
    keep, busy = [], pd.Timestamp('1970-01-01', tz='UTC')
    for row in t.itertuples():
        ok = row.et >= busy; keep.append(ok)
        if ok: busy = row.xt
    t['taken'] = keep; both = t[t.taken]
    stats('只做 Remi TXF', own); stats('只做 NQ 2m 夜盤', mir); stats('Remi TXF + NQ 2m 夜盤', both)
    for src, z in both.groupby('src'):
        lost = t[~t.taken & (t.src == src)]
        print(f'      其中 {src}：做了 {len(z)} 筆 {z.pts.sum():+.0f} 點；被占住沒做 {len(lost)} 筆（自己 {lost.pts.sum():+.0f} 點）')


if __name__ == '__main__':
    main()
