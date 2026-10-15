"""Build clean NQ / ES 1-minute files from two versions of the getdata-finance free samples.

The 2026-09-03 sample (2026-04-01 .. 2026-09-02) has synthetic rows: whole days whose prices are
not on the 0.25 tick, open == previous close on every bar, and a ~10% jump away from the real
price level (2026-08-03 .. 2026-08-14, and the holidays 2026-05-25 / 06-19 / 07-03). The older
2026-08-04 sample (2026-02-02 .. 2026-07-31) has real prices on those holidays' neighbours and adds
February-March, but it is not back-adjusted for the June roll: before 2026-06-11 it is a constant
offset below the newer file (NQ 281, ES 61 points).

Clean file = older sample up to 2026-06-10 shifted by that offset + newer sample from 2026-06-11,
minus every day where most rows are off-tick (synthetic).

usage: python3 build_data.py OLD_NQ NEW_NQ OLD_ES NEW_ES OUT_DIR
  OLD_* : NQ_1m.csv / ES_1m.csv at commits 6a00d71 / 58b144f (2026-08-04)
  NEW_* : NQ_1m.csv / ES_1m.csv at commits 41366a5 / 0908875 (2026-09-03)
"""
import os
import sys
import numpy as np
import pandas as pd

SPLICE = pd.Timestamp('2026-06-11').date()      # first New York date taken from the newer file
PX = ['open', 'high', 'low', 'close']


def read(path):
    return pd.read_csv(path, parse_dates=['datetime']).set_index('datetime').sort_index()


def et_date(idx):
    return np.array(idx.tz_convert('America/New_York').date)


def synthetic_days(df):
    off = ((df[PX] * 4) % 1).abs().max(axis=1) > 1e-6
    share = pd.Series(off.values, index=et_date(df.index)).groupby(level=0).mean()
    return set(share[share > 0.5].index)


def build(old_path, new_path, sym):
    old, new = read(old_path), read(new_path)
    od, nd = et_date(old.index), et_date(new.index)
    bad = synthetic_days(old) | synthetic_days(new)
    # offset between the files where both are real and before the June roll
    ov = old.index.intersection(new.index)
    ovd = et_date(ov)
    keep = np.array([(d < SPLICE) and (d not in bad) for d in ovd])
    diff = (new.loc[ov[keep], 'close'] - old.loc[ov[keep], 'close']).round(6)
    assert diff.nunique() == 1, f'{sym}: offset before the June roll is not constant'
    offset = float(diff.iloc[0])
    part1 = old[od < SPLICE].copy()
    part1[PX] += offset
    part2 = new[nd >= SPLICE]
    out = pd.concat([part1, part2]).sort_index()
    assert out.index.is_unique
    out = out[[d not in bad for d in et_date(out.index)]]
    print(f'{sym}: offset {offset:+.2f}, dropped synthetic days {sorted(str(d) for d in bad)}')
    print(f'{sym}: {len(out)} rows, {out.index[0]} .. {out.index[-1]}, {len(set(et_date(out.index)))} New York dates')
    return out


if __name__ == '__main__':
    old_nq, new_nq, old_es, new_es, out_dir = sys.argv[1:6]
    os.makedirs(out_dir, exist_ok=True)
    for sym, o, n in (('NQ', old_nq, new_nq), ('ES', old_es, new_es)):
        build(o, n, sym).reset_index().to_csv(os.path.join(out_dir, f'{sym}_1m_clean.csv'), index=False)
