#!/usr/bin/env python3
"""Run the nine VerifyMyMU models for every analyte/level, inside the tool itself."""
import csv, json, collections, statistics
from playwright.sync_api import sync_playwright
import os
TOOL = 'file://' + os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'VerifyMyMU.html'))

IQC2UCAL={'S-Alb':'Albumin','S-ALP':'ALP','S-ALAT':'ALT','S-ASAT':'AST','S-Amyl':'Amylase',
 'S-Bili':'Total Bilirubin','S-CK':'CK','S-Kol':'Cholesterol','S-Kreat':'Creatinine','S-Kals':'Calcium',
 'S-Klorid':'Chloride','S-Jern':'Iron','S-Gluk':'Glucose','S-gGT':'GGT','S-HDL':'HDL Cholesterol',
 'S-Kalium':'Potassium','S-LD':'LDH','S-LDL':'LDL Cholesterol','S-Lipase':'Lipase','S-Mg':'Magnesium',
 'S-Na':'Sodium','S-Fosfat':'Phosphorus','S-Prot':'Total Protein','S-Trig':'Triglyceride','S-Urea':'Urea',
 'S-Urat':'Uric Acid','S-Trans':'Transferrin','S-IgA':'IgA','S-IgG':'IgG','S-IgM':'IgM'}
EQA2IQC={'Alb':'S-Alb','ALP':'S-ALP','ALT':'S-ALAT','AST':'S-ASAT','Amyl':'S-Amyl','Bil, tot':'S-Bili',
 'CK':'S-CK','Ca':'S-Kals','Chol':'S-Kol','Chol-HDL':'S-HDL','Chol-LDL':'S-LDL','Cl':'S-Klorid',
 'Crea':'S-Kreat','Fe':'S-Jern','GT':'S-gGT','Glucose':'S-Gluk','IgA':'S-IgA','IgG':'S-IgG','IgM':'S-IgM',
 'K':'S-Kalium','LD':'S-LD','Lipase':'S-Lipase','Mg':'S-Mg','Na':'S-Na','Pi':'S-Fosfat','Prot':'S-Prot',
 'Transf':'S-Trans','Trigly':'S-Trig','Urea':'S-Urea','Uric acid':'S-Urat'}
MODELS=['iso','iso_hybrid','nordtest_rms','nordtest_sem','nordtest_mean','eurolab','cofrac','cofrac_rms','iso21748']

def load():
    iqc=[r for r in csv.DictReader(open('data/iqc-summary.csv'))]
    eqa=collections.defaultdict(list)
    for r in csv.DictReader(open('data/eqa-final.csv')):
        if r['excluded']: continue
        t=EQA2IQC.get(r['analyte'])
        if not t: continue
        try:
            X=float(r['assigned'])
            # the per-round bias follows the stated rule (printed diff% when it carries a decimal,
            # otherwise recomputed); feed the tool a result consistent with that bias so that its
            # internal (res-X)/X reproduces it exactly
            res=X*(1+float(r['bias_used'])/100)
        except Exception: continue
        sd=r['group_sd'] if r['group_sd'] not in ('','-') and not r['group_sd'].startswith('<') else ''
        um=''
        if r['ucref_used']!='': um=float(r['ucref_used'])/100*X
        eqa[t].append(dict(X=X,res=res,sd=(float(sd) if sd else ''),n=(float(r['group_n']) if r['group_n'] else ''),
                           um=um,type=r['type'],round=r['round'],sample=r['sample']))
    return iqc,eqa

JS = r"""
(payload)=>{
  UCREF_SRC='reported'; PREC_SRC='pooled'; BIAS_TREAT=payload.biasTreat; COV_RULE=payload.covRule;
  EQA_TYPE_MODE='auto'; ML_ANOVA=null; ML_NREP=1; ML_CVREP=null; ML_NREP_EQA=1; ML_NUCAL=null;
  const body=document.getElementById('nt_rows'); body.innerHTML='';
  payload.rows.forEach(r=>{ addNtRow({}); });
  const trs=[...document.querySelectorAll('#nt_rows tr')];
  trs.forEach((tr,i)=>{ const r=payload.rows[i]; const inp=tr.querySelectorAll('input');
    inp[0].value=r.X; inp[1].value=r.res; inp[2].value=r.sd; inp[3].value=r.n; if(inp[4])inp[4].value=r.um;
    const sel=tr.querySelector('.nttype'); if(sel)sel.value=r.type; });
  const nb=nordtestBias();
  const out={eqaType:EQA_TYPE, nb:{rounds:nb.rounds,mean:nb.mean,sd:nb.sd,RMSbias:nb.RMSbias,uCref:nb.uCref,
      uMean:nb.uMean,range:nb.range,sR:nb.sR,pLab:nb.pLab,nTrace:nb.nTrace,nCons:nb.nCons,derived:nb.derived}, levels:[]};
  payload.levels.forEach(L=>{
    const ucalPct=getUcalPct(payload.ucalKey,L.mean,ROCHE_UCAL);
    const P={lv:L.lv,mean:L.mean,rw:L.rw,dfRw:L.df,ucal:(ucalPct!=null?ucalPct/2:null),dfUcal:null,
             nb:nb,anova:null,precNote:'pooled',k:2};
    const res={lv:L.lv,mean:L.mean,rw:L.rw,ucalPct:(ucalPct!=null?ucalPct/2:null),models:{}};
    payload.models.forEach(id=>{ const r=runModel(id,P);
      res.models[id]= r? (r.err? {err:r.err} : {uc:r.uc,U:r.U,k:r.k,nuEff:r.nuEff,bVal:r.bVal,bU:r.bU,uPrec:r.uPrec,Uplus:r.Uplus,Uminus:r.Uminus}) : null; });
    out.levels.push(res);
  });
  return out;
}
"""

def main():
    iqc,eqa=load()
    levels=collections.defaultdict(list)
    for r in iqc:
        levels[r['test']].append(dict(lv=r['level'],mean=float(r['mean']),rw=float(r['u_Rw_pct']),df=int(r['n'])-1))
    rows=[]
    with sync_playwright() as pw:
        b=pw.chromium.launch()
        pg=b.new_page()
        pg.goto(TOOL)
        pg.wait_for_timeout(1200)
        for test in sorted(levels):
            er=eqa.get(test,[])
            if not er: print('no EQA rows for',test); continue
            payload=dict(rows=er,levels=levels[test],ucalKey=IQC2UCAL[test],models=MODELS,
                         biasTreat='rss',covRule='k2')
            out=pg.evaluate(JS,payload)
            for L in out['levels']:
                base=dict(test=test,level=L['lv'],mean=L['mean'],u_Rw=L['rw'],u_cal=L['ucalPct'],
                          eqa_type=out['eqaType'],rounds=out['nb']['rounds'],mean_bias=out['nb']['mean'],
                          sd_bias=out['nb']['sd'],rms_bias=out['nb']['RMSbias'],u_Cref=out['nb']['uCref'])
                for m in MODELS:
                    v=L['models'].get(m) or {}
                    base['U_'+m]= round(v['U'],3) if v.get('U') is not None else v.get('err','')
                    base['uc_'+m]= round(v['uc'],3) if v.get('uc') is not None else ''
                rows.append(base)
        b.close()
    with open('data/results-k2-rss.csv','w',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print('levels computed:',len(rows))
    for r in rows[:4]: print({k:r[k] for k in list(r)[:8]})
if __name__=='__main__': main()
