#!/usr/bin/env python3
"""Same driver as run_models.py, but sweeping the coverage rule and the bias-treatment axis."""
import csv, collections
from playwright.sync_api import sync_playwright
import run_models as RM
import os
TOOL = 'file://' + os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'VerifyMyMU.html'))

COV=['k2','ws','mc']
BIAS=['rss','rssU','sumu','sumumax','ue']
def main():
    iqc,eqa=RM.load()
    levels=collections.defaultdict(list)
    for r in iqc:
        levels[r['test']].append(dict(lv=r['level'],mean=float(r['mean']),rw=float(r['u_Rw_pct']),df=int(r['n'])-1))
    out=[]
    with sync_playwright() as pw:
        b=pw.chromium.launch()
        pg=b.new_page(); pg.goto(TOOL); pg.wait_for_timeout(1200)
        for cov in COV:
            for bt in BIAS:
                for test in sorted(levels):
                    er=eqa.get(test)
                    if not er: continue
                    res=pg.evaluate(RM.JS,dict(rows=er,levels=levels[test],ucalKey=RM.IQC2UCAL[test],
                                               models=RM.MODELS,biasTreat=bt,covRule=cov))
                    for L in res['levels']:
                        for m in RM.MODELS:
                            v=L['models'].get(m) or {}
                            out.append(dict(cov=cov,bias=bt,test=test,level=L['lv'],model=m,
                                U=(round(v['U'],4) if v.get('U') is not None else ''),
                                uc=(round(v['uc'],4) if v.get('uc') is not None else ''),
                                k=(round(v['k'],4) if v.get('k') is not None else ''),
                                Uplus=v.get('Uplus') or '', Uminus=v.get('Uminus') or '',
                                nu=(v.get('nuEff') or ''), err=v.get('err','')))
        b.close()
    with open('data/results-axes.csv','w',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    print('rows',len(out))
if __name__=='__main__': main()
