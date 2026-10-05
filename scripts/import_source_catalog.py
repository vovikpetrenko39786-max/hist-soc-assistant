import asyncio, json
from pathlib import Path
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.entities import Source

DATA=Path(__file__).resolve().parents[1]/'data'/'source_catalog_seed_2026_2027.json'

async def run():
    d=json.loads(DATA.read_text(encoding='utf-8'))
    async with SessionLocal() as session:
        for item in d['sources']:
            row=await session.scalar(select(Source).where(Source.source_key==item['key']))
            if row is None:
                row=Source(source_key=item['key'], title=item['title'], source_type=item['source_type'], status=item['status'])
                session.add(row)
            row.title=item['title']; row.author=item.get('author'); row.subject=item.get('subject'); row.grade=item.get('grade'); row.level=item.get('level')
            row.year=item.get('year'); row.edition=item.get('edition'); row.publisher=item.get('publisher'); row.source_type=item['source_type']; row.status=item['status']
            row.origin=item.get('origin'); row.access_status=item.get('access_status'); row.is_current=item.get('rollout_status') not in {'archived','expired'}
            row.fpu_number=item.get('fpu_number'); row.isbn=item.get('isbn'); row.source_url=item.get('source_url'); row.authority_rank=item.get('authority_rank',50)
            row.verification_status=item.get('verification_status'); row.rollout_status=item.get('rollout_status'); row.availability_status=item.get('availability_status'); row.coverage=item.get('coverage')
            row.metadata_json={'source_catalog_version':'0.6','notes':item.get('notes')}
        await session.commit()
        print(f"Imported {len(d['sources'])} source records")

if __name__=='__main__': asyncio.run(run())
