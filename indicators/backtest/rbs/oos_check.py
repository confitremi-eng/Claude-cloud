"""Out-of-sample check of Remi Superb v3 with the rules frozen (see ../oos_plan.md).

  cd indicators/backtest
  python3 -I rbs/oos_check.py [main | rules | neighbours | scaled | all]      # default: all

Data: data/NQ_1m_5y.csv (Databento NQ 2021-10-19 .. 2026-10-18, build_databento.py) and data/NQ_1m_5y_rolls.txt
(the roll offsets, to get the real price level). Years run October to October; Y1-Y4 are out of sample, IS is the
year the rules were picked on (2025-10-15 .. 2026-10-14).
Frozen v3 (commit 9bcf668), each NQ profile one position at a time, 1 point cost:
  NQ 2m   (20, 0, 8, 1), Trend Judge > 10, 1-hour EMA20 side, stop >= 1 ATR, <= 3 ATR from the 15 s EMA1130, event
          windows, trend 0-180 minutes, 3R; MIX box 60 min, first 10% break within 60 min, stop at the middle, 3R,
          no MIX 16-20 New York; no new trades from Taipei Saturday 02:00; 60-bar exit, 17:00 halt, data holes
  NQ 5m   the same, 2R
  NQ 3m   trend signals only, trend 90-120 minutes, 1R
  NQ RTH  1m cash-session bars, (35, 0, 8, 1), Trend Judge > 20, 7 ATR, no trend window, NQ 2m (24-hour, previous
          bar) not opposite, 3R, exit by 60 bars or the session end
Sections: main (per year), rules (Friday / MIX 16-20 / 0-180 on and off, trend vs MIX), neighbours (stage, threshold,
window), scaled (the one pre-registered variant: thresholds in proportion to the real NQ price).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import re
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import mix_range as mr
import mix_breakout as mb
import market_matrix as mm
import mix_opt as mo

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, 'data', 'NQ_1m_5y.csv')
ROLLS = os.path.join(HERE, 'data', 'NQ_1m_5y_rolls.txt')
YEARS = [('Y1 21/10–22/10', '2021-10-15', '2022-10-14'), ('Y2 22/10–23/10', '2022-10-15', '2023-10-14'),
         ('Y3 23/10–24/10', '2023-10-15', '2024-10-14'), ('Y4 24/10–25/10', '2024-10-15', '2025-10-14'),
         ('IS 25/10–26/10', '2025-10-15', '2026-10-14')]
COST = 1.0


# ───────────── data ─────────────
def load():
    one = mm.read_csv(DATA); one['bad'] = False
    return one


def real_price(index):
    """Unadjusted NQ price level: the back-adjusted price minus every later roll offset."""
    rolls = []
    for line in open(ROLLS, encoding='utf-8'):
        m = re.search(r'offset ([+-][\d.]+) \(last common minute (.+?)\)', line)
        if m: rolls.append((pd.Timestamp(m.group(2)), float(m.group(1))))
    off = np.zeros(len(index))
    for t, o in rolls:
        off += np.where(index <= t, o, 0.0)
    return off


def scale_series(one):
    """Per-minute factor real price / mean real price of the in-sample year (for the scaled-threshold variant)."""
    real = one.close.values - real_price(one.index)
    ins = (one.index >= YEARS[-1][1]) & (one.index <= YEARS[-1][2] + ' 23:59')
    return pd.Series(real / real[ins].mean(), index=one.index)


# ───────────── charts ─────────────
def chart(one, tdm, tf, th, st, scale=None):
    """mm.chart, optionally with thresholds that follow the price (th, st times the factor at the bar)."""
    df = mm.chart(one, tdm, tf, th, st)
    k = np.ones(len(df)) if scale is None else scale.reindex(pd.DatetimeIndex(df.last_min)).ffill().bfill().values
    df['thr'] = th * k
    if scale is not None:
        d = df.tj_diff.values; stt = st * k
        df['tj_dir'] = np.where(np.isnan(d), 0, np.where(d > stt, 2, np.where(d > df.thr, 1, np.where(d < -stt, -2, np.where(d < -df.thr, -1, 0)))))
        tdir = np.sign(df.tj_dir.values); tb = np.zeros(len(df), int)
        for j in range(len(df)):
            tb[j] = (tb[j - 1] + 1) if (j and tdir[j] != 0 and tdir[j] == tdir[j - 1]) else (1 if tdir[j] != 0 else 0)
        df['tmin'] = tb * tf
    return df


class Ctx:
    """What mix_opt.breaks / boxes need, built from a given chart."""
    def __init__(self, df, tf, H):
        self.tf, self.df = tf, df
        mr.TF, mr.TH = tf, df.thr.values
        rbs._cache[('NQ', tf)] = df
        self.B = B = mr.load()
        rbs._cache.pop(('NQ', tf), None)
        self.h, self.l, self.c, self.o = B['h'], B['l'], B['c'], B['o']
        self.n = len(self.c); self.hole = B['hole']; self.date = B['date']; self.tmin = df.tmin.values
        self.h1 = pd.merge_asof(pd.DataFrame({'t': df.datetime}), H, on='t', direction='backward').h1.fillna(0).values
        et = (df.datetime + pd.Timedelta(minutes=tf)).dt.tz_convert(ss.NY)
        self.halt = ((et.dt.hour * 60 + et.dt.minute) == 1020).values
        tw = (df.datetime + pd.Timedelta(minutes=tf)).dt.tz_convert('Asia/Taipei')
        self.late = ((tw.dt.weekday == 5) & (tw.dt.hour * 60 + tw.dt.minute >= 120)).values

    def bars(self, minutes):
        return max(1, round(minutes / self.tf))


def trend_set(df, H, tf, stage, th_arr, dist, lo, hi, nq_ok=None):
    s = mm.trend_signals(df, H, tf, stage, 8)
    m = (s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.slow < dist) & (s.spread > th_arr[s.i]) & (s.tm >= lo) & (s.tm < hi)
    if nq_ok is not None: m &= nq_ok(s)
    return s[m]


# ───────────── one position at a time ─────────────
def sim(C, trend, mix, R_trend, R_mix, friday=True):
    """trend: frame of signals (close entry, two-bar stop); mix: [(bar, side, price, stop, info)] stop orders."""
    df = C.df; h, l, c = C.h, C.l, C.c
    holeb = np.r_[False, (df.datetime.diff() > pd.Timedelta(minutes=30)).values[1:]]
    trad = df.tradable.values
    tr = {int(i): int(k) for i, k in zip(trend.i, trend.side)}
    mx = {j: (k, px, st) for j, k, px, st, _ in mix}
    trades = []; pos = 0
    for j in range(len(c)):
        if pos != 0 and j > vb:
            hs = (l[j] <= vs) if pos == 1 else (h[j] >= vs)
            ht = (h[j] >= vt) if pos == 1 else (l[j] <= vt)
            if hs or ht or j - vb >= 60 or C.halt[j] or holeb[j]:
                px = vs if hs else vt if ht else (c[j - 1] if holeb[j] else c[j])
                trades.append((kind, pos, ve, px, abs(ve - vs), d0)); pos = 0
        if not trad[j] or C.halt[j] or (friday and C.late[j]): continue
        if pos == 0 and j in mx:
            k, px, st = mx[j]
            pos, ve, vs, vt, vb, kind, d0 = k, px, st, px + R_mix * (px - st), j, 'MIX', C.date[j]
            if (pos == 1 and l[j] <= vs) or (pos == -1 and h[j] >= vs):
                trades.append((kind, pos, ve, vs, abs(ve - vs), d0)); pos = 0
        if pos == 0 and j in tr:
            k = tr[j]; st = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j])
            pos, ve, vs, vt, vb, kind, d0 = k, c[j], st, c[j] + R_trend * (c[j] - st), j, '趨勢', C.date[j]
    t = pd.DataFrame(trades, columns=['kind', 'side', 'entry', 'exit', 'risk', 'date'])
    t['R'] = (t.exit - t.entry) * t.side / t.risk
    t['net'] = t.R - COST / t.risk
    return t


def mix_list(C, no_pm=True):
    bx = mo.boxes(C)
    return [x for x in mo.breaks(C, bx) if not (no_pm and x[4]['sess'] == '收盤後 16-20')]


# ───────────── reporting ─────────────
def year_stats(t):
    if len(t) == 0: return dict(n=0, win=np.nan, per=np.nan, tot=0.0, dd=0.0, streak=0, months='-')
    n = t.net.values; eq = np.cumsum(n); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq))
    loss = n <= 0; streak = cur = 0
    for x in loss:
        cur = cur + 1 if x else 0; streak = max(streak, cur)
    mo_ = pd.Series(n).groupby(t.date.str[:7].values).sum()
    return dict(n=len(t), win=100 * (t.R > 0).mean(), per=n.mean(), tot=n.sum(), dd=dd, streak=streak, months=f'{(mo_ > 0).sum()}/{len(mo_)}')


def table(name, t):
    print(f'\n  ## {name}')
    print(f'   {"":<16} {"筆數":>5} {"勝率":>6} {"每筆":>7} {"全年":>8} {"回撤":>6} {"連虧":>4} {"賺錢月":>6}')
    oos = []
    for nm, a, b in YEARS:
        y = t[(t.date >= a) & (t.date <= b)]
        if not nm.startswith('IS'): oos.append(y)
        r = year_stats(y)
        print(f'   {nm:<16} {r["n"]:5d} {r["win"]:5.1f}% {r["per"]:+7.3f} {r["tot"]:+8.1f} {r["dd"]:6.1f} {r["streak"]:4d} {r["months"]:>6}')
    o = pd.concat(oos); r = year_stats(o)
    yrs = [year_stats(t[(t.date >= a) & (t.date <= b)])['tot'] for nm, a, b in YEARS[:4]]
    print(f'   {"樣本外 4 年合計":<14} {r["n"]:5d} {r["win"]:5.1f}% {r["per"]:+7.3f} {r["tot"]:+8.1f} {r["dd"]:6.1f} {r["streak"]:4d} {r["months"]:>6}'
          f'   賺錢的年 {sum(x > 0 for x in yrs)}/4')
    return r['per'], sum(x > 0 for x in yrs), max(year_stats(t[(t.date >= a) & (t.date <= b)])['dd'] for nm, a, b in YEARS[:4])


def one_line(name, t):
    yrs = [year_stats(t[(t.date >= a) & (t.date <= b)]) for nm, a, b in YEARS]
    o = year_stats(t[(t.date >= YEARS[0][1]) & (t.date <= YEARS[3][2])])
    print(f'   {name:<26} ' + '  '.join(f'{r["tot"]:+6.0f}' for r in yrs) + f'   樣本外每筆 {o["per"]:+.3f}  賺錢年 {sum(r["tot"] > 0 for r in yrs[:4])}/4  最大年回撤 {max(r["dd"] for r in yrs[:4]):4.0f}')


# ───────────── profiles ─────────────
class Market:
    def __init__(self, one, scale=None):
        self.one, self.scale = one, scale
        self.tdm = mm.minute_trend(one); self.H = mm.hourly(one, False)
        self._c = {}

    def ctx(self, tf, th=10.0, st=35.0):
        key = (tf, th)
        if key not in self._c:
            self._c[key] = Ctx(chart(self.one, self.tdm, tf, th, st, self.scale), tf, self.H)
        return self._c[key]

    def nq(self, tf, R, lo, hi, mix=True, stage=20, th=10.0, friday=True, no_pm=True, trend=True):
        C = self.ctx(tf, th, 35.0 * th / 10.0)
        T = trend_set(C.df, self.H, tf, stage, C.df.thr.values, 3.0, lo, hi) if trend else C.df.iloc[0:0].assign(i=[], side=[])
        M = mix_list(C, no_pm) if mix else []
        return sim(C, T, M, R, R, friday)


def nq_rth(one, scale=None, detail=False):
    """NQ RTH 1m (QQQ setting) with the NQ 2m not-opposite filter from the 24-hour chart. detail: (chart, taken signals)."""
    cash = mm.cash_only(one); tdq = mm.minute_trend(cash); Hq = mm.hourly(cash, True)
    sc = None if scale is None else scale
    df = chart(cash, tdq, 1, 20.0, 40.0, sc)
    dn = mm.chart(one, mm.minute_trend(one), 2, 10.0, 35.0)
    c2 = dn.close.values
    aF = 1 - (1 - 2 / 1131) ** 24; aS = 1 - (1 - 2 / 1131) ** 8
    d2 = pd.Series(c2).ewm(alpha=aF, adjust=False).mean().values - pd.Series(c2).ewm(alpha=aS, adjust=False).mean().values
    k2 = np.ones(len(dn)) if scale is None else scale.reindex(pd.DatetimeIndex(dn.last_min)).ffill().bfill().values
    ndir = np.where(d2 > 10 * k2, 1, np.where(d2 < -10 * k2, -1, 0))
    nstart = pd.DatetimeIndex(dn.datetime).values.astype('datetime64[ns]').astype(np.int64)

    def nq_ok(s):
        t_open = pd.DatetimeIndex(df.last_min.values[s.i])
        t_open = (t_open.tz_localize('UTC') if t_open.tz is None else t_open).values.astype('datetime64[ns]').astype(np.int64)
        k = np.searchsorted(nstart, t_open, 'right') - 2
        return ndir[k] * s.side.values >= 0
    s = trend_set(df, Hq, 1, 35, df.thr.values, 7.0, 0, 10 ** 9, nq_ok)
    tw = (df.datetime + pd.Timedelta(minutes=1)).dt.tz_convert('Asia/Taipei').values[s.i]
    tw = pd.DatetimeIndex(tw); tw = tw.tz_localize('UTC').tz_convert('Asia/Taipei') if tw.tz is None else tw
    s = s[~((tw.weekday == 5) & (tw.hour * 60 + tw.minute >= 120))]
    t = ss.seq(s.sort_values('i'), 3.0)
    if detail: return df, t
    return pd.DataFrame({'kind': '趨勢', 'date': t.date.values, 'R': t.r3.values, 'net': t.r3.values - COST / t.risk.values})


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    one = load()
    print(f'NQ {one.index[0]:%Y-%m-%d} .. {one.index[-1]:%Y-%m-%d}；規則凍結（v3 @ 9bcf668），每筆扣 {COST:g} 點')
    M = Market(one)
    if what in ('main', 'all'):
        print('\n################ 1. v3 各做法逐年（一次一筆）')
        res = {}
        res['NQ 2m'] = table('NQ 2m（趨勢 0–180 + MIX，3R）', M.nq(2, 3.0, 0, 180))
        res['NQ 5m'] = table('NQ 5m（趨勢 0–180 + MIX，2R）', M.nq(5, 2.0, 0, 180))
        res['NQ 3m'] = table('NQ 3m（趨勢 90–120，1R）', M.nq(3, 1.0, 90, 120, mix=False))
        res['NQ RTH'] = table('NQ RTH 1m（QQQ 做法，3R）', nq_rth(one))
        print('\n  ## 過關判斷（oos_plan.md 第 4 節；4 年版：主測合計每筆 ≥ +0.10R、至少 3 年賺錢、每年回撤 ≤ 40R）')
        for k, (per, wins, dd) in res.items():
            if k == 'NQ 2m':
                v = '過關' if per >= 0.10 and wins >= 3 and dd <= 40 else '部分過關' if per > 0 else '不過關'
            else:
                v = '過關' if per > 0 and wins >= 3 else '部分過關' if per > 0 else '不過關'
            print(f'   {k:<8} 樣本外每筆 {per:+.3f}R、賺錢年 {wins}/4、最大年回撤 {dd:.0f}R → {v}')
    if what in ('rules', 'all'):
        print('\n################ 2. 規則和組成（NQ 2m，每年 R：Y1 Y2 Y3 Y4 IS）')
        one_line('v3（全部規則）', M.nq(2, 3.0, 0, 180))
        one_line('只有趨勢訊號', M.nq(2, 3.0, 0, 180, mix=False))
        one_line('只有 MIX 突破', M.nq(2, 3.0, 0, 180, trend=False))
        one_line('關掉週五截止', M.nq(2, 3.0, 0, 180, friday=False))
        one_line('MIX 美東 16–20 也做', M.nq(2, 3.0, 0, 180, no_pm=False))
        one_line('趨勢時間不限（0–∞）', M.nq(2, 3.0, 0, 10 ** 9))
        print('   NQ 5m')
        one_line('v3（全部規則）', M.nq(5, 2.0, 0, 180))
        one_line('只有趨勢訊號', M.nq(5, 2.0, 0, 180, mix=False))
        one_line('只有 MIX 突破', M.nq(5, 2.0, 0, 180, trend=False))
        one_line('MIX 美東 16–20 也做', M.nq(5, 2.0, 0, 180, no_pm=False))
    if what in ('neighbours', 'all'):
        print('\n################ 3. 鄰近參數（NQ 2m，只看是不是一片都賺；每年 R：Y1 Y2 Y3 Y4 IS）')
        for stg in (15, 20, 25):
            one_line(f'階段 {stg}', M.nq(2, 3.0, 0, 180, stage=stg))
        for th in (8.0, 10.0, 12.0):
            one_line(f'門檻 {th:g}', M.nq(2, 3.0, 0, 180, th=th))
        for hi in (120, 180, 240):
            one_line(f'趨勢時間 0–{hi}', M.nq(2, 3.0, 0, hi))
    if what in ('scaled', 'all'):
        print('\n################ 4. 事先登記的替代版本：門檻跟真實價格等比例（每年 R：Y1 Y2 Y3 Y4 IS）')
        sc = scale_series(one)
        for nm, a, b in YEARS:
            x = sc[(sc.index >= a) & (sc.index <= b + ' 23:59')]
            print(f'   {nm}：門檻倍數 {x.mean():.2f}（NQ 2m 門檻約 {10 * x.mean():.1f} 點）')
        S = Market(one, sc)
        for tf, R, lo, hi, mix in ((2, 3.0, 0, 180, True), (5, 2.0, 0, 180, True), (3, 1.0, 90, 120, False)):
            one_line(f'NQ {tf}m 原版門檻', M.nq(tf, R, lo, hi, mix=mix))
            one_line(f'NQ {tf}m 等比例門檻', S.nq(tf, R, lo, hi, mix=mix))
        one_line('NQ RTH 原版門檻', nq_rth(one))
        one_line('NQ RTH 等比例門檻', nq_rth(one, sc))


if __name__ == '__main__':
    main()
