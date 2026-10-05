from pathlib import Path
import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.entities import Source

DATASET_PATH = Path(__file__).resolve().parents[2] / 'data' / 'source_catalog_seed_2026_2027.json'

class SourceCatalogService:
    def _dataset(self):
        return json.loads(DATASET_PATH.read_text(encoding='utf-8'))

    async def list_sources(self, session: AsyncSession, subject=None, grade=None, level=None, status=None):
        stmt = select(Source)
        if subject: stmt = stmt.where(Source.subject == subject)
        if grade is not None: stmt = stmt.where(Source.grade == grade)
        if level: stmt = stmt.where(Source.level == level)
        if status: stmt = stmt.where(Source.status == status)
        result = await session.execute(stmt.order_by(Source.authority_rank.desc(), Source.title))
        return result.scalars().all()

    def resolve_preview(self, subject: str, grade: int, level: str='basic', unit_title: str|None=None, topic_title: str|None=None):
        d=self._dataset(); bykey={x['key']:x for x in d['sources']}; out=[]
        for r in d['mapping_rules']:
            if r['subject']!=subject or r['grade']!=grade or r['level']!=level: continue
            ums=r.get('unit_match') or []
            if ums:
                if not unit_title or not any(x.lower() in unit_title.lower() for x in ums): continue
            if r['source_key']=='SOC_11_ADV_SOC_POL_2026':
                blob=((unit_title or '')+' '+(topic_title or '')).lower()
                if not any(x in blob for x in ['социолог','политолог']): continue
            s=bykey[r['source_key']]
            out.append({
                'source_key':s['key'],'title':s['title'],'source_role':r['source_role'],'priority':r['priority'],
                'authority_rank':s.get('authority_rank',50),'verification_status':s.get('verification_status'),
                'rollout_status':s.get('rollout_status'),'availability_status':s.get('availability_status'),
                'rationale':'Совпадение предмета, класса, уровня и области покрытия по проверенному правилу Source Catalog v0.6.'
            })
        return sorted(out,key=lambda x:(x['priority'],-x['authority_rank']))
