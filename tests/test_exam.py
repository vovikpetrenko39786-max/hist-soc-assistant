def test_exam_model_imports():
    from app.models.exam import ExamModel, ExamResource, CodifierElement, ExamTask, TopicExamMapping
    assert ExamModel.__tablename__ == "exam_models"
    assert CodifierElement.__tablename__ == "codifier_elements"
    assert ExamTask.__tablename__ == "exam_tasks"
    assert TopicExamMapping.__tablename__ == "topic_exam_mappings"
