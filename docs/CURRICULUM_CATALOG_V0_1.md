# Curriculum Catalog v0.1

Универсальный слой содержания без персональных данных учителя и учащихся.

## Topic Card
Центральная единица: предмет, класс, программа/версия, раздел, тема, результаты, понятия, навыки, источники и экзаменационные связи.

## API
- `GET /api/v1/catalog/subjects`
- `GET /api/v1/catalog/curricula?subject=HISTORY&grade=6&level=basic`
- `GET /api/v1/catalog/topics/search?q=Египет&subject=HISTORY&grade=5`
- `GET /api/v1/catalog/topics/{topic_id}`

## Статусы проверки
`draft -> reviewed -> verified -> archived`.
AI-generated карточка не становится `verified` автоматически.

## Seed
`scripts/seed_catalog_core.py` создаёт предметы, классы 1–11 и универсальный набор навыков. Темы не придумываются кодом: они должны импортироваться из актуальной ФРП.

## Следующий pipeline
ФРП -> Curriculum -> Units -> Topics -> Outcomes -> Concepts -> Topic Sources -> verification.

Главное требование: новый пользователь без личной карточки должен получать качественный материал по связке `предмет + класс + тема`.
