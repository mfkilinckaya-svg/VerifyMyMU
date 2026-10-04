#!/usr/bin/env python3
"""Monte Carlo: reproducibility, and agreement with an independent implementation.

A stochastic result cannot be compared digit for digit with a re-implementation, so the previous
checks left it out — which is exactly how a defect survived there. Three properties are checked
instead, and together they pin the arm down:

  1. Reproducibility: with a seed, the same evaluation gives the same interval twice, and a
     different seed gives a different one. Without this, nothing else about MC is checkable.
  2. Agreement: a second Monte Carlo written here (numpy, scaled-t draws, 400 000 draws) must
     reach the same 95 % interval as the tool, within the Monte Carlo error of the two runs.
  3. Consistency with the analytic arms: when every component has large degrees of freedom the
     draw must collapse onto k = 1.96, and it must not include the bias point estimate.
"""
import asyncio, math, sys
import numpy as np
from playwright.async_api import async_playwright

import os
TOOL = 'file://' + os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'VerifyMyMU.html'))
DRAWS_PY = 400_000
fails = []


def rep(name, ok, detail=''):
    print(('  PASS  ' if ok else '  FAIL  ') + name + (('   ' + str(detail)) if detail else ''))
    if not ok:
        fails.append(name)


def mc_python(terms, draws=DRAWS_PY, seed=7):
    """terms: [(u, nu or None)] -> half-width of the central 95 % interval of the sum."""
    rng = np.random.default_rng(seed)
    tot = np.zeros(draws)
    for u, nu in terms:
        if not u or u <= 0:
            continue
        if nu and math.isfinite(nu) and 0 < nu < 2000:
            # scaled t: z / sqrt(chi2_nu / nu), the same construction the tool uses
            z = rng.standard_normal(draws)
            chi = rng.chisquare(nu, draws)
            tot += u * z / np.sqrt(chi / nu)
        else:
            tot += u * rng.standard_normal(draws)
    lo, hi = np.percentile(tot, [2.5, 97.5])
    return (hi - lo) / 2


async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(TOOL); await pg.wait_for_timeout(1500)
        await pg.evaluate("goView('simple'); loadExample()"); await pg.wait_for_timeout(1300)
        await pg.evaluate("simpleAfterLoad()"); await pg.wait_for_timeout(1500)

        # ---------------- 1. reproducibility ----------------
        js_run = """(cfg)=>{ _mcSeed(cfg.seed); MC_DRAWS=cfg.draws; COV_RULE='mc'; BIAS_TREAT='rss';
            const c=poolContext(); const lv=c.levels[0]; const P=muPrim(c.stats[lv],c.k,lv);
            const out={}; ['iso','nordtest_mean','eurolab','cofrac'].forEach(m=>{
              const r=runModel(m,P); out[m]=r&&r.U?+r.U.toFixed(6):null;});
            return out;}"""
        a1 = await pg.evaluate(js_run, dict(seed=20914, draws=50000))
        a2 = await pg.evaluate(js_run, dict(seed=20914, draws=50000))
        a3 = await pg.evaluate(js_run, dict(seed=1, draws=50000))
        rep('same seed reproduces the interval exactly', a1 == a2, a1)
        rep('a different seed gives a different interval', a1 != a3, (a1['nordtest_mean'], a3['nordtest_mean']))
        unseeded = [await pg.evaluate(js_run, dict(seed=None, draws=50000)) for _ in range(2)]
        rep('unseeded runs differ, as they should', unseeded[0] != unseeded[1])

        # ---------------- 2. agreement with an independent Monte Carlo ----------------
        prim = await pg.evaluate("""()=>{
            COV_RULE='k2'; BIAS_TREAT='rss';
            const c=poolContext(); const lv=c.levels[0]; const P=muPrim(c.stats[lv],c.k,lv);
            const out={};
            ['iso','nordtest_mean','nordtest_rms','eurolab','cofrac','iso21748'].forEach(id=>{
              const m=MU_MODEL_BY_ID(id); const r=m.compute(P);
              const prec=r.prec.filter(t=>t&&t.u>0).map(t=>[t.u,t.nu]);
              const bU=r.bU||0, bNu=r.bNu||null;
              out[id]={terms:prec.concat(bU>0?[[bU,bNu]]:[]),
                       ucCorr:Math.sqrt(prec.reduce((a,t)=>a+t[0]*t[0],0)+bU*bU)};});
            return out;}""")
        print('\nMonte Carlo half-width, tool vs independent implementation (relative difference)')
        for mid, p in prim.items():
            terms = [(t[0], t[1]) for t in p['terms']]
            k_py = mc_python(terms) / p['ucCorr']
            k_tool = await pg.evaluate("""(cfg)=>{ _mcSeed(cfg.seed); MC_DRAWS=cfg.draws; COV_RULE='mc'; BIAS_TREAT='rss';
                const c=poolContext(); const lv=c.levels[0]; const P=muPrim(c.stats[lv],c.k,lv);
                const r=runModel(cfg.id,P); return r&&r.k?r.k:null;}""",
                dict(seed=20914, draws=200000, id=mid))
            d = abs(k_tool - k_py) / k_py
            # two independent Monte Carlo runs agree to within their own noise; 1 % is generous at
            # 200 000 / 400 000 draws and still far below the 3-10 % effect being measured
            rep('%-14s k_tool %.4f  k_python %.4f  (%.2f %%)' % (mid, k_tool, k_py, d * 100), d < 0.01)

        # ---------------- 3. consistency with the analytic arms ----------------
        iso_k = await pg.evaluate("""()=>{ _mcSeed(20914); MC_DRAWS=200000; COV_RULE='mc'; BIAS_TREAT='rss';
            const c=poolContext(); const lv=c.levels[0]; const P=muPrim(c.stats[lv],c.k,lv);
            return runModel('iso',P).k;}""")
        rep('with large degrees of freedom the draw collapses onto 1.96',
            abs(iso_k - 1.96) < 0.01, round(iso_k, 4))

        # the bias point estimate must not be drawn: doubling it must not change the coverage factor
        pair = await pg.evaluate("""()=>{
            const c=poolContext(); const lv=c.levels[0]; const P=muPrim(c.stats[lv],c.k,lv);
            const keep=P.nb.mean; const out=[];
            [1,2].forEach(f=>{ P.nb.mean=keep*f; _mcSeed(20914); MC_DRAWS=200000; COV_RULE='mc'; BIAS_TREAT='rss';
              out.push(+runModel('nordtest_mean',P).k.toFixed(6)); });
            P.nb.mean=keep; return out;}""")
        rep('doubling the bias point estimate leaves the coverage factor untouched',
            pair[0] == pair[1], pair)

        rep('no page errors', not errs, errs[:2])
        await pg.evaluate("COV_RULE='k2'; _mcSeed(null);")
        await b.close()

    print('\n%d failed' % len(fails))
    sys.exit(1 if fails else 0)


asyncio.run(main())
