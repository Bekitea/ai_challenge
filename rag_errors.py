"""Типизированные ошибки прикладного слоя RAG.

Инфраструктурные ошибки (сеть, sqlite-vec, файлы) оборачиваются в эти
исключения, чтобы пользовательские сообщения не раскрывали детали реализации.
"""

from __future__ import annotations


class RagError(Exception):
    """Базовое исключение RAG-подсистемы."""


class KnowledgeBaseNotFoundError(RagError):
    """База знаний не найдена."""


class KnowledgeBaseAlreadyExistsError(RagError):
    """База знаний с таким названием уже существует."""


class AgentNotFoundError(RagError):
    """Агент не найден."""


class DocumentNotFoundError(RagError):
    """Документ не найден."""


class DocumentIndexingError(RagError):
    """Ошибка индексации документа."""


class VectorStoreError(RagError):
    """Ошибка работы с векторным хранилищем sqlite-vec."""


class EmbeddingProviderError(RagError):
    """Ошибка провайдера эмбеддингов."""


class RerankerProviderError(RagError):
    """Ошибка провайдера реранкера."""


class EmbeddingDimensionMismatchError(RagError):
    """Размерность эмбеддинга не совпадает с размерностью базы знаний."""


class KnowledgeBaseNotAttachedError(RagError):
    """База знаний не подключена к агенту."""


class FileExtractionError(RagError):
    """Ошибка чтения/извлечения текста из файла."""


class UnsupportedFileTypeError(FileExtractionError):
    """Расширение файла не поддерживается."""
