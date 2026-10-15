import pandas as pd, numpy as np
R = pd.read_csv('round1.csv')
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 200)
g = R.groupby(['var', 'exit'])
A = pd.DataFrame({
    'cells_tr_pos': g.apply(lambda x: int((x.exp_tr > 0).sum())),
    'mean_exp_tr': g.exp_tr.mean(), 'min_n_tr': g.n_tr.min(), 'tot_n_tr': g.n_tr.sum(),
    'cells_te_pos': g.apply(lambda x: int((x.exp_te > 0).sum())),
    'mean_exp_te': g.exp_te.mean(), 'tot_n_te': g.n_te.sum(),
    'win_tr': g.apply(lambda x: np.average(x.win_tr.fillna(0), weights=x.n_tr.clip(lower=1))),
    'win_te': g.apply(lambda x: np.average(x.win_te.fillna(0), weights=x.n_te.clip(lower=1))),
}).reset_index()
cand = A[A.min_n_tr >= 15].sort_values('mean_exp_tr', ascending=False)
print('TOP 25 by TRAIN mean expectancy (8 cells: NQ/ES x 1/2/3/5m), with their TEST results:')
print(cand.head(25).round(3).to_string(index=False))
print('\nBaseline-like rows:')
print(A[A['var'].isin(['BO N=25 ema=1 strong=0', 'BO N=20 ema=1 strong=0'])].round(3).to_string(index=False))
