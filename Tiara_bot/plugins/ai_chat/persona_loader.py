"""人格 Markdown 加载器。

- frontmatter 解析（`name` / `description`）+ 目录扫描缓存 + 热重载；
- 运行时切换的人格通过 nonebot-plugin-localstore 持久化，重启后仍然生效
  （`AI_CHAT_PERSONA` 作为初始默认值）。
"""

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from nonebot import require

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_file

from .config import config

logger = logging.getLogger("ai_chat.persona")

_SAVED_PERSONA_FILE = "persona.json"


class Persona:
    """人格：名称 + 描述 + 提示词正文。"""

    def __init__(self, name: str, description: str, prompt: str) -> None:
        self.name = name
        self.description = description
        self.prompt = prompt

    def __repr__(self) -> str:
        return f"<Persona {self.name}: {self.description}>"


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


def _parse_md(text: str) -> tuple[dict[str, str], str]:
    """解析 markdown frontmatter，返回 (meta, body)。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text.strip()

    header, body = m.group(1), m.group(2)

    meta: dict[str, str] = {}
    for line in header.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()

    return meta, body.strip()


def _read_persona(path: Path) -> Optional[Persona]:
    """读取单个人格文件。文件不存在 / 非 .md / 正文为空 / IO 错误均返回 None。"""
    if not path.exists() or path.suffix != ".md":
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    meta, body = _parse_md(text)
    name = meta.get("name") or path.stem
    description = meta.get("description") or ""
    if not body:
        return None
    return Persona(name=name, description=description, prompt=body)


def load_persona(name: str) -> Optional[Persona]:
    """按名称加载人格，不存在或名称非法则返回 None。"""
    # 名称来自配置或指令，先挡掉路径分隔符，避免读到人格目录之外的文件
    if not name or Path(name).name != name:
        return None
    return _read_persona(config.persona_path / f"{name}.md")


@lru_cache(maxsize=1)
def _list_persona_names_cached() -> tuple[str, ...]:
    """扫描人格目录，缓存文件名。"""
    p = config.persona_path
    if not p.exists():
        return ()
    return tuple(sorted(f.stem for f in p.glob("*.md")))


def list_personas() -> list[Persona]:
    """列出所有人格（含元数据）。"""
    result: list[Persona] = []
    for name in _list_persona_names_cached():
        persona = load_persona(name)
        if persona:
            result.append(persona)
    return result


def reload_personas() -> int:
    """清空缓存并重新扫描，返回加载成功的人格数量。"""
    _list_persona_names_cached.cache_clear()
    _load_saved_persona.cache_clear()
    return len(list_personas())


# ============================================================
# 当前人格的读取与持久化
# ============================================================

def _persona_state_path() -> Optional[Path]:
    """人格状态文件路径；本地存储不可用时返回 None。"""
    try:
        return get_plugin_data_file(_SAVED_PERSONA_FILE)
    except Exception as e:  # pragma: no cover - 取决于运行环境
        logger.debug("本地存储不可用，人格切换将不会持久化：%s", e)
        return None


@lru_cache(maxsize=1)
def _load_saved_persona() -> Optional[str]:
    """读取已持久化的人格名；文件缺失、损坏或人格已删除时返回 None。"""
    path = _persona_state_path()
    if path is None or not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("读取人格状态失败：%s", e)
        return None

    name = data.get("persona") if isinstance(data, dict) else None
    if isinstance(name, str) and name and persona_exists(name):
        return name
    return None


def _save_persona(name: str) -> None:
    """持久化人格名，失败只告警不影响本次切换。"""
    path = _persona_state_path()
    if path is None:
        return
    try:
        path.write_text(
            json.dumps({"persona": name}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as e:
        logger.warning("保存人格状态失败：%s", e)


def get_default_persona_name() -> str:
    """当前人格名：已持久化的切换结果优先，其次取 AI_CHAT_PERSONA。"""
    return _load_saved_persona() or config.ai_chat_persona


def set_default_persona(name: str) -> bool:
    """切换人格：更新运行时配置并持久化，人格不存在时返回 False。"""
    if not persona_exists(name):
        return False

    config.ai_chat_persona = name
    _save_persona(name)
    _load_saved_persona.cache_clear()
    logger.info("人格已切换为 %s", name)
    return True


def persona_exists(name: str) -> bool:
    return name in _list_persona_names_cached()
