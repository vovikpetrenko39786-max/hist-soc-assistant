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


def test_class_label_parsing_regression():
    router = RequestRouter()

    no_letter = router.route("Подготовь урок для 10 класса по истории")
    assert no_letter.grade == 10
    assert no_letter.class_label is None

    compact = router.route("Подготовь урок для 10А класса по истории")
    assert compact.grade == 10
    assert compact.class_label == "10-А"

    spaced = router.route("Подготовь урок для 10 А класса по истории")
    assert spaced.grade == 10
    assert spaced.class_label == "10-А"

    hyphenated = router.route("Подготовь урок для 10-А класса по истории")
    assert hyphenated.grade == 10
    assert hyphenated.class_label == "10-А"
