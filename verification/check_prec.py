#!/usr/bin/env python3
"""Independent check of the ANOVA precision path and the u(C_ref) source axis.

check_axes.py verified the coverage and bias-treatment axes but held the other two fixed:
precision source = pooled, u(C_ref) source = provider-reported. Those two were therefore
unverified. This file re-implements both from the raw data and compares with the tool.

  1. ANOVA  — ISO 5725-2:2025 8.4.5.2 Formula (6), unbalanced one-way random effects, with DAY
              as the grouping factor, nested inside (lot x instrument) so lot and device shifts
              do not leak into s_r. Negative between-day components clamped to zero (8.4.5.4).
  2. u(Cref)— Nordtest TR 537 ed.4 p.21/p.22 and ISO 13528 7.7, the four sources the tool offers,
              with the rule that a traceable target always takes the provider's own u.
"""
import asyncio, csv, math, collections, sys
from datetime import datetime
from playwright.async_api import async_playwright

import os
TOOL = 'file://' + os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'VerifyMyMU.html'))
IQC_CSV = os.path.join(os.path.dirname(__file__), '..', 'examples', 'example-IQC-albumin.csv')
fails = []


def rep(name, ok, detail=''):
    print(('  PASS  ' if ok else '  FAIL  ') + name + (('   ' + str(detail)) if detail else ''))
    if not ok:
        fails.append(name)


# ---------------------------------------------------------------- 1. ANOVA in Python
def anova_from_csv(path, lot_level=None):
    """Same nesting as the tool: level -> (lot, instrument) -> day.

    The tool labels a level by the grouping the MU Record produced ("Level 1"), not by the text in
    the file's Level column ("ClinChem 2"), so the lot -> level map is taken from the tool and the
    raw rows are re-keyed with it. Comparing on the file's own labels would have compared nothing.
    """
    rows = []
    for r in csv.DictReader(open(path)):
        try:
            v = float(r['Result'])
        except (ValueError, KeyError):
            continue
        dt = datetime.strptime(r['Date'].strip(), '%d/%m/%Y %H:%M:%S')
        lot = r['Control lot'].strip()
        lv = (lot_level or {}).get(lot, r['Level'].strip())
        rows.append((lv, (lot, r['Instrument'].strip()),
                     (dt.year, dt.month, dt.day), v))

    by_lv = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
    for lv, sub, day, v in rows:
        by_lv[lv][sub][day].append(v)

    out = {}
    for lv, subs in by_lv.items():
        ssW = ssB = 0.0
        dfW = dfB = Ntot = aTot = g = 0
        n0num = sumVal = 0.0
        multi = 0
        for sub, days in subs.items():
            groups = list(days.values())
            a, N = len(groups), sum(len(x) for x in groups)
            if a < 2 or N <= a:
                continue
            m = sum(sum(x) for x in groups) / N
            sN2 = 0.0
            for gg in groups:
                n = len(gg)
                mi = sum(gg) / n
                ssW += sum((v - mi) ** 2 for v in gg)
                ssB += n * (mi - m) ** 2
                sN2 += n * n
                if n > 1:
                    multi += 1
            dfW += N - a; dfB += a - 1; Ntot += N; aTot += a; g += 1
            n0num += sN2 / N; sumVal += m * N
        if g == 0 or dfW < 3 or dfB < 2 or multi < 3:
            out[lv] = None
            continue
        msW, msB = ssW / dfW, ssB / dfB
        n0 = (Ntot - n0num) / max(1, aTot - g)
        sr2 = msW
        sbd2 = max(0.0, (msB - msW) / n0)
        grand = sumVal / Ntot
        out[lv] = dict(sr=math.sqrt(sr2), sbd=math.sqrt(sbd2), sTot=math.sqrt(sr2 + sbd2),
                       srPct=math.sqrt(sr2) / grand * 100, sTotPct=math.sqrt(sr2 + sbd2) / grand * 100,
                       dfr=dfW, dfb=dfB, nObs=Ntot, n0=n0, mean=grand)
    return out


