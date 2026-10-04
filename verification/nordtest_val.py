import json,math
from playwright.sync_api import sync_playwright
import os
TOOL = 'file://' + os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'VerifyMyMU.html'))
# Nordtest TR 537 ed.4 App.4/App.9 — ammonium. sR is given as %, the tool wants the peer SD in
# the unit of the assigned value, so sd_abs = sR% * X / 100.
D=[(81,83,10,31),(73,75,7,36),(264,269,8,32),(210,213,10,35),(110,112,7,36),(140,144,11,34)]
ROWS=[[X,res,round(sR*X/100,6),n] for X,res,sR,n in D]
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(); errs=[]
    pg.on('pageerror',lambda e: errs.append('PAGEERR: '+str(e)))
    pg.on('console',lambda m: errs.append('CONSOLE: '+m.text) if m.type=='error' else None)
    pg.goto(TOOL); pg.wait_for_timeout(600)
    r=pg.evaluate(r"""(ROWS)=>{
      loadPoolEx();
      document.getElementById('p_analyte').value='Ammonium NH4-N (Nordtest TR 537 App.4)';
      document.getElementById('p_unit').value='ug/L';
      document.getElementById('p_k').value='2';
      document.getElementById('p_ucal').value='';          // Nordtest branch: no u_cal
      document.getElementById('p_cvi').value=''; document.getElementById('p_cvg').value='';
      document.getElementById('p_rows').innerHTML='';
      addPoolRow({lv:'Level 1',lot:'control sample',N:135,mean:200,urw:3.34});  // sRw 1.67 % of 200
      document.getElementById('p_mumethod').value='nordtest'; setMuMethod();
      document.getElementById('nt_rows').innerHTML='';
      ROWS.forEach(e=>addNtRow({X:e[0],res:e[1],sd:e[2],n:e[3]}));
      document.getElementById('nt_ucrefsrc').value='nordtest'; setUcrefSrc();
      calcNt();
      const nb=nordtestBias(); const c=poolContext(); const lv=c.levels[0]; const o=c.stats[lv];
      return {rounds:nb.rounds,biases:nb.rows.map(x=>+x.bias.toFixed(4)),
              ucref_i:nb.rows.map(x=>+x.uc.toFixed(4)),
              RMS:nb.RMSbias,uCref:nb.uCref,uBias:nb.uBias,
              uRw:o.pooledUrw/o.meanVal*100, U:o.pU};}""",ROWS)
    r['_errs']=errs; b.close()
PUB=dict(uRw=1.67,RMS=2.26,uCref=1.52,uBias=2.73,uc=3.20,U=6.4)
print("Nordtest TR 537 ed.4 — Appendix 4 / Appendix 9 ammonium example\n")
print(f"{'quantity':18s} {'TOOL':>10s} {'HANDBOOK':>8s} {'diff':>9s}")
rows=[('u_Rw %',r['uRw'],PUB['uRw']),('RMS_bias %',r['RMS'],PUB['RMS']),
      ('u(C_ref) %',r['uCref'],PUB['uCref']),('u(bias) %',r['uBias'],PUB['uBias']),
      ('u_c %',r['U']/2,PUB['uc']),('U % (k=2)',r['U'],PUB['U'])]
ok=True
for nm,a,pub in rows:
    d=a-pub; ok&= abs(d)<0.01
    print(f"{nm:18s} {a:10.4f} {pub:8.2f} {d:+9.4f}")
print("\nround bias %:", r['biases'])
print("u(Cref_i) %:", r['ucref_i'], " (handbook: 1.80 1.17 1.41 1.69 1.17 1.89)")
print("\nErrors:", r['_errs'] if r['_errs'] else 'none')
print("\n>>> TOOL REPRODUCES THE PUBLISHED EXAMPLE" if ok else "\n>>> MISMATCH")
