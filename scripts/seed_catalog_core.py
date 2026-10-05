import asyncio
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.catalog import GradeLevel, Skill, Subject
SUBJECTS=[('HISTORY','История'),('SOCIAL_STUDIES','Обществознание'),('INDIVIDUAL_PROJECT','Индивидуальный проект')]
SKILLS=[('identify','Определять и распознавать','cognitive'),('compare','Сравнивать','cognitive'),('classify','Классифицировать','cognitive'),('explain','Объяснять','cognitive'),('give_example','Приводить конкретный пример','subject'),('argue','Аргументировать позицию','communicative'),('analyze_source','Анализировать источник','subject'),('analyze_map','Анализировать историческую карту','subject'),('establish_causality','Устанавливать причинно-следственные связи','cognitive'),('build_plan','Структурировать материал и составлять план','regulatory'),('interpret_statistics','Интерпретировать статистические данные','cognitive'),('apply_concept','Применять понятие к новой ситуации','subject')]
def level(g): return 'primary_general' if g<=4 else ('basic_general' if g<=9 else 'secondary_general')
async def seed():
    async with SessionLocal() as s:
        for code,name in SUBJECTS:
            if not await s.scalar(select(Subject).where(Subject.code==code)): s.add(Subject(code=code,name=name))
        for g in range(1,12):
            if not await s.scalar(select(GradeLevel).where(GradeLevel.grade==g)): s.add(GradeLevel(grade=g,education_level=level(g),label=f'{g} класс'))
        for code,name,cat in SKILLS:
            if not await s.scalar(select(Skill).where(Skill.code==code)): s.add(Skill(code=code,name=name,category=cat))
        await s.commit()
if __name__=='__main__': asyncio.run(seed())
