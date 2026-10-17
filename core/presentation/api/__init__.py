"""REST API слой (FastAPI): единый веб-интерфейс поверх use cases.

Это третий (после ``core.presentation.cli`` и ``core.presentation.celery``)
слой представления. Импортирует
только ``use_cases`` (DTO) и stdlib; бизнес-объект ``Agent`` здесь не виден.
"""
