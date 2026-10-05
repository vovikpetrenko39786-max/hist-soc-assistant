from app.services.sources import SourceCatalogService

def test_history_source_resolution():
    result=SourceCatalogService().resolve_preview('HISTORY',9,'basic','Всеобщая история. История Нового времени','Европа в XIX веке')
    assert result
    assert result[0]['source_key']=='HIST_WORLD_9_STATE_2026'

def test_social_10_source_resolution():
    result=SourceCatalogService().resolve_preview('SOCIAL_STUDIES',10,'basic','Человек и общество','Общество как система')
    assert result
    assert result[0]['source_key']=='SOC_10_STATE_2026'
