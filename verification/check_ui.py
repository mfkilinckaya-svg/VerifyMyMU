#!/usr/bin/env python3
"""UI-level regression: asserts what the SCREENS say, not what runModel() computes.

Every defect found on 28 September lived here, not in the model algebra: values typed in one
card never reaching the printed report, a chart that needed a button press, an exclusion that
updated two screens out of three, two screens giving the same model different verdicts. The
model cross-checks (check_models.py, check_axes.py) cannot see any of that by construction.

Each check is an assertion about the rendered page after a scripted user journey.
"""
import asyncio, re, sys
from playwright.async_api import async_playwright

import os
TOOL = 'file://' + os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'VerifyMyMU.html'))
results = []


def check(name, ok, detail=''):
    results.append((ok, name, detail))
    print(('  PASS  ' if ok else '  FAIL  ') + name + (('   ' + str(detail)) if detail else ''))


async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' else None)
        await pg.goto(TOOL); await pg.wait_for_timeout(1500)

        # ---------- journey: guide -> example -> definition -> result ----------
        await pg.evaluate("gbRender(); gbGoLab()"); await pg.wait_for_timeout(500)
        active = await pg.evaluate("()=>[...document.querySelectorAll('section.view')].filter(x=>x.classList.contains('active')).map(x=>x.id)")
        check('decision guide continues to the 3-step screen, not the axis panel', active == ['v-simple'], active)

        await pg.evaluate("loadExample()"); await pg.wait_for_timeout(1300)
        await pg.evaluate("simpleAfterLoad()"); await pg.wait_for_timeout(1500)
        await pg.evaluate("""()=>{document.getElementById('s_analyte').value='Albumin';
            document.getElementById('s_instr').value='Roche cobas 8000 (c701/c702)';
            document.getElementById('s_sample').value='Serum/Plasma'; setupStep();
            document.getElementById('s_device').value='c703'; setupStep();}""")
        await pg.wait_for_timeout(600)
        await pg.evaluate("simpleRun()"); await pg.wait_for_timeout(1200)

        # ---------- 1. the definition reaches the printed report ----------
        await pg.evaluate("genReport()"); await pg.wait_for_timeout(1500)
        rep = await pg.evaluate("()=>document.getElementById('r_out').innerText")
        for field, want in [('analyte', 'Albumin'), ('sample', 'Serum/Plasma'), ('instrument', 'c703')]:
            check('report header carries the %s typed in step 0' % field, want in rep, want)
        check('report shows no dash for the measurand', 'Amount of Albumin' in rep)

        # ---------- 2. the scheme type is read from the rounds, not from the guide answer ----------
        et = await pg.evaluate("()=>[EQA_TYPE, EQA_TYPE_MODE]")
        check('EQA scheme type derived automatically as traceable for albumin', et == ['accuracy', 'auto'], et)
        out = await pg.evaluate("()=>document.getElementById('s_out').innerText")
        check('result banner states where the scheme type came from', 'read from the 8 rounds' in out)

        # ---------- 3. the guide and the gate agree, model by model ----------
        for ref, lbl in (('acc', 'traceable'), ('peer', 'consensus')):
            dis = await pg.evaluate("""(ref)=>{
                document.getElementById('gb_ref').value=ref;
                document.getElementById('gb_rounds').value='ge6';
                document.getElementById('gb_rep').value='n';
                document.getElementById('gb_sr').value='y';
                const a={ref,rounds:'ge6',rep:'n',sr:'y'};
                EQA_TYPE=(ref==='peer')?'peer':'accuracy';
                /* The two screens must not CONTRADICT each other; they need not use the identical
                   word. The gate sees the data and can say WHY a caveat applies (a significant mean
                   bias), where the guide, which runs before any data is entered, can only say THAT
                   one applies. So the assertion is on the severity class, and word-level differences
                   are printed as information. */
                const CLS={ok:'use',sens:'caveat',warn:'caveat',block:'no',no:'missing'};
                const bad=[],note=[];
                GB_RULES.forEach(x=>{const m=MU_MODEL_BY_ID(x.id); if(!m)return;
                  const g=x.rule(a).v, t=modelStatus(m).s;
                  if(CLS[g]!==CLS[t]) bad.push(x.id+': guide='+g+' gate='+t);
                  else if(g!==t) note.push(x.id+': '+g+'/'+t);});
                return {bad,note};}""", ref)
            check('guide and result gate do not contradict for a %s target' % lbl,
                  dis['bad'] == [], dis['bad'] or ('same class, different wording: ' + ', '.join(dis['note']) if dis['note'] else ''))

        # ---------- 4. the SEM variant is flagged when the mean bias is significant ----------
        await pg.evaluate("EQA_TYPE_MODE='auto'; nordtestBias();")
        sem = await pg.evaluate("()=>modelStatus(MU_MODEL_BY_ID('nordtest_sem'))")
        check('SEM variant flagged: albumin mean bias is significant', sem['s'] == 'warn', sem['t'][:60])

        # ---------- 5. the chart is present, with the limit as its own bar ----------
        await pg.evaluate("goView('simple'); simpleRun()"); await pg.wait_for_timeout(1200)
        fig = await pg.evaluate("()=>document.querySelectorAll('#s_out figure').length")
        check('result screen draws the model-comparison chart', fig >= 1, fig)
        lim = await pg.evaluate("()=>apsLimits(null,null).map(l=>l.label+'='+l.v.toFixed(2))")
        check('chart carries EFLM desirable and minimum separately', len(lim) == 2, lim)
        cap = await pg.evaluate("()=>document.querySelector('#s_out figcaption').innerText")
        check('caption counts models against the limit', 'meet EFLM desirable' in cap)

        # ---------- 5b. the limit chosen in step 3 reaches the printed report ----------
        for setup, want_mu, want_src in (
                ("document.getElementById('s3_apssel').value='eflm_min'; simpleAps(false);", 3.75, 'EFLM minimum'),
                ("document.getElementById('s3_apssel').value='other'; simpleAps(false);"
                 "document.getElementById('s3_apsname').value='RCPA allowable';"
                 "document.getElementById('s3_aps').value='8'; simpleApsTyped();", 8.0, 'RCPA allowable')):
            await pg.evaluate("()=>{%s}" % setup); await pg.wait_for_timeout(400)
            await pg.evaluate("simpleRun(); genReport()"); await pg.wait_for_timeout(1600)
            got = await pg.evaluate("""()=>{const c=poolContext();
                return {mu:c.allow?c.allow.mu:null, src:c.allow?c.allow.src:null,
                        inReport:document.getElementById('r_out').innerText.indexOf('Allowable %U')>=0};}""")
            check('the record uses the limit chosen in step 3 (%s)' % want_src,
                  abs((got['mu'] or 0) - want_mu) < 1e-9 and got['src'] == want_src, got)
            check('the printed report states that limit (%s)' % want_src, got['inReport'])
        await pg.evaluate("()=>{document.getElementById('s3_apssel').value='none'; simpleAps(false); genReport();}")
        await pg.wait_for_timeout(1400)
        none_row = await pg.evaluate("()=>document.getElementById('r_out').innerText.indexOf('Allowable %U')>=0")
        check('choosing no limit prints no verdict rather than a stale one', not none_row)
        await pg.evaluate("()=>{document.getElementById('s3_apssel').value='eflm_des'; simpleAps(false);}")
        await pg.wait_for_timeout(400)

        # ---------- 5c. the CRM screen routes into the budget, both ways ----------
        await pg.evaluate("goView('bias'); loadBiasEx(); calcBias()"); await pg.wait_for_timeout(700)
        vis = await pg.evaluate("()=>({route:getComputedStyle(document.getElementById('b_route')).display,"
                                "corr:!document.getElementById('b_corr_btn').disabled})")
        check('CRM result offers the two routes, with the correction route enabled when significant',
              vis['route'] != 'none' and vis['corr'], vis)
        base = await pg.evaluate("()=>{const c=poolContext();const lv=c.levels[0];"
                                 "return +runModel('iso',muPrim(c.stats[lv],c.k,lv)).U.toFixed(4);}")
        await pg.evaluate("crmCorrected()"); await pg.wait_for_timeout(900)
        after = await pg.evaluate("()=>{const c=poolContext();const lv=c.levels[0];const P=muPrim(c.stats[lv],c.k,lv);"
                                  "return {U:+runModel('iso',P).U.toFixed(4), rec:+c.stats[lv].pU.toFixed(4),"
                                  " ub:P.ubiasCorr, field:document.getElementById('s3_ubias').value};}")
        import math as _m
        want = round(_m.hypot(base, 2 * after['ub']), 4)
        check('a corrected bias enters the ISO budget as a third component',
              abs(after['U'] - want) < 1e-3 and abs(after['rec'] - after['U']) < 1e-3,
              (base, after, want))
        await pg.evaluate("()=>{document.getElementById('b_mean').value='141.9'; calcBias(); crmCorrected();}")
        await pg.wait_for_timeout(600)
        msg = await pg.evaluate("()=>document.getElementById('b_routenote').innerText")
        check('an insignificant bias is refused for correction', 'not statistically significant' in msg)
        await pg.evaluate("()=>{document.getElementById('s3_ubias').value=''; setUbias();"
                          "loadBiasEx(); calcBias(); crmUseAsRef();}")
        await pg.wait_for_timeout(900)
        row = await pg.evaluate("""()=>{const r=[...document.querySelectorAll('#nt_rows tr')];
            const last=r[r.length-1]; const i=last.querySelectorAll('input');
            return {type:last.querySelector('.nttype').value, X:i[0].value, res:i[1].value, um:i[4].value};}""")
        check('the CRM can be used as a trueness reference (one Xref round)',
              row['type'] == 'Xref' and row['X'] == '141.8' and row['res'] == '143.4', row)
        await pg.evaluate("loadExampleEqa()"); await pg.wait_for_timeout(600)

        # ---------- 5d. the EQA screen holds no second copy of the bias series ----------
        await pg.evaluate("goView('eqa'); loadEqaSingle(); calcEqaSingle()"); await pg.wait_for_timeout(600)
        check('the duplicate multi-round table is gone', await pg.evaluate("()=>!document.getElementById('e_rows')"))
        before = await pg.evaluate("()=>document.querySelectorAll('#nt_rows tr').length")
        await pg.evaluate("""()=>{document.getElementById('e_sd').value='1.3';
            document.getElementById('e_n').value='63'; document.getElementById('e_type').value='Xt';
            calcEqaSingle(); eqaAddToSeries();}""")
        await pg.wait_for_timeout(800)
        row = await pg.evaluate("""()=>{const r=[...document.querySelectorAll('#nt_rows tr')];
            const last=r[r.length-1]; const i=last.querySelectorAll('input');
            return {n:r.length, type:last.querySelector('.nttype').value, sd:i[2].value, np:i[3].value};}""")
        check('a single round can be sent to the bias series with its target type and peer statistics',
              row['n'] == before + 1 and row['type'] == 'Xt' and row['sd'] == '1.3' and row['np'] == '63', row)
        warn = await pg.evaluate("""()=>{document.getElementById('nt_rows').innerHTML='';
            document.getElementById('e_sd').value=''; document.getElementById('e_n').value='';
            calcEqaSingle(); eqaAddToSeries();
            return document.getElementById('e_addnote').innerText;}""")
        await pg.wait_for_timeout(600)
        check('a round without peer SD or n is accepted but flagged as optimistic',
              'no u(C' in warn or 'optimistic' in warn, warn[:80])
        await pg.evaluate("()=>{document.getElementById('nt_rows').innerHTML=''; loadExampleEqa();}")
        await pg.wait_for_timeout(600)

        # ---------- 6. QC review draws itself on arrival ----------
        await pg.evaluate("goView('qc')"); await pg.wait_for_timeout(1800)
        qc = await pg.evaluate("()=>document.getElementById('qc_out').querySelectorAll('svg').length")
        check('Levey-Jennings charts appear without pressing a button', qc >= 1, qc)

        # ---------- 7. applying an exclusion updates the Estimate MU result too ----------
        before = await pg.evaluate("""()=>{const m=document.getElementById('s_out').innerText.match(/u\\s*Rw\\s*([\\d.]+)/);return m?m[1]:null;}""")
        await pg.evaluate("excludeBeyond(2)"); await pg.wait_for_timeout(700)
        during = await pg.evaluate("""()=>{const m=document.getElementById('s_out').innerText.match(/u\\s*Rw\\s*([\\d.]+)/);return m?m[1]:null;}""")
        check('marking points alone changes nothing', before == during, (before, during))
        await pg.evaluate("applyExclusions()"); await pg.wait_for_timeout(2200)
        after = await pg.evaluate("""()=>{const m=document.getElementById('s_out').innerText.match(/u\\s*Rw\\s*([\\d.]+)/);return m?m[1]:null;}""")
        check('Apply & recalculate refreshes the Estimate MU result', after != before, (before, after))
        await pg.evaluate("resetExcl(); applyExclusions()"); await pg.wait_for_timeout(1800)

        # ---------- 8. multi-analyte set survives starting the next analyte ----------
        await pg.evaluate("goView('simple'); simpleSaveAnalyte()"); await pg.wait_for_timeout(2000)
        n1 = await pg.evaluate("()=>REPORT_SET.length")
        await pg.evaluate("simpleNewAnalyte()"); await pg.wait_for_timeout(1200)
        n2 = await pg.evaluate("()=>[REPORT_SET.length, (typeof IQC==='undefined'||!IQC), document.getElementById('s_analyte').value]")
        check('saving an analyte adds it to the set', n1 == 1, n1)
        check('starting the next analyte keeps the set and clears the data', n2 == [1, True, ''], n2)

        # ---------- 9. no console errors anywhere in the journey ----------
        check('no console or page errors during the whole journey', not errs, errs[:3])

        await b.close()

    bad = [r for r in results if not r[0]]
    print('\n%d checks, %d failed' % (len(results), len(bad)))
    sys.exit(1 if bad else 0)


asyncio.run(main())
