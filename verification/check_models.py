#!/usr/bin/env python3
"""Independent re-implementation of the nine models, compared with the tool's output.
Nothing here imports the tool: u_Rw comes from the IQC summary, the bias primitives are
recomputed from the per-round EQA file, and u_cal is typed in from the C.f.a.s. sheets."""
import csv, math, statistics, collections

# u_cal: calibrator value v and EXPANDED U_cal as printed on the c703 row (ACN in the comment)
UCAL={ # test : (v, U_cal, acn)
 'S-Alb':(28.2,0.264,'20100 ALBP/BCP'), 'S-ALP':(246,1.58,'20110'), 'S-ALAT':(103,0.686,'20140'),
 'S-ASAT':(105,0.859,'20230'), 'S-Amyl':(185,1.40,'20170'), 'S-Bili':(73.2,0.498,'20312'),
 'S-CK':(341,2.52,'20420'), 'S-Kol':(4.18,0.0358,'20411'), 'S-Kreat':(336,2.88,'20460'),
 'S-Kals':(2.68,0.0217,'20340'), 'S-Jern':(35.6,0.228,'20770'), 'S-Gluk':(10.7,0.0886,'20620/20630'),
 'S-gGT':(144,0.933,'20600'), 'S-LD':(267,1.45,'20810'), 'S-Lipase':(93.3,0.677,'20850'),
 'S-Mg':(1.10,0.00698,'20890'), 'S-Fosfat':(1.68,0.0103,'20990'), 'S-Prot':(50.5,0.269,'21110'),
 'S-Trig':(1.54,0.0181,'21130'), 'S-Urea':(16.9,0.314,'UREAL'), 'S-Urat':(306,2.31,'21170'),
 'S-Trans':(2.69,0.0385,'21150'), 'S-IgA':(4.20,0.0589,'20720'), 'S-IgG':(18.8,0.201,'20740'),
 'S-IgM':(1.47,0.0182,'20750'), 'S-HDL':(1.69,0.0302,'20710'), 'S-LDL':(3.54,0.0400,'20820'),
 # ISE: printed maximum bound a converted as rectangular, u = a/sqrt(3); table stores 2*u
 'S-Na':[(120,0.506567),(160,0.738546)], 'S-Kalium':[(3,0.014087),(7,0.032909)],
 'S-Klorid':[(80,0.480702),(120,0.720995)]}
EQA2IQC={'Alb':'S-Alb','ALP':'S-ALP','ALT':'S-ALAT','AST':'S-ASAT','Amyl':'S-Amyl','Bil, tot':'S-Bili',
 'CK':'S-CK','Ca':'S-Kals','Chol':'S-Kol','Chol-HDL':'S-HDL','Chol-LDL':'S-LDL','Cl':'S-Klorid',
 'Crea':'S-Kreat','Fe':'S-Jern','GT':'S-gGT','Glucose':'S-Gluk','IgA':'S-IgA','IgG':'S-IgG','IgM':'S-IgM',
 'K':'S-Kalium','LD':'S-LD','Lipase':'S-Lipase','Mg':'S-Mg','Na':'S-Na','Pi':'S-Fosfat','Prot':'S-Prot',
 'Transf':'S-Trans','Trigly':'S-Trig','Urea':'S-Urea','Uric acid':'S-Urat'}

def ucal_pct(test,conc):
    e=UCAL[test]
    if isinstance(e,list):                     # level-dependent (ISE)
        v,u=min(e,key=lambda l:abs(l[0]-conc)) # nearest printed level
        return (u/v*100)/2                     # stored value is expanded (2u) -> standard
    v,U,_=e
    return (U/v*100)/2                         # U_cal is k=2 -> u_cal

