"""AI 聊天插件配置。

字段名与环境变量一一对应（NoneBot 配置大小写不敏感），例如：
    DEEPSEEK_API_KEY / AI_CHAT_MAX_HISTORY / AI_CHAT_PERSONA ...

新增开关：
    AI_CHAT_ENABLED / AI_CHAT_PRIORITY / AI_CHAT_PROACTIVE_ENABLED / AI_CHAT_ASSISTANT_NAME
"""

from pathlib import Path

from nonebot import get_plugin_config
from pydantic import BaseModel, Field, field_validator, model_validator


class AIChatConfig(BaseModel):
    # ---------- 插件开关与匹配优先级 ----------
    # 关闭后所有 Matcher 都不再响应
    ai_chat_enabled: bool = True
    # on_message / 「/聊」的匹配优先级，数字越小越先匹配
    ai_chat_priority: int = 99
    # 关闭后机器人只在被 @ 或收到「/聊」时回复，不再主动插话
    ai_chat_proactive_enabled: bool = True
    # 机器人在对话历史中的署名
    ai_chat_assistant_name: str = "Tiara"

    # ---------- DeepSeek 模型参数 ----------
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_temperature: float = Field(default=0.8, ge=0.0, le=2.0)
    deepseek_max_tokens: int = Field(default=2000, ge=1)
    deepseek_timeout: int = Field(default=20, ge=1)

    # ---------- 对话历史 ----------
    ai_chat_max_history: int = Field(default=10, ge=1)
    ai_chat_persona: str = "default"
    ai_chat_persona_dir: str = "Tiara_bot/plugins/ai_chat/personas"

    # ---------- 主动回复（秘书决策） ----------
    proactive_base_prob: float = Field(default=0.15, ge=0.0, le=1.0)
    secretary_reply_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    secretary_max_tokens: int = Field(default=200, ge=1)

    # ---------- 能量系统 ----------
    energy_max: float = Field(default=1.0, gt=0.0)
    energy_recovery_per_minute: float = Field(default=0.02, ge=0.0)
    energy_cost_short: float = Field(default=0.1, ge=0.0)
    energy_cost_long: float = Field(default=0.3, ge=0.0)
    energy_threshold_reply: float = Field(default=0.3, ge=0.0)
    energy_threshold_smile: float = Field(default=0.1, ge=0.0)
    proactive_cooldown_seconds: int = Field(default=60, ge=0)

    # ---------- 天使之笑 ----------
    angel_smile_max_tokens: int = Field(default=50, ge=1)
    angel_smile_prompt: str = (
        "你正在群聊中。你只需要回复一句非常简短的话（不超过15个字），"
        "可以是简短的评价、附和、或表情符号，不要展开话题。"
    )

    @field_validator("ai_chat_priority")
    @classmethod
    def check_priority(cls, v: int) -> int:
        if v >= 1:
            return v
        raise ValueError("ai_chat command priority must greater than 1")

    @model_validator(mode="after")
    def check_thresholds(self) -> "AIChatConfig":
        """保证「天使之笑」阈值不高于正常回复阈值，否则低能量分支永远不可达。"""
        if self.energy_threshold_smile > self.energy_threshold_reply:
            raise ValueError(
                "energy_threshold_smile must not greater than energy_threshold_reply"
            )
        return self

    @property
    def persona_path(self) -> Path:
        """人格目录路径。配置目录不存在时回退到插件自带目录。"""
        path = Path(self.ai_chat_persona_dir)
        if not path.is_absolute() and not path.exists():
            return Path(__file__).parent / "personas"
        return path


# 与其它插件保持一致的类名（`from .config import Config`）
Config = AIChatConfig

# 模块级单例，供其他模块 `from .config import config` 使用
config = get_plugin_config(AIChatConfig)
