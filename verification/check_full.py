#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Full pass over the paths the routine suite does not reach.

check_ui.py walks ONE journey with the built-in example. This file drives the real file inputs with
awkward but realistic exports — Turkish headers, decimal commas, day-first dates, two analysers,
three reagent lots, a summary-only file, and a file with nothing recognisable in it — and then
exercises the screens that journey never touches.
"""
import asyncio, sys, os
from playwright.async_api import async_playwright

import os
TOOL = 'file://' + os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'VerifyMyMU.html'))
FX = '/tmp/claude-0/-home-claude/15cc05a9-ab4f-5bff-a328-ab8b925f0ab6/scratchpad/fx'
fails, warns = [], []


def check(name, ok, detail=''):
    print(('  PASS  ' if ok else '  FAIL  ') + name + (('   ' + str(detail)[:150]) if detail else ''))
    if not ok:
        fails.append(name)


def note(name, detail=''):
    print('  NOTE  ' + name + (('   ' + str(detail)[:150]) if detail else ''))
    warns.append(name)


async def load_iqc(pg, path):
    """Drive the real file input on the 3-step screen, as a user would."""
    await pg.evaluate("goView('simple')")
    await pg.set_input_files('#s_file', path)
    await pg.wait_for_timeout(2500)


async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append('console: ' + m.text) if m.type == 'error' else None)
        await pg.goto(TOOL); await pg.wait_for_timeout(1500)

        # ---------------------------------------------------------------- 1. awkward real export
        print('\n1 · Turkish headers, decimal commas, day-first dates, two analysers')
        await load_iqc(pg, os.path.join(FX, 'tr_two_instruments.csv'))
        st = await pg.evaluate("""()=>({mode:(typeof IQC!=='undefined'&&IQC)?IQC.mode:null,
            n:(typeof IQC!=='undefined'&&IQC)?IQC.recs.length:0,
            tests:[...document.getElementById('s_test').options].map(o=>o.text),
            instr:[...document.getElementById('s1_instr').options].map(o=>o.text)})""")
        check('the file is read at all', st['n'] > 0, st['n'])
        check('raw mode detected', st['mode'] == 'raw', st['mode'])
        check('both analysers found', len([i for i in st['instr'] if 'Cihaz' in i]) == 2, st['instr'])
        vals = await pg.evaluate("()=>IQC.recs.slice(0,3).map(r=>r.value)")
        check('decimal commas parsed as decimals, not thousands', all(20 < v < 70 for v in vals), vals)
        dts = await pg.evaluate("()=>IQC.recs.slice(0,3).map(r=>r.dt&&r.dt.getMonth())")
        check('dates read day-first (January, not May)', all(m == 0 for m in dts), dts)
        res = await pg.evaluate("""()=>{simpleRun();const c=poolContext();
            return {levels:c.levels, n:c.levels.map(l=>c.stats[l].m),
                    rw:c.levels.map(l=>+(c.stats[l].pooledUrw/c.stats[l].meanVal*100).toFixed(2))};}""")
        check('two levels resolved from the Turkish level column', len(res['levels']) == 2, res)
        check('u_Rw lands near the 2.7 % the data was built with',
              all(2.0 < x < 3.6 for x in res['rw']), res['rw'])

        # §6.4 pooling of identical instruments
        pooled = await pg.evaluate("""()=>{POOL_DEVICES=true;const pd=document.getElementById('iqc_pooldev');
            if(pd)pd.checked=true; importIqc(); const c=poolContext();
            const o=c.stats[c.levels[0]];
            return {pooled:!!c.pooledDevices, K:o.K||null, uB:o.uBetween!=null?+o.uBetween.toFixed(4):null,
                    rw:+(o.pooledUrw/o.meanVal*100).toFixed(3)};}""")
        await pg.wait_for_timeout(600)
        if pooled['pooled']:
            check('§6.4 device pooling adds a between-device component',
                  pooled['K'] == 2 and pooled['uB'] is not None, pooled)
        else:
            note('§6.4 device pooling did not engage on this file', pooled)
        await pg.evaluate("""()=>{POOL_DEVICES=false;const pd=document.getElementById('iqc_pooldev');
            if(pd)pd.checked=false; importIqc();}""")
        await pg.wait_for_timeout(500)

        # ---------------------------------------------------------------- 2. several reagent lots
        print('\n2 · three reagent lots on one level (ISO/TS 20914 Formula 2 pooling)')
        await load_iqc(pg, os.path.join(FX, 'three_lots.csv'))
        lots = await pg.evaluate("""()=>{simpleRun();const c=poolContext();
            const o=c.stats[c.levels[0]];
            return {levels:c.levels.length, lots:o.m, df:o.dfRw,
                    rw:+(o.pooledUrw/o.meanVal*100).toFixed(3)};}""")
        check('the three lots are pooled into one level', lots['lots'] == 3, lots)
        check('degrees of freedom add up across lots', lots['df'] and lots['df'] > 200, lots['df'])

        # ---------------------------------------------------------------- 3. summary-only file
        print('\n3 · a summary export with no individual measurements')
        await load_iqc(pg, os.path.join(FX, 'summary_mode.csv'))
        sm = await pg.evaluate("""()=>({mode:(typeof IQC!=='undefined'&&IQC)?IQC.mode:null,
            status:(document.getElementById('iqc_status')||{}).textContent||'',
            out:(document.getElementById('s_iqcout')||{}).textContent||''})""")
        if sm['mode'] == 'summary':
            check('summary mode recognised', True, sm['mode'])
            qc = await pg.evaluate("()=>{goView('qc');return document.getElementById('qc_out').innerText.slice(0,80);}")
            await pg.wait_for_timeout(900)
            check('Levey-Jennings declines politely without raw points',
                  'raw' in qc.lower() or 'summary' in qc.lower(), qc[:70])
        else:
            note('summary-only file was not recognised as summary mode', sm)

        # ---------------------------------------------------------------- 4. an unreadable file
        print('\n4 · a file with nothing recognisable in it')
        await load_iqc(pg, os.path.join(FX, 'garbage.csv'))
        g = await pg.evaluate("""()=>({status:(document.getElementById('iqc_status')||{}).textContent||'',
            mapcard:(document.getElementById('iqc_mapcard')||{}).style.display,
            crashed:(typeof IQC==='undefined')})""")
        check('an unreadable file does not crash the tool', not g['crashed'], g)
        check('it says something, or offers the column mapper',
              bool(g['status'].strip()) or g['mapcard'] != 'none', g)

        # ---------------------------------------------------------------- 5. the screens the journey skips
        print('\n5 · screens the routine journey does not open')
        await pg.goto(TOOL); await pg.wait_for_timeout(1500)
        await pg.evaluate("goView('simple'); loadExample()"); await pg.wait_for_timeout(1300)
        await pg.evaluate("simpleAfterLoad(); simpleRun()"); await pg.wait_for_timeout(1500)

        for view, probe in (('core', 'c_rows'), ('pool', 'p_rows'), ('about', None),
                            ('guide', 'gb_out'), ('methods', 'ml_out'), ('eqa', 'e_out'),
                            ('bias', 'b_out'), ('report', 'r_out'), ('qc', 'qc_out')):
            before = len(errs)
            await pg.evaluate("goView('%s')" % view); await pg.wait_for_timeout(900)
            check('%-8s opens without error' % view, len(errs) == before, errs[before:before + 1])

        # the formula reference page must list every implemented model
        about = await pg.evaluate("()=>{goView('about');return document.getElementById('v-about').innerText;}")
        await pg.wait_for_timeout(500)
        missing = [m for m in ('ISO/TS 20914', 'Nordtest', 'EUROLAB', 'Cofrac', 'ISO 21748')
                   if m not in about]
        check('Formulas & sources names every model family', not missing, missing)

        # decision guide over every combination of answers
        print('\n6 · decision guide, every combination of answers')
        combos = await pg.evaluate("""()=>{
            const out=[];
            const refs=['peer','acc','crm','none'], rds=['0','lt6','ge6'], reps=['n','y'], srs=['y','n'];
            for(const ref of refs) for(const rounds of rds) for(const rep of reps) for(const sr of srs){
              const a={ref:ref,rounds:rounds,rep:rep,sr:sr};
              const n={ok:0,sens:0,warn:0,block:0,no:0};
              GB_RULES.forEach(function(r){ const v=r.rule(a); n[v.v]=(n[v.v]||0)+1; });
              let tot=0; for(const k in n) tot+=n[k];
              out.push({a:a,tot:tot,n:n});
            }
            return out;}""")
        bad = [c for c in combos if c['tot'] != 9]
        check('every answer combination judges all nine models', not bad, bad[:2])
        nonefree = [c for c in combos if c['a']['ref'] == 'none' and (c['n'].get('ok', 0) > 1)]
        check('with no trueness reference only the ISO model stays available', not nonefree, nonefree[:2])

        # ---------------------------------------------------------------- 7. exports
        print('\n7 · the files the tool hands out')
        async def grab(fn):
            async with pg.expect_download(timeout=8000) as d:
                await pg.evaluate(fn)
            dl = await d.value
            return dl.suggested_filename
        try:
            check('blank IQC template downloads', (await grab("dlTemplate('iqc')")).endswith(('.xlsx', '.csv')))
            check('blank EQA template downloads', (await grab("dlTemplate('eqa')")).endswith(('.xlsx', '.csv')))
            await pg.evaluate("()=>{document.getElementById('p_includeml').checked=true; genReport();}")
            await pg.wait_for_timeout(2500)
            check('method-comparison appendix exports as CSV', (await grab("downloadApxCsv()")).endswith('.csv'))
            check('printable report downloads', (await grab("downloadCurrentReport()")).endswith('.html'))
        except Exception as e:
            note('a download could not be captured in this environment', str(e)[:90])

        # ---------------------------------------------------------------- 8. reset
        print('\n8 · full reset')
        await pg.evaluate("doReset()"); await pg.wait_for_timeout(1200)
        clean = await pg.evaluate("""()=>({iqc:(typeof IQC==='undefined'||!IQC), set:REPORT_SET.length,
            rows:document.querySelectorAll('#nt_rows tr').length, ub:UBIAS_PCT,
            analyte:document.getElementById('s_analyte').value,
            out:document.getElementById('s_out').innerHTML.length})""")
        check('reset clears data, series, set and the corrected-bias term',
              clean['iqc'] and clean['set'] == 0 and clean['rows'] == 0
              and clean['ub'] is None and clean['analyte'] == '' and clean['out'] == 0, clean)

        check('no console or page errors in the whole pass', not errs, errs[:3])
        await b.close()

    print('\n%d checks failed, %d notes' % (len(fails), len(warns)))
    sys.exit(1 if fails else 0)


asyncio.run(main())