def bias_primitives(rows):
    b=[(r['res']-r['X'])/r['X']*100 for r in rows]
    n=len(b); mean=statistics.mean(b); sd=statistics.stdev(b) if n>1 else 0.0
    rms=math.sqrt(sum(x*x for x in b)/n)
    uc=statistics.mean([r['u']/r['X']*100 for r in rows])
    sRel=[r['sd']/r['X']*100 for r in rows if r['sd'] is not None]
    sR=math.sqrt(sum(x*x for x in sRel)/len(sRel)) if sRel else None
    ns=[r['n'] for r in rows if r['n']]
    p=statistics.mean(ns) if ns else None
    return dict(n=n,mean=mean,sd=sd,rms=rms,uCref=uc,rng=max(b)-min(b),
                uMean=math.sqrt((sd*sd/n if n>1 else 0)+uc*uc),sR=sR,p=p)

def models(rw,ucal,B):
    m,sd,n,uc=abs(B['mean']),B['sd'],B['n'],B['uCref']
    out={}
    out['iso']=math.sqrt(rw*rw+ucal*ucal)
    out['iso_hybrid']=math.sqrt(rw*rw+ucal*ucal+m*m+B['uMean']**2)
    out['nordtest_rms']=math.sqrt(rw*rw+B['rms']**2+uc*uc)
    out['nordtest_sem']=math.sqrt(rw*rw+B['uMean']**2)
    out['nordtest_mean']=math.sqrt(rw*rw+m*m+B['uMean']**2)
    out['eurolab']=math.sqrt(rw*rw+m*m+uc*uc+rw*rw)          # CV_rep = u_Rw, n_rep = 1
    out['cofrac']=math.sqrt(rw*rw+(m/math.sqrt(3))**2+sd*sd)
    out['cofrac_rms']=math.sqrt(rw*rw+(B['rms']/math.sqrt(3))**2+sd*sd)
    if B['sR'] and B['p']:
        sR,p=B['sR'],B['p']; sL=math.sqrt(max(0,sR*sR-rw*rw))
        out['iso21748']=math.sqrt(rw*rw+sL*sL+(sR*sR)/p)      # n_rep(EQA)=1
    return {k:2*v for k,v in out.items()}                     # k = 2

eqa=collections.defaultdict(list)
for r in csv.DictReader(open('data/eqa-final.csv')):
    if r['excluded']: continue
    t=EQA2IQC.get(r['analyte'])
    if not t: continue
    X=float(r['assigned']); res=X*(1+float(r['bias_used'])/100)
    sd=None
    if r['group_sd'] and not r['group_sd'].startswith('<') and r['group_sd']!='-':
        sd=float(r['group_sd'])
    u=float(r['ucref_used'])/100*X if r['ucref_used'] else 0.0
    eqa[t].append(dict(X=X,res=res,sd=sd,n=float(r['group_n']) if r['group_n'] else None,u=u))

tool={(r['test'],r['level']):r for r in csv.DictReader(open('data/results-k2-rss.csv'))}
MOD=['iso','iso_hybrid','nordtest_rms','nordtest_sem','nordtest_mean','eurolab','cofrac','cofrac_rms','iso21748']
worst=0; bad=[]; nchk=0; ucal_diff=[]
for r in csv.DictReader(open('data/iqc-summary.csv')):
    t,lv=r['test'],r['level']
    if t not in eqa: continue
    rw=float(r['u_Rw_pct']); mean=float(r['mean'])
    uc=ucal_pct(t,mean)
    B=bias_primitives(eqa[t])
    mine=models(rw,uc,B)
    tr=tool.get((t,lv))
    if not tr: continue
    d=abs(uc-float(tr['u_cal']))
    if d>1e-6: ucal_diff.append((t,lv,round(uc,4),round(float(tr['u_cal']),4)))
    for m in MOD:
        if m not in mine or not tr['U_'+m]: continue
        nchk+=1
        diff=abs(mine[m]-float(tr['U_'+m]))
        rel=diff/max(1e-9,float(tr['U_'+m]))
        worst=max(worst,rel)
        if rel>0.005: bad.append((t,lv,m,round(mine[m],3),float(tr['U_'+m])))
print('compared %d model results'%nchk)
print('largest relative difference: %.2e'%worst)
print('mismatches >0.5%%:',len(bad))
for x in bad[:15]: print('   ',x)
print('u_cal differences:',ucal_diff if ucal_diff else 'none')
