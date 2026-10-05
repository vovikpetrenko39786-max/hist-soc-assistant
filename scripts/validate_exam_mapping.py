from __future__ import annotations
import json
from pathlib import Path
DATA=Path(__file__).resolve().parents[1]/"data"/"exam_mapping_seed_2027.json"
d=json.loads(DATA.read_text(encoding="utf-8"))
errors=[]
keys=set()
for m in d["models"]:
    if m["model_key"] in keys: errors.append(f"duplicate model key {m['model_key']}")
    keys.add(m["model_key"])
    if m["year"]==2027 and m["status"]!="project": errors.append(f"2027 model must remain project: {m['model_key']}")
    task_keys=set()
    for t in m.get("tasks",[]):
        if t["task_key"] in task_keys: errors.append(f"duplicate task key {m['model_key']}:{t['task_key']}")
        task_keys.add(t["task_key"])
        if not t.get("verification_status"): errors.append(f"missing verification status {m['model_key']}:{t['task_key']}")
    codes=set()
    for c in m.get("codifier_elements",[]):
        if c["code"] in codes: errors.append(f"duplicate codifier {m['model_key']}:{c['code']}")
        codes.add(c["code"])
        if not c.get("verification_status"): errors.append(f"missing verification {m['model_key']}:{c['code']}")
print(json.dumps({"models":len(d["models"]),"codifier_elements":sum(len(x.get("codifier_elements",[])) for x in d["models"]),"tasks":sum(len(x.get("tasks",[])) for x in d["models"]),"errors":errors},ensure_ascii=False,indent=2))
raise SystemExit(1 if errors else 0)
