from pydantic import BaseModel, field_validator


class ScopedConfig(BaseModel):
    command_priority: int = 9
    plugin_enabled: bool = True

    @field_validator("command_priority")
    @classmethod
    def check_priority(cls, v: int) -> int:
        if v >= 1:
            return v
        raise ValueError("sign command priority must greater than 1")


class Config(BaseModel):
    sign: ScopedConfig = ScopedConfig()
