import json
from pathlib import Path
DATA=Path(__file__).resolve().parents[1]/'data'/'source_catalog_seed_2026_2027.json'

def validate():
    d=json.loads(DATA.read_text(encoding='utf-8')); errors=[]
    keys=[s['key'] for s in d['sources']]
    if len(keys)!=len(set(keys)): errors.append('duplicate source keys')
    known=set(keys)
    for r in d['mapping_rules']:
        if r['source_key'] not in known: errors.append(f"unknown mapping source {r['source_key']}")
    fp=[s['fpu_number'] for s in d['sources'] if s.get('fpu_number')]
    if len(fp)!=len(set(fp)): errors.append('duplicate fpu numbers')
    for s in d['sources']:
        if s['source_type']=='textbook' and s.get('verification_status')=='verified_fpu' and not s.get('fpu_number'):
            errors.append(f"verified_fpu without fpu_number: {s['key']}")
        if s.get('availability_status')=='metadata_only' and s.get('file_path'):
            errors.append(f"metadata_only with file path: {s['key']}")
    print(json.dumps({'sources':len(d['sources']),'mapping_rules':len(d['mapping_rules']),'gaps':len(d.get('source_gaps',[])),'errors':errors},ensure_ascii=False,indent=2))
    raise SystemExit(1 if errors else 0)
if __name__=='__main__': validate()
