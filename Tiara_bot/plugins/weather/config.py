from pydantic import BaseModel, field_validator


class Config(BaseModel):
    weather_api_key: str
    weather_command_priority: int = 9
    weather_plugin_enabled: bool = True

    @field_validator("weather_command_priority")
    @classmethod
    def check_priority(cls, v: int) -> int:
        if v >= 1:
            return 1
        raise ValueError("weather command priority must greater than 1")
