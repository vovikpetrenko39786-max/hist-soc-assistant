import uuid

from app.schemas.pedagogy import PedagogyGenerationRequest
from app.services.generation_context import GroundedContextBuilder
from app.services.pedagogy_provider import TemplatePedagogyProvider
from app.services.pedagogy_quality import PedagogyQualityGate


def card():
    return {
        "subject":{"code":"SOCIAL_STUDIES","name":"Обществознание"}, "grade":10,
        "curriculum":{"level":"basic","title":"Обществознание 10"},
        "unit":{"title":"Человек и общество"},
        "topic":{"title":"Социальные институты","essential_questions":["Почему обществу нужны социальные институты?"],"typical_misconceptions":["Институт = организация"]},
        "outcomes":[{"type":"subject","text":"Объяснять функции социальных институтов.","priority":1}],
        "concepts":[{"term":"социальный институт","importance":"required"}],
        "skills":[{"code":"explain","name":"Объяснять","priority":1}],
        "interdisciplinary_links":[], "exam_links":[],
    }


def retrieval():
    return {"hits":[{
        "chunk_id":uuid.uuid4(),"source_id":uuid.uuid4(),"source_key":"BOOK","source_title":"Учебник","source_status":"primary",
        "section":"§3","page_pdf_start":20,"page_pdf_end":20,"page_print_start":18,"page_print_end":18,"quote_safe":False,"snippet":"Социальные институты выполняют функции."
    }]}


def test_assessment_teacher_student_split_and_quality():
    req = PedagogyGenerationRequest(artifact_type="assessment",subject="SOCIAL_STUDIES",grade=10,topic="Социальные институты",audience="both")
    ctx = GroundedContextBuilder().build(req, card(), retrieval())
    bundle = TemplatePedagogyProvider()._assessment(ctx)
    assert bundle["teacher"]["tasks"][0]["answer"] is not None
    assert bundle["student"]["tasks"][0]["answer"] is None
    assert sum(x["points"] for x in bundle["teacher"]["tasks"]) == bundle["teacher"]["max_points"]
    report = PedagogyQualityGate().evaluate("assessment",bundle["teacher"],bundle["student"],card(),ctx["source_manifest"])
    assert report["passed"] is True


def test_worksheet_student_has_no_answers():
    req = PedagogyGenerationRequest(artifact_type="worksheet",subject="SOCIAL_STUDIES",grade=10,topic="Социальные институты",audience="both")
    ctx = GroundedContextBuilder().build(req, card(), retrieval())
    bundle = TemplatePedagogyProvider()._worksheet(ctx)
    tasks = [x for s in bundle["student"]["sections"] for x in s["tasks"]]
    assert all(x["answer"] is None for x in tasks)


def test_homework_student_has_no_teacher_note():
    req = PedagogyGenerationRequest(artifact_type="homework",subject="SOCIAL_STUDIES",grade=10,topic="Социальные институты",audience="student")
    ctx = GroundedContextBuilder().build(req, card(), retrieval())
    bundle = TemplatePedagogyProvider()._homework(ctx)
    assert bundle["student"]["teacher_note"] is None


def test_idea_enhancer_has_three_options():
    req = PedagogyGenerationRequest(artifact_type="idea_enhancement",request_text="Хочу урок как расследование",subject="HISTORY",grade=7)
    ctx = GroundedContextBuilder().build(req, None, {"hits":[]})
    bundle = TemplatePedagogyProvider()._idea(ctx)
    assert {x["label"] for x in bundle["teacher"]["options"]} == {"minimal","optimal","bold"}
    assert bundle["teacher"]["recommended_option"] == "optimal"