# ---------------------------------------------------------------- 2. u(Cref) in Python
def ucref_python(rounds, src):
    """rounds: list of dicts X, sd, n, umRep, traceable. Returns the mean u(Cref) in per cent."""
    vals = []
    for r in rounds:
        base = (r['sd'] / r['X'] * 100) / math.sqrt(r['n']) if (r['sd'] and r['n']) else 0.0
        if r['traceable']:
            uc = (r['umRep'] / r['X'] * 100) if r['umRep'] else 1.25 * base
        elif src == 'iso13528':
            uc = 1.25 * base
        elif src == 'reported':
            uc = (r['umRep'] / r['X'] * 100) if r['umRep'] else base
        elif src == 'reportedU':
            uc = ((r['umRep'] / 2) / r['X'] * 100) if r['umRep'] else base
        else:                                   # nordtest: classical s_R/sqrt(p)
            uc = base
        vals.append(uc)
    return sum(vals) / len(vals)


EXAMPLE_ROUNDS_JS = "() => [...document.querySelectorAll('#nt_rows tr')].map(tr=>{" \
    "const i=tr.querySelectorAll('input'); const t=tr.querySelector('.nttype');" \
    "return {X:parseFloat(i[0].value), res:parseFloat(i[1].value), sd:parseFloat(i[2].value)," \
    " n:parseFloat(i[3].value), umRep:(i[4]&&i[4].value!=='')?parseFloat(i[4].value):null," \
    " ttype:t?t.value:'Xrob'};})"


