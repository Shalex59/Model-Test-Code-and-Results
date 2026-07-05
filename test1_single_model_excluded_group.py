"""
TEST 1: Single-model test, one solvent group EXCLUDED (hold-out-by-group).
------------------------------------------------------------------------
An entire solvent group (e.g. all Methanol+Water recipes) is held out as the
test set. The model trains only on the OTHER groups plus synthetic failures,
then is asked to recognize the held-out group it has never seen.

This tests whether the model can GENERALIZE to unfamiliar chemistry.

Real recipes = confirmed successes (label 1).
Synthetic failures (label 0) are made by altering one factor of a real recipe.
Features: RDKit descriptors (logP, TPSA, HBD, HBA) + conditions.
Requires PEG_filtered.xlsx in the same folder.
"""
import pandas as pd, numpy as np
from rdkit import Chem
from rdkit.Chem import Crippen, rdMolDescriptors
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score

np.random.seed(42)
SMILES={'Water':'O','Acetone':'CC(=O)C','Acetonitrile':'CC#N','Methanol':'CO',
'Tetrahydrofuran':'C1CCOC1','Dimethylformamide':'CN(C)C=O','Hexane':'CCCCCC',
'Heptane':'CCCCCCC','Chloroform':'C(Cl)(Cl)Cl','Pyridine':'c1ccncc1','Dimethoxyethane':'COCCOC'}
DENSITY={'Water':0.997,'Acetone':0.784,'Acetonitrile':0.786,'Methanol':0.792,
'Tetrahydrofuran':0.889,'Dimethylformamide':0.944,'Hexane':0.655,'Heptane':0.684,
'Chloroform':1.489,'Pyridine':0.982,'Dimethoxyethane':0.868}
ALL=list(SMILES.keys())
def desc(n):
    m=Chem.MolFromSmiles(SMILES[n])
    return np.array([Crippen.MolLogP(m),rdMolDescriptors.CalcTPSA(m),
                     rdMolDescriptors.CalcNumHBD(m),rdMolDescriptors.CalcNumHBA(m)])
DESC={s:desc(s) for s in ALL}
def clean(s): return s.replace('(near crit)','').strip().rstrip(',').strip()
def names(s): return [clean(x) for x in str(s).split(',') if clean(x)]
def wfracs(nl,rs,unit):
    vals=[float(x) for x in str(rs).replace(' ','').split(',') if x and '-' not in x]
    v=np.array(vals); v=v/v.sum()
    if unit=='vol':
        d=np.array([DENSITY[n] for n in nl]); w=v*d; w=w/w.sum()
    else: w=v
    return w
def feat(nl,w,temp,sp,bm):
    mix=np.zeros(4)
    for n,ww in zip(nl,w): mix+=ww*DESC[n]
    return np.concatenate([mix,[len(nl),max(w),temp,hash(str(sp))%1000,hash(str(bm))%1000]])
df=pd.read_excel('PEG_filtered.xlsx')
df['Temp']=pd.to_numeric(df['Temperature (Celsius)'],errors='coerce').fillna(25.0)
rev=df[df['Phase']=='Reverse'].copy(); rev['nl']=rev['Solvents'].apply(names)
rev=rev[rev['nl'].apply(len)>1].reset_index(drop=True)
pos=pd.DataFrame([{'nl':r['nl'],'w':wfracs(r['nl'],r['Solvent Ratio'],r['Solvent Ratio Unit']),
 'temp':r['Temp'],'sp':r['Stationary Phase'],'bm':r['Base Material'],
 'pair':' + '.join(sorted(r['nl']))} for _,r in rev.iterrows()])
def make_fail(row,n):
    out=[]
    for _ in range(n):
        nl=list(row['nl']);w=list(row['w']);temp=row['temp'];sp=row['sp'];bm=row['bm']
        k=np.random.choice(['ratio','temp','swap','sp','bm'])
        if k=='ratio':
            i=np.random.randint(len(w));w[i]=min(max(w[i]+np.random.choice([-1,1])*np.random.uniform(.25,.45),.01),.99)
        elif k=='temp':temp=temp+np.random.choice([-1,1])*np.random.uniform(30,55)
        elif k=='swap':
            i=np.random.randint(len(nl));alt=[s for s in ALL if s not in nl];nl[i]=np.random.choice(alt)
        elif k=='sp':sp=str(sp)+"_ALT"+str(np.random.randint(99))
        elif k=='bm':bm=str(np.random.choice(['Silica','PS/DVB','BEH']))+"_ALT"
        w=np.array(w);w=w/w.sum(); out.append({'nl':nl,'w':w,'temp':temp,'sp':sp,'bm':bm})
    return out
def X(rows): return np.array([feat(r['nl'],r['w'],r['temp'],r['sp'],r['bm']) for r in rows])
pairs=['Methanol + Water','Acetonitrile + Water','Acetone + Water']; N_FAIL=3
models={'RandomForest':lambda:RandomForestClassifier(n_estimators=400,max_depth=10,random_state=42,class_weight='balanced'),
        'XGBoost':lambda:XGBClassifier(n_estimators=400,max_depth=6,learning_rate=0.1,random_state=42,eval_metric='logloss')}
print("TEST 1: ONE SOLVENT GROUP EXCLUDED (hold-out-by-group)  [failures 3:1]\n")
for mname,mk in models.items():
    print("="*60);print(mname);print("="*60)
    print(f"{'Held-out group':<24}{'overall':>9}{'real recog':>12}{'fail caught':>12}")
    for held in pairs:
        tr=pos[pos['pair']!=held].to_dict('records'); te=pos[pos['pair']==held].to_dict('records')
        tf=[];[tf.extend(make_fail(r,N_FAIL)) for r in tr]
        ef=[];[ef.extend(make_fail(r,N_FAIL)) for r in te]
        Xtr=np.vstack([X(tr),X(tf)]);ytr=np.array([1]*len(tr)+[0]*len(tf))
        Xte=np.vstack([X(te),X(ef)]);yte=np.array([1]*len(te)+[0]*len(ef))
        sc=StandardScaler().fit(Xtr);clf=mk();clf.fit(sc.transform(Xtr),ytr)
        pred=clf.predict(sc.transform(Xte))
        acc=accuracy_score(yte,pred)*100
        rr=accuracy_score([1]*len(te),pred[:len(te)])*100
        fc=accuracy_score([0]*len(ef),pred[len(te):])*100
        print(f"{held:<24}{acc:>8.1f}%{rr:>11.1f}%{fc:>11.1f}%")
    print()

# ======================================================================
# RESULTS (failures 3:1). Numbers shift slightly run-to-run because the
# synthetic failures are randomly generated.
# ======================================================================
#
# RandomForest
# Held-out group            overall  real recog  fail caught
# Methanol + Water            75.0%       0.0%      100.0%
# Acetonitrile + Water        76.1%       8.7%       98.6%
# Acetone + Water             79.3%      21.7%       98.6%
#
# XGBoost
# Held-out group            overall  real recog  fail caught
# Methanol + Water            71.1%      12.5%       90.6%
# Acetonitrile + Water        73.9%       8.7%       95.7%
# Acetone + Water             76.1%      13.0%       97.1%
#
# Interpretation: overall accuracy looks high only because the many
# synthetic failures are easy to catch. The model recognizes almost none
# of the held-out group's REAL recipes (0-21%), because it never saw that
# group's chemistry in training. It cannot generalize to an unseen group.
