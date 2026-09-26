"""晚安睡眠管理插件入口"""

from typing import Any

from maibot_sdk import MaiBotPlugin

from .command_handlers import SleepCommandHandlersMixin
from .config_models import GoodnightSleepManagerConfig
from .confirmation_judge import ensure_sleep_confirmation_prompt_files
from .core_mixin import SleepCoreMixin
from .hook_handlers import SleepHookHandlersMixin
from .schema_i18n import apply_config_schema_i18n
from .state_storage import migrate_legacy_data_files, set_data_dir


def _setup_plugin_data_dir(ctx: Any) -> None:
    """把 SDK 提供的数据目录注入持久化模块，并迁移旧目录里的数据"""

    paths = getattr(ctx, "paths", None)
    set_data_dir(getattr(paths, "data_dir", "") if paths is not None else "")

    try:
        migrated = migrate_legacy_data_files()
    except Exception as exc:
        ctx.logger.warning(f"迁移旧数据目录失败: {exc}")
        return
    if migrated:
        ctx.logger.info(f"已从旧数据目录迁移睡眠状态数据: {migrated}")


class GoodnightSleepManagerPlugin(
    SleepHookHandlersMixin,
    SleepCommandHandlersMixin,
    SleepCoreMixin,
    MaiBotPlugin,
):
    """根据 Bot 自己发出的晚安短句进入睡眠状态"""

    config_model = GoodnightSleepManagerConfig

    def __init__(self) -> None:
        """初始化插件状态"""

        super().__init__()
        self._init_sleep_state()

    async def on_load(self) -> None:
        """插件加载时输出当前状态"""

        _setup_plugin_data_dir(self.ctx)
        ensure_sleep_confirmation_prompt_files(self.ctx.logger)
        self._restore_sleep_state()
        self._start_natural_wake_task()
        self._start_idle_sleep_task()
        self.ctx.logger.info("晚安睡眠管理已加载")

    async def on_unload(self) -> None:
        """插件卸载时保留未过期睡眠状态，便于重启恢复"""

        await self._stop_natural_wake_task()
        await self._stop_idle_sleep_task()
        await self._handle_plugin_unload()

    async def on_config_update(self, scope: str, config_data: dict[str, object], version: str) -> None:
        """配置热更新回调"""

        del scope
        del config_data
        del version
        if self.config.control.persist_sleep_state:
            self._save_sleep_state()
        else:
            self._clear_sleep_state_storage()
        await self._restart_natural_wake_task()
        await self._restart_idle_sleep_task()
        self.ctx.logger.info("晚安睡眠管理配置已更新")

    @classmethod
    def build_config_schema(
        cls,
        *,
        plugin_id: str = "",
        plugin_name: str = "",
        plugin_version: str = "",
        plugin_description: str = "",
        plugin_author: str = "",
    ) -> dict[str, object]:
        """构造带本地化标签的 WebUI 配置 Schema"""

        schema = super().build_config_schema(
            plugin_id=plugin_id,
            plugin_name=plugin_name,
            plugin_version=plugin_version,
            plugin_description=plugin_description,
            plugin_author=plugin_author,
        )
        return apply_config_schema_i18n(schema)


def create_plugin() -> GoodnightSleepManagerPlugin:
    """创建插件实例"""

    return GoodnightSleepManagerPlugin()