async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(TOOL); await pg.wait_for_timeout(1500)
        await pg.evaluate("goView('simple'); loadExample()"); await pg.wait_for_timeout(1300)
        await pg.evaluate("simpleAfterLoad()"); await pg.wait_for_timeout(1500)

        # ---------------- ANOVA ----------------
        lot_level = await pg.evaluate("()=>{const g=iqcGroups();const m={};"
                                      "if(g&&g.rows)g.rows.forEach(r=>{if(r.lot!=null)m[String(r.lot)]=r.lv;});return m;}")
        mine = anova_from_csv(IQC_CSV, lot_level)
        theirs = await pg.evaluate("()=>{ML_ANOVA=dayAnovaByLevel();return ML_ANOVA;}")
        print('ANOVA — variance components, tool vs independent re-implementation')
        for lv in sorted(theirs):
            t, m = theirs[lv], mine.get(lv)
            if t is None or m is None:
                rep('level %s: both decline to split the components' % lv, t is None and m is None)
                continue
            for field in ('sr', 'sbd', 'sTot'):
                d = abs(t[field] - m[field]) / max(1e-12, m[field]) if m[field] else abs(t[field])
                rep('%-12s %-5s  tool %.6f  python %.6f' % (lv, field, t[field], m[field]), d < 1e-6)
            rep('%-12s degrees of freedom %d/%d' % (lv, t['dfr'], t['dfb']),
                t['dfr'] == m['dfr'] and t['dfb'] == m['dfb'], (m['dfr'], m['dfb']))
            rep('%-12s n0 (unbalanced estimator)  tool %.6f  python %.6f' % (lv, t['n0'], m['n0']),
                abs(t['n0'] - m['n0']) < 1e-9)

        # the ANOVA figure must also be the one the models use when that axis is selected
        got = await pg.evaluate("""()=>{const out={};
            const c=poolContext();
            ['pooled','anova'].forEach(src=>{PREC_SRC=src; ML_ANOVA=dayAnovaByLevel();
              const lv=c.levels[0]; const P=muPrim(c.stats[lv],c.k,lv);
              out[src]={rw:P.rw, df:P.dfRw, note:P.precNote, lv};});
            PREC_SRC='pooled'; return out;}""")
        lv0 = got['pooled']['lv']
        exp = mine.get(lv0)
        rep('selecting the ANOVA axis feeds s_total into the models',
            exp is not None and abs(got['anova']['rw'] - exp['sTotPct']) < 1e-6,
            '%s: tool %.6f vs python %.6f' % (lv0, got['anova']['rw'], exp['sTotPct'] if exp else float('nan')))
        rep('the two precision sources really differ', abs(got['anova']['rw'] - got['pooled']['rw']) > 1e-9,
            '%.4f vs %.4f %%' % (got['anova']['rw'], got['pooled']['rw']))

        # ---------------- u(Cref) ----------------
        print('\nu(C_ref) source axis — tool vs independent re-implementation')
        rounds_raw = await pg.evaluate(EXAMPLE_ROUNDS_JS)
        rounds = [dict(X=r['X'], sd=r['sd'], n=r['n'], umRep=r['umRep'],
                       traceable=r['ttype'] in ('Xt', 'Xref')) for r in rounds_raw
                  if r['X'] and not math.isnan(r['X'])]
        rep('example rounds read back from the table', len(rounds) == 8, len(rounds))

        for src in ('nordtest', 'iso13528', 'reported', 'reportedU'):
            tool_uc = await pg.evaluate("(s)=>{UCREF_SRC=s; const nb=nordtestBias(); return nb?nb.uCref:null;}", src)
            mine_uc = ucref_python(rounds, src)
            d = abs(tool_uc - mine_uc) / max(1e-12, mine_uc)
            rep('u(Cref) source %-10s  tool %.6f  python %.6f' % (src, tool_uc, mine_uc), d < 1e-9)

        # Albumin's rounds are all traceable, so the four sources cannot differ on it. The axis is
        # therefore exercised on a consensus measurand — ALT, 12 real Labquality rounds, Xrob —
        # otherwise "verified" would mean only that an inert control was inert.
        ALT = [dict(X=90, res=86, sd=3.9, n=86, um=0.556 / 100 * 90),
               dict(X=73, res=71, sd=3.9, n=86, um=0.685 / 100 * 73),
               dict(X=85, res=82, sd=3.6, n=84, um=0.588 / 100 * 85),
               dict(X=60, res=57, sd=3.8, n=83, um=0.833 / 100 * 60),
               dict(X=114.6, res=105.0, sd=8.7, n=133, um=0.785 / 100 * 114.6),
               dict(X=79.4, res=74.9, sd=4.1, n=133, um=0.504 / 100 * 79.4),
               dict(X=70.6, res=66.2, sd=4.7, n=124, um=0.708 / 100 * 70.6),
               dict(X=87.2, res=82.0, sd=4.0, n=124, um=0.459 / 100 * 87.2)]
        await pg.evaluate("""(rows)=>{const b=document.getElementById('nt_rows'); b.innerHTML='';
            rows.forEach(r=>addNtRow({type:'Xrob',X:r.X,res:r.res,sd:r.sd,n:r.n,um:r.um})); calcNt();}""", ALT)
        await pg.wait_for_timeout(400)
        cons = [dict(X=r['X'], sd=r['sd'], n=r['n'], umRep=r['um'], traceable=False) for r in ALT]
        seen = {}
        for src in ('nordtest', 'iso13528', 'reported', 'reportedU'):
            tool_uc = await pg.evaluate("(s)=>{UCREF_SRC=s;const nb=nordtestBias();return nb?nb.uCref:null;}", src)
            mine_uc = ucref_python(cons, src)
            seen[src] = tool_uc
            d = abs(tool_uc - mine_uc) / max(1e-12, mine_uc)
            rep('consensus rounds, u(Cref) %-10s  tool %.6f  python %.6f' % (src, tool_uc, mine_uc), d < 1e-9)
        rep('the four sources really do differ on a consensus target',
            len(set(round(v, 9) for v in seen.values())) >= 3, {k: round(v, 4) for k, v in seen.items()})
        rep('ISO 13528 is exactly 1.25 x the classical form',
            abs(seen['iso13528'] - 1.25 * seen['nordtest']) < 1e-12)
        rep('the expanded reading is exactly half the standard one',
            abs(seen['reportedU'] - seen['reported'] / 2) < 1e-12)
        # restore the albumin rounds
        await pg.evaluate("loadExampleEqa()"); await pg.wait_for_timeout(500)

        # a traceable round must ignore the peer SD whatever the axis says
        spread = []
        for src in ('nordtest', 'iso13528', 'reported', 'reportedU'):
            spread.append(await pg.evaluate("(s)=>{UCREF_SRC=s;const nb=nordtestBias();return nb.uCref;}", src))
        allt = all(r['traceable'] for r in rounds)
        rep('all albumin rounds are traceable, so the axis cannot move u(Cref)',
            (not allt) or (max(spread) - min(spread) < 1e-12), '%s -> %s' % (allt, [round(x, 6) for x in spread]))
        await pg.evaluate("UCREF_SRC='iso13528'")

        rep('no page errors', not errs, errs[:2])
        await b.close()

    print('\n%d failed' % len(fails))
    sys.exit(1 if fails else 0)


asyncio.run(main())
