#!/usr/bin/env python3
"""Independent re-implementation across the WHOLE axis grid, not just k=2 / RSSu.

check_models.py compared one corner of the axis space (coverage k=2, bias treatment RSSu,
pooled precision). Everything the other axes do — Welch-Satterthwaite, Monte Carlo, and the
five bias-treatment conventions — was therefore never checked against anything, which is how
a Monte Carlo defect survived that check. This file closes that hole.

Nothing here imports the tool: the model primitives are rebuilt from the IQC summary, the EQA
rounds and the typed calibrator values, and the coverage / bias-treatment algebra is written
out again from the source documents (GUM G.4, ISO 21748 13.2.3.3, Magnusson & Ellison Table 3).
"""
import csv, math, statistics, collections
from scipy.stats import t as tdist

from check_models import UCAL, EQA2IQC, ucal_pct, bias_primitives   # reuse the verified inputs

SQ3 = math.sqrt(3.0)


# ---------------------------------------------------------------- model primitives
def primitives(rw, dfRw, ucal, dfUcal, B):
    """Return, per model: precision terms [(u, nu)], the bias point estimate, its uncertainty
    and the degrees of freedom of that uncertainty — exactly the quantities the coverage and
    bias-treatment algebra below consumes."""
    n, mean, sd, rms, uc = B['n'], B['mean'], B['sd'], B['rms'], B['uCref']
    nu = max(1, n - 1)
    uMean = B['uMean']
    P = {}
    P['iso'] = dict(prec=[(rw, dfRw), (ucal, dfUcal)], bVal=0.0, bU=0.0, bNu=None)
    P['iso_hybrid'] = dict(prec=[(rw, dfRw), (ucal, dfUcal)], bVal=abs(mean), bU=uMean, bNu=nu)
    P['nordtest_rms'] = dict(prec=[(rw, dfRw)], bVal=rms, bU=uc, bNu=nu)
    P['nordtest_sem'] = dict(prec=[(rw, dfRw)], bVal=0.0, bU=uMean, bNu=nu)
    P['nordtest_mean'] = dict(prec=[(rw, dfRw)], bVal=abs(mean), bU=uMean, bNu=nu)
    # EUROLAB: CV_rep defaults to u_Rw and n_rep = 1, so the replicate term equals u_Rw
    rep = rw / math.sqrt(1)
    P['eurolab'] = dict(prec=[(rw, dfRw)], bVal=abs(mean), bU=math.sqrt(uc * uc + rep * rep), bNu=nu)
    P['cofrac'] = dict(prec=[(rw, dfRw)], bVal=0.0,
                       bU=math.sqrt((abs(mean) / SQ3) ** 2 + sd * sd), bNu=nu)
    P['cofrac_rms'] = dict(prec=[(rw, dfRw)], bVal=0.0,
                           bU=math.sqrt((rms / SQ3) ** 2 + sd * sd), bNu=nu)
    if B['sR'] and B['p']:
        sR, p = B['sR'], B['p']
        sL = math.sqrt(max(0.0, sR * sR - rw * rw))          # s_r taken as u_Rw (pooled precision)
        nuR = max(1, (p - 1) * n)                            # (p-1) * rounds
        udelta = math.sqrt(max(0.0, (sR * sR - (1 - 1.0 / 1) * rw * rw) / p))   # n_rep(EQA) = 1
        P['iso21748'] = dict(prec=[(rw, dfRw), (sL, nuR)], bVal=0.0, bU=udelta, bNu=nuR)
    return P


# ---------------------------------------------------------------- coverage + bias algebra
def welch(uc, terms):
    den = 0.0
    any_ = False
    for u, nu in terms:
        if u and u > 0 and nu and math.isfinite(nu) and nu > 0:
            den += u ** 4 / nu
            any_ = True
    if not any_ or den <= 0:
        return None
    return uc ** 4 / den


def expand(p, mean_signed, cov, bias_treat):
    """Returns (U, k, nuEff) or ('ERR', reason)."""
    prec = [(u, nu) for (u, nu) in p['prec'] if u and u > 0]
    uPrec = math.sqrt(sum(u * u for u, _ in prec))
    bVal, bU, bNu = p['bVal'], p['bU'], p['bNu']

    bSigned = mean_signed if bVal > 0 else 0.0
    DELTA = -bSigned
    ucCorr = math.sqrt(uPrec * uPrec + bU * bU)

    withB = prec + ([(bU, bNu)] if bU > 0 else [])
    if bias_treat in ('rss', 'rssU'):
        terms = withB + ([(bVal, bNu)] if bVal > 0 else [])
        uc = math.sqrt(uPrec ** 2 + bU ** 2 + bVal ** 2) if bias_treat == 'rss' else ucCorr
    else:
        terms = withB
        uc = ucCorr

    k, nuEff = 2.0, None
    if cov == 'ws':
        nuEff = welch(uc, withB)          # WS_BIAS false: the point estimate is excluded
        if nuEff:
            nuEff = max(1, math.floor(nuEff))
            k = float(tdist.ppf(0.975, nuEff))

    if bias_treat == 'rss':
        U = k * uc
    elif bias_treat == 'rssU':
        U = k * math.sqrt(uPrec ** 2 + bU ** 2 + (DELTA / k) ** 2)
    elif bias_treat == 'sumu':
        U = max(max(0.0, k * ucCorr - DELTA), max(0.0, k * ucCorr + DELTA))
    elif bias_treat == 'ue':
        if ucCorr > 0 and abs(DELTA) / ucCorr > 0.8:
            U = 1.65 * ucCorr + abs(DELTA)
        else:
            return ('ERR', 'Ue')
    else:                                   # sumumax
        U = k * ucCorr + abs(DELTA)
    return (U, k, nuEff)


