import numpy as np, pandas as pd
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 300)
M = pd.read_csv('nq_stage2.csv')
M['half'] = np.where(M.mon <= 6, 'AJ', 'JS')
keys = ['thr', 'N', 'erMin', 'exit', 'stopN', 'bias']
def agg(x):
    n = x.n.sum()
    aj = x[x.half == 'AJ']; js = x[x.half == 'JS']
    mm = x.groupby('mon').apply(lambda y: y.sumR.sum() / y.n.sum())
    tfm = x.groupby('tf').apply(lambda y: y.sumR.sum() / y.n.sum())
    days_proxy = n
    return pd.Series({'n': n, 'avgR': x.sumR.sum() / n, 'pts': x.sumP.sum() / n, 'win': 100 * x.wins.sum() / n,
                      'R_AJ': aj.sumR.sum() / max(aj.n.sum(), 1), 'R_JS': js.sumR.sum() / max(js.n.sum(), 1),
                      'n_JS': js.n.sum(), 'mon+': int((mm > 0).sum()), 'tf+': int((tfm > 0).sum()),
                      'R_1m': tfm.get(1, np.nan), 'R_2m': tfm.get(2, np.nan), 'R_3m': tfm.get(3, np.nan), 'R_5m': tfm.get(5, np.nan)})
S = M.groupby(keys).apply(agg).reset_index()
S.to_csv('nq_stage2_summary.csv', index=False)
print('combos:', len(S), ' with R_AJ>0 and R_JS>0:', int(((S.R_AJ > 0) & (S.R_JS > 0)).sum()), ' best R_JS:', S.R_JS.max().round(3))
print('\n== marginal effect of each parameter (mean over all other settings; avgR / R_AJ / R_JS / pts / n)')
for k in keys:
    g = S.groupby(k)[['avgR', 'R_AJ', 'R_JS', 'pts', 'n']].mean()
    print(f'-- {k}'); print(g.round(3).to_string())
print('\n== top 25 by min(R_AJ, R_JS) with n >= 150')
S['minhalf'] = S[['R_AJ', 'R_JS']].min(axis=1)
print(S[S.n >= 150].sort_values('minhalf', ascending=False).head(25).round(3).to_string(index=False))
print('\n== top 25 by avgR with n >= 200')
print(S[S.n >= 200].sort_values('avgR', ascending=False).head(25).round(3).to_string(index=False))
