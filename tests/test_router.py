from app.services.router import RequestRouter


def test_full_social_studies_lesson():
    result = RequestRouter().route(
        "Завтра 10 класс. Обществознание. Сделай полноценный урок по социальным институтам."
    )
    assert result.task == "lesson"
    assert result.subject == "social_studies"
    assert result.grade == 10
    assert result.mode == "full"


def test_strict_source():
    result = RequestRouter().route(
        "Найди в учебнике истории 10 класса точную цитату и страницу."
    )
    assert result.task == "source_query"
    assert result.subject == "history"
    assert result.strict_source is True
