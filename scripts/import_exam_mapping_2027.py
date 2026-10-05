"""Import universal exam models and codifier/task metadata for 2027 projects.

Important: 2027 models are project documents as of 2026-10-05.
The importer preserves verification_status and never upgrades project/baseline data to final automatically.
"""
from __future__ import annotations
import argparse, asyncio, json
from pathlib import Path
from sqlalchemy import delete, select
from app.db.session import SessionLocal
from app.models.exam import CodifierElement, ExamModel, ExamResource, ExamTask

DEFAULT_DATASET=Path(__file__).resolve().parents[1]/"data"/"exam_mapping_seed_2027.json"

async def import_dataset(path: Path):
    data=json.loads(path.read_text(encoding="utf-8"))
    counts={"models":0,"resources":0,"codifier_elements":0,"tasks":0}
    async with SessionLocal() as session:
        for item in data["models"]:
            model=await session.scalar(select(ExamModel).where(ExamModel.model_key==item["model_key"]))
            if model is None:
                model=ExamModel(model_key=item["model_key"],exam=item["exam"],subject=item["subject"],year=item["year"],status=item["status"],total_tasks=item.get("total_tasks"),max_primary_score=item.get("max_primary_score"),source_url=item["source_url"],change_source_url=item.get("change_source_url"),notes=item.get("notes"),metadata_json=item.get("metadata",{}))
                session.add(model); await session.flush(); counts["models"]+=1
            else:
                model.status=item["status"]; model.total_tasks=item.get("total_tasks"); model.max_primary_score=item.get("max_primary_score"); model.source_url=item["source_url"]; model.change_source_url=item.get("change_source_url"); model.notes=item.get("notes"); model.metadata_json=item.get("metadata",{})
            await session.execute(delete(ExamResource).where(ExamResource.exam_model_id==model.id))
            await session.execute(delete(ExamTask).where(ExamTask.exam_model_id==model.id))
            await session.execute(delete(CodifierElement).where(CodifierElement.exam_model_id==model.id))
            for r in item.get("resources",[]):
                session.add(ExamResource(exam_model_id=model.id,resource_type=r["resource_type"],title=r["title"],url=r["url"],source_year=r.get("source_year"),status=r.get("status","official"),notes=r.get("notes"),metadata_json=r.get("metadata",{}))); counts["resources"]+=1
            for c in item.get("codifier_elements",[]):
                session.add(CodifierElement(exam_model_id=model.id,code=c["code"],section=c.get("section"),normalized_label=c["normalized_label"],source_reference=c["source_reference"],verification_status=c["verification_status"],metadata_json=c.get("metadata",{}))); counts["codifier_elements"]+=1
            for t in item.get("tasks",[]):
                session.add(ExamTask(exam_model_id=model.id,task_key=t["task_key"],task_number=t.get("task_number"),title=t["title"],response_type=t.get("response_type"),max_score=t.get("max_score"),skill_codes=t.get("skill_codes",[]),content_scope=t.get("content_scope",{}),verification_status=t["verification_status"],source_reference=t["source_reference"],notes=t.get("notes"),metadata_json=t.get("metadata",{}))); counts["tasks"]+=1
        await session.commit()
    return counts

async def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--dataset",type=Path,default=DEFAULT_DATASET); args=ap.parse_args()
    print(await import_dataset(args.dataset))
if __name__=="__main__": asyncio.run(main())
