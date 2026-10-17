from core.domain.exceptions.agent_persistence_error import AgentPersistenceError


class MemoryAccessError(AgentPersistenceError):
    """Ошибка доступа к памяти агента (глобальной или задачи диалога)."""
