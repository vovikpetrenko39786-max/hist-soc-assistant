from app.services.pedagogy_quality import PedagogyQualityGate


def _check(report, code):
    return next(x for x in report["checks"] if x["code"] == code)


def test_required_sources_empty_manifest_fails():
    gate = PedagogyQualityGate()

    teacher = {
        "artifact_type": "informational",
        "answer": (
            "Без подтвержденных официальных материалов нельзя достоверно "
            "перечислить изменения."
        ),
        "source_references": [],
    }

    report = gate.evaluate(
        "informational",
        teacher,
        None,
        None,
        [],
        require_sources=True,
    )

    assert report["passed"] is False

    check = _check(report, "required_sources")
    assert check["passed"] is False
    assert "source_manifest пуст" in check["message"]


def test_non_strict_informational_can_have_empty_manifest():
    gate = PedagogyQualityGate()

    teacher = {
        "artifact_type": "informational",
        "answer": "Краткий аналитический ответ без заявленных внешних источников.",
        "source_references": [],
    }

    report = gate.evaluate(
        "informational",
        teacher,
        None,
        None,
        [],
        require_sources=False,
    )

    assert "required_sources" not in {
        x["code"] for x in report["checks"]
    }


def test_required_sources_with_manifest_passes_source_requirement():
    gate = PedagogyQualityGate()

    title = "ФИПИ. ЕГЭ-2027. История. Демонстрационный вариант (проект)"

    manifest = [
        {
            "chunk_id": "test-fipi-2027-001",
            "source_id": "test-fipi-2027",
            "source_key": "fipi-ege-history-2027-demo",
            "title": title,
            "source_title": title,
            "page_pdf_start": 1,
            "page_pdf_end": 1,
            "page_print_start": 3,
            "page_print_end": 3,
            "status": "project",
        }
    ]

    teacher = {
        "artifact_type": "informational",
        "answer": (
            "Материал ФИПИ на 2027 год обозначен как проект. "
            "Сведения основаны на указанном документе."
        ),
        "source_references": [
            {
                "chunk_id": "test-fipi-2027-001",
                "source_id": "test-fipi-2027",
                "source_key": "fipi-ege-history-2027-demo",
                "title": title,
                "source_title": title,
                "page_pdf_start": 1,
                "page_pdf_end": 1,
                "page_print_start": 3,
                "page_print_end": 3,
            }
        ],
    }

    report = gate.evaluate(
        "informational",
        teacher,
        None,
        None,
        manifest,
        require_sources=True,
    )

    check = _check(report, "required_sources")
    assert check["passed"] is True