# ---------------------------------------------------------------- data
def load():
    eqa = collections.defaultdict(list)
    for r in csv.DictReader(open('data/eqa-final.csv')):
        if r['excluded']:
            continue
        tkey = EQA2IQC.get(r['analyte'])
        if not tkey:
            continue
        X = float(r['assigned'])
        res = X * (1 + float(r['bias_used']) / 100)
        sd = None
        if r['group_sd'] and not r['group_sd'].startswith('<') and r['group_sd'] != '-':
            sd = float(r['group_sd'])
        u = float(r['ucref_used']) / 100 * X if r['ucref_used'] else 0.0
        eqa[tkey].append(dict(X=X, res=res, sd=sd,
                              n=float(r['group_n']) if r['group_n'] else None, u=u))
    iqc = list(csv.DictReader(open('data/iqc-summary.csv')))
    return iqc, eqa


def main():
    iqc, eqa = load()
    tool = {}
    for r in csv.DictReader(open('data/results-axes.csv')):
        tool[(r['cov'], r['bias'], r['test'], r['level'], r['model'])] = r

    MOD = ['iso', 'iso_hybrid', 'nordtest_rms', 'nordtest_sem', 'nordtest_mean',
           'eurolab', 'cofrac', 'cofrac_rms', 'iso21748']
    stats = collections.defaultdict(lambda: dict(n=0, worst=0.0, bad=[]))
    mc_gap = []
    err_agree = err_disagree = 0

    for r in iqc:
        test, lv = r['test'], r['level']
        if test not in eqa:
            continue
        rw = float(r['u_Rw_pct'])
        mean_conc = float(r['mean'])
        dfRw = int(r['n']) - 1
        ucal = ucal_pct(test, mean_conc)
        B = bias_primitives(eqa[test])
        P = primitives(rw, dfRw, ucal, None, B)

        for cov in ('k2', 'ws', 'mc'):
            for bt in ('rss', 'rssU', 'sumu', 'sumumax', 'ue'):
                for m in MOD:
                    if m not in P:
                        continue
                    tr = tool.get((cov, bt, test, lv, m))
                    if tr is None:
                        continue
                    mine = expand(P[m], B['mean'], 'ws' if cov == 'ws' else 'k2', bt)

                    if mine[0] == 'ERR':
                        if tr['err']:
                            err_agree += 1
                        else:
                            err_disagree += 1
                            stats[(cov, bt)]['bad'].append((test, lv, m, 'expected an error'))
                        continue
                    if not tr['U']:
                        err_disagree += 1
                        stats[(cov, bt)]['bad'].append((test, lv, m, 'tool declined, we did not'))
                        continue

                    U_mine, k_mine, _ = mine
                    U_tool = float(tr['U'])

                    if cov == 'mc':
                        # Monte Carlo is stochastic, so it cannot be reproduced exactly. What must
                        # hold is the invariant the fix established: MC differs from WS only through
                        # the coverage factor, and with these degrees of freedom the two agree.
                        k_tool = float(tr['k']) if tr['k'] else None
                        _, k_ws, _ = expand(P[m], B['mean'], 'ws', bt)
                        if k_tool:
                            mc_gap.append((abs(k_tool - k_ws) / k_ws, test, lv, m, bt, k_tool, k_ws))
                        continue

                    d = abs(U_mine - U_tool) / max(1e-9, U_tool)
                    s = stats[(cov, bt)]
                    s['n'] += 1
                    s['worst'] = max(s['worst'], d)
                    if d > 0.005:
                        s['bad'].append((test, lv, m, round(U_mine, 3), round(U_tool, 3), round(d, 4)))

    print('independent re-implementation vs the tool, across the axis grid')
    print('%-14s %7s %14s %8s' % ('coverage/bias', 'n', 'worst rel diff', 'bad'))
    tot = 0
    allbad = 0
    for key in sorted(stats):
        if key[0] == 'mc':
            continue
        s = stats[key]
        if not s['n']:
            continue
        tot += s['n']
        allbad += len(s['bad'])
        print('%-14s %7d %14.2e %8d' % ('/'.join(key), s['n'], s['worst'], len(s['bad'])))
        for b in s['bad'][:4]:
            print('      ', b)
    print('-' * 50)
    print('total compared      :', tot)
    print('mismatches > 0.5 %% :', allbad)
    print('declines agreed     :', err_agree, ' disagreed:', err_disagree)
    if mc_gap:
        mc_gap.sort(reverse=True)
        worst = mc_gap[0]
        print('MC vs WS coverage factor: %d compared, largest relative gap %.3f %%  (%s %s %s %s: k_mc=%.4f k_ws=%.4f)'
              % (len(mc_gap), worst[0] * 100, worst[1], worst[2], worst[3], worst[4], worst[5], worst[6]))
        over = [g for g in mc_gap if g[0] > 0.03]
        print('MC k differing from WS k by more than 3 %%:', len(over))
        for g in over[:5]:
            print('      ', g[1:])


if __name__ == '__main__':
    main()
