"""晚安睡眠管理的持久化状态文件工具"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import json
import shutil

from .state import SleepRecord

PERSISTENCE_VERSION = 2
GLOBAL_SCOPE_KEY = "global"
STATE_FILENAME = "sleep_state.json"
# 迁移来源目录（按优先级）：曾用过的旧插件 ID 目录、上游版本硬编码目录
LEGACY_PLUGIN_DIR_NAMES = ("local.goodnight-sleep-manager", "goodnight_sleep_manager")
# 未注入数据目录时的回退目录（与上游行为保持一致）
FALLBACK_PLUGIN_DIR_NAME = "goodnight_sleep_manager"
MIGRATION_MARKER_FILENAME = ".legacy_migration_done"

_data_dir: Path | None = None


def set_data_dir(data_dir: Path | str | None) -> None:
    """注入插件数据目录，由插件加载时传入 ctx.paths.data_dir"""

    global _data_dir
    normalized = str(data_dir or "").strip()
    _data_dir = Path(normalized) if normalized else None


def get_legacy_data_dirs() -> list[Path]:
    """返回历史版本可能写过数据的目录，按优先级排列"""

    plugins_root = Path(__file__).resolve().parents[2] / "data" / "plugins"
    return [plugins_root / name for name in LEGACY_PLUGIN_DIR_NAMES]


def get_plugin_data_dir() -> Path:
    """返回插件数据目录；未注入时退回上游旧路径，保证脱离宿主也能工作"""

    if _data_dir is not None:
        return _data_dir
    return get_legacy_data_dirs()[-1]


def get_sleep_state_path() -> Path:
    """返回睡眠状态持久化文件路径"""

    return get_plugin_data_dir() / STATE_FILENAME


def migrate_legacy_data_files() -> list[str]:
    """把历史目录里的数据文件搬到插件数据目录

    只做一次性搬迁：在插件数据目录写下标记文件，避免用户清空新状态后又被旧文件覆盖。
    迁移过程只做复制，不删除旧目录里的任何文件。
    """

    target_dir = get_plugin_data_dir()
    legacy_dirs = get_legacy_data_dirs()
    if target_dir in legacy_dirs:
        return []

    marker_path = target_dir / MIGRATION_MARKER_FILENAME
    if marker_path.exists():
        return []

    migrated: list[str] = []
    for legacy_dir in legacy_dirs:
        if not legacy_dir.is_dir():
            continue
        for source_path in sorted(legacy_dir.rglob("*")):
            if not source_path.is_file():
                continue
            relative_path = source_path.relative_to(legacy_dir)
            target_path = target_dir / relative_path
            if target_path.exists():
                continue
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_path)
            except Exception:
                continue
            migrated.append(f"{legacy_dir.name}/{relative_path.as_posix()}")

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
    except Exception:
        pass
    return migrated


def load_persisted_sleep_records() -> Dict[str, SleepRecord]:
    """读取尚未判定是否过期的睡眠状态"""

    state_path = get_sleep_state_path()
    if not state_path.exists():
        return {}

    raw_data = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, dict):
        raise ValueError("睡眠状态文件根节点必须是对象")

    raw_records = raw_data.get("sleep_records")
    if isinstance(raw_records, dict):
        return _load_records_from_mapping(raw_records)

    legacy_record = _load_legacy_record(raw_data)
    return {legacy_record.scope_key: legacy_record} if legacy_record is not None else {}


def save_persisted_sleep_records(sleep_records: Dict[str, SleepRecord]) -> None:
    """保存当前所有睡眠作用域状态"""

    active_records = {
        scope_key: record
        for scope_key, record in sleep_records.items()
        if record.sleep_until is not None and scope_key.strip()
    }

    state_path = get_sleep_state_path()
    if not active_records:
        clear_persisted_sleep_state()
        return

    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "version": PERSISTENCE_VERSION,
        "sleep_records": {
            scope_key: {
                "scope_key": record.scope_key,
                "scope_label": record.scope_label,
                "group_id": record.group_id,
                "session_id": record.session_id,
                "sleep_started_at": (
                    record.sleep_started_at.isoformat(timespec="seconds")
                    if record.sleep_started_at is not None
                    else None
                ),
                "sleep_until": record.sleep_until.isoformat(timespec="seconds"),
                "sleep_reason": record.sleep_reason,
            }
            for scope_key, record in active_records.items()
            if record.sleep_until is not None
        },
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_persisted_sleep_state() -> None:
    """删除持久化睡眠状态文件"""

    state_path = get_sleep_state_path()
    if state_path.exists():
        state_path.unlink()


def _load_records_from_mapping(raw_records: dict[Any, Any]) -> Dict[str, SleepRecord]:
    """从新版 sleep_records 映射读取睡眠状态"""

    records: Dict[str, SleepRecord] = {}
    for raw_scope_key, raw_record in raw_records.items():
        if not isinstance(raw_record, dict):
            continue

        record = _build_record(
            scope_key=str(raw_record.get("scope_key") or raw_scope_key or "").strip(),
            scope_label=str(raw_record.get("scope_label") or raw_scope_key or "").strip(),
            group_id=str(raw_record.get("group_id") or "").strip(),
            session_id=str(raw_record.get("session_id") or "").strip(),
            sleep_started_at_raw=raw_record.get("sleep_started_at"),
            sleep_until_raw=raw_record.get("sleep_until"),
            sleep_reason_raw=raw_record.get("sleep_reason"),
        )
        if record is not None:
            records[record.scope_key] = record
    return records


def _load_legacy_record(raw_data: dict[str, Any]) -> SleepRecord | None:
    """兼容读取 v1 的单一全局睡眠状态"""

    return _build_record(
        scope_key=GLOBAL_SCOPE_KEY,
        scope_label="全局配置",
        group_id="",
        session_id="",
        sleep_started_at_raw=raw_data.get("sleep_started_at"),
        sleep_until_raw=raw_data.get("sleep_until"),
        sleep_reason_raw=raw_data.get("sleep_reason"),
    )


def _build_record(
    *,
    scope_key: str,
    scope_label: str,
    group_id: str,
    session_id: str,
    sleep_started_at_raw: Any,
    sleep_until_raw: Any,
    sleep_reason_raw: Any,
) -> SleepRecord | None:
    """把持久化字段转换为 SleepRecord"""

    if not scope_key:
        return None
    if not isinstance(sleep_until_raw, str) or not sleep_until_raw.strip():
        return None

    sleep_started_at = None
    if isinstance(sleep_started_at_raw, str) and sleep_started_at_raw.strip():
        sleep_started_at = datetime.fromisoformat(sleep_started_at_raw.strip())
    sleep_until = datetime.fromisoformat(sleep_until_raw.strip())
    sleep_reason = sleep_reason_raw.strip() if isinstance(sleep_reason_raw, str) else ""
    return SleepRecord(
        scope_key=scope_key,
        scope_label=scope_label or scope_key,
        sleep_started_at=sleep_started_at,
        sleep_until=sleep_until,
        sleep_reason=sleep_reason,
        group_id=group_id,
        session_id=session_id,
    )
