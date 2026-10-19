from __future__ import annotations

from core.application.dtos.preset_seed_result_dto import PresetSeedResultDTO
from core.application.presets.task_profile_presets import (
    PRESET_TASK_PROFILES,
    TaskProfilePreset,
)
from core.application.use_cases.create_task_profile import (
    CreateTaskProfileUseCase,
)


class EnsurePresetTaskProfilesUseCase:
    """Создаёт предустановленные профили задачи, если их ещё нет.

    Существующие профили (в т.ч. изменённые пользователем) не перезаписываются.
    """

    def __init__(
        self,
        task_profile_repository,
        create_task_profile: CreateTaskProfileUseCase,
        presets: list[TaskProfilePreset] | None = None,
    ):
        self._repository = task_profile_repository
        self._create_task_profile = create_task_profile
        self._presets = presets if presets is not None else PRESET_TASK_PROFILES

    def execute(self) -> PresetSeedResultDTO:
        existing = {
            profile.name.strip().casefold()
            for profile in self._repository.get_all_profiles()
        }
        result = PresetSeedResultDTO()
        for preset in self._presets:
            if preset.name.strip().casefold() in existing:
                result.skipped += 1
                continue
            self._create_task_profile.execute(
                preset.name,
                preset.description,
                preset.preferences,
                list(preset.invariants),
                list(preset.mcp_servers),
            )
            existing.add(preset.name.strip().casefold())
            result.created += 1
            result.names.append(preset.name)
        return result
