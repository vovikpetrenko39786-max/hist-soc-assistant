import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    ClassCourse,
    ClassGroup,
    Course,
    CurriculumProgress,
    Homework,
    Lesson,
    LessonStatus,
    Source,
)


class MemoryService:
    async def build_class_course_context(
        self, session: AsyncSession, class_course_id: uuid.UUID
    ) -> dict:
        course_row = await session.execute(
            select(ClassCourse, ClassGroup, Course, Source)
            .join(ClassGroup, ClassCourse.class_id == ClassGroup.id)
            .join(Course, ClassCourse.course_id == Course.id)
            .outerjoin(Source, ClassCourse.primary_source_id == Source.id)
            .where(ClassCourse.id == class_course_id)
        )
        course_record = course_row.one_or_none()
        if course_record is None:
            raise LookupError("Class course not found")
        class_course, class_group, course, source = course_record

        lesson_row = await session.execute(
            select(Lesson)
            .where(
                Lesson.class_course_id == class_course_id,
                Lesson.status.in_(
                    [LessonStatus.completed, LessonStatus.partially_completed]
                ),
            )
            .order_by(desc(Lesson.date), desc(Lesson.lesson_number))
            .limit(1)
        )
        last_lesson = lesson_row.scalar_one_or_none()

        progress_row = await session.execute(
            select(CurriculumProgress)
            .where(CurriculumProgress.class_course_id == class_course_id)
            .order_by(desc(CurriculumProgress.updated_at))
            .limit(1)
        )
        progress = progress_row.scalar_one_or_none()

        homework_row = await session.execute(
            select(Homework)
            .where(
                Homework.class_course_id == class_course_id,
                Homework.status == "assigned",
            )
            .order_by(desc(Homework.assigned_date))
            .limit(1)
        )
        homework = homework_row.scalar_one_or_none()

        return {
            "class_course_id": str(class_course.id),
            "class_label": class_group.name,
            "grade": class_group.grade,
            "subject": course.subject,
            "course_level": course.level,
            "primary_source_key": source.source_key if source else None,
            "primary_source_id": (
                str(class_course.primary_source_id)
                if class_course.primary_source_id
                else None
            ),
            "last_lesson": None
            if not last_lesson
            else {
                "date": last_lesson.date.isoformat(),
                "topic": last_lesson.topic,
                "status": last_lesson.status.value,
                "completed_content": last_lesson.completed_content,
                "unfinished_content": last_lesson.unfinished_content,
                "reflection": last_lesson.reflection,
                "next_step": last_lesson.next_step,
            },
            "progress": None
            if not progress
            else {
                "unit": progress.unit,
                "topic": progress.topic,
                "subtopic": progress.subtopic,
                "status": progress.status.value,
                "notes": progress.notes,
            },
            "homework": None
            if not homework
            else {
                "assigned_date": homework.assigned_date.isoformat(),
                "due_date": homework.due_date.isoformat() if homework.due_date else None,
                "text": homework.text,
                "purpose": homework.purpose,
            },
        }
