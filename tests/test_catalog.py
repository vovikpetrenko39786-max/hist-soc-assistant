def test_catalog_model_imports():
    from app.models.catalog import Concept, Curriculum, CurriculumUnit, GradeLevel, LearningOutcome, Skill, Subject, Topic, TopicSource
    assert Subject.__tablename__ == 'subjects'
    assert GradeLevel.__tablename__ == 'grade_levels'
    assert Curriculum.__tablename__ == 'curricula'
    assert CurriculumUnit.__tablename__ == 'curriculum_units'
    assert Topic.__tablename__ == 'topics'
    assert LearningOutcome.__tablename__ == 'learning_outcomes'
    assert Concept.__tablename__ == 'concepts'
    assert Skill.__tablename__ == 'skills'
    assert TopicSource.__tablename__ == 'topic_sources'
