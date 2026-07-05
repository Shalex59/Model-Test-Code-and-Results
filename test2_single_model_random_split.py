"""
TEST 2: Single-model test, data RANDOMLY split.
-----------------------------------------------
Instead of holding out a whole solvent group, the real recipes are split
randomly 75/25. The model therefore sees SOME examples of every solvent
group during training. This is a fairer test of whether the model can learn
the pattern when it isn't asked to generalize to totally unseen chemistry.

Same single-model setup and features as Test 1 (RDKit descriptors + conditions).
Averaged over 5 random splits. Requires PEG_filtered.xlsx in the same folder.
"""
import pandas as pd, numpy as np
from rdkit import Chem
from rdkit.Chem import Crippen, rdMolDescriptors
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
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
pos=[{'nl':r['nl'],'w':wfracs(r['nl'],r['Solvent Ratio'],r['Solvent Ratio Unit']),
 'temp':r['Temp'],'sp':r['Stationary Phase'],'bm':r['Base Material']} for _,r in rev.iterrows()]
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
N_FAIL=3
models={'RandomForest':lambda:RandomForestClassifier(n_estimators=400,max_depth=10,random_state=42,class_weight='balanced'),
        'XGBoost':lambda:XGBClassifier(n_estimators=400,max_depth=6,learning_rate=0.1,random_state=42,eval_metric='logloss')}
print("TEST 2: RANDOM SPLIT single model (75/25, 5 splits averaged)  [failures 3:1]\n")
for mname,mk in models.items():
    rrs=[];accs=[]
    for seed in [1,2,3,4,5]:
        tr,te=train_test_split(pos,test_size=0.25,random_state=seed)
        tf=[];[tf.extend(make_fail(r,N_FAIL)) for r in tr]
        ef=[];[ef.extend(make_fail(r,N_FAIL)) for r in te]
        Xtr=np.vstack([X(tr),X(tf)]);ytr=np.array([1]*len(tr)+[0]*len(tf))
        Xte=np.vstack([X(te),X(ef)]);yte=np.array([1]*len(te)+[0]*len(ef))
        sc=StandardScaler().fit(Xtr);clf=mk();clf.fit(sc.transform(Xtr),ytr)
        pred=clf.predict(sc.transform(Xte))
        accs.append(accuracy_score(yte,pred)*100)
        rrs.append(accuracy_score([1]*len(te),pred[:len(te)])*100)
    print(f"{mname}:")
    print(f"   overall accuracy:        {np.mean(accs):.1f}%  (range {min(accs):.1f}-{max(accs):.1f}%)")
    print(f"   real recipes recognized: {np.mean(rrs):.1f}%  (range {min(rrs):.1f}-{max(rrs):.1f}%)\n")

# ======================================================================
# RESULTS (failures 3:1, 5 random splits averaged). Numbers shift
# slightly run-to-run because failures are randomly generated.
# ======================================================================
#
# RandomForest
#    overall accuracy:        80.5%  (range 72.7-85.2%)
#    real recipes recognized: 74.5%  (range 50.0-90.9%)
#
# XGBoost
#    overall accuracy:        82.7%  (range 77.3-87.5%)
#    real recipes recognized: 72.7%  (range 59.1-81.8%)
#
# Interpretation: once the model sees SOME examples of every solvent
# group in training, real-recipe recognition jumps from near-zero
# (Test 1) to ~73%. The bottleneck in Test 1 was the unseen chemistry,
# not the model itself.
