from core.domain.exceptions.agent_persistence_error import AgentPersistenceError


class HistoryAccessError(AgentPersistenceError):
    """Ошибка доступа к истории чата."""
