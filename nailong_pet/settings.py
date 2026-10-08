"""桌宠配置的数据模型与输入校验。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


MIN_DISPLAY_WIDTH = 60
MAX_DISPLAY_WIDTH = 720
DEFAULT_DISPLAY_WIDTH = 180
DEFAULT_VOLUME = 70


def _bounded_int(value: object, default: int, minimum: int, maximum: int) -> int:
    if type(value) is not int:
        return default
    return max(minimum, min(maximum, value))


def _boolean(value: object, default: bool) -> bool:
    return value if type(value) is bool else default


@dataclass(frozen=True, slots=True)
class PetSettings:
    """经过校验、可直接供界面使用的桌宠配置。"""

    width: int = DEFAULT_DISPLAY_WIDTH
    position: tuple[int, int] | None = None
    sound: bool = True
    volume: int = DEFAULT_VOLUME
    idle: bool = False
    snap: bool = True

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, object] | None,
        *,
        default_width: int = DEFAULT_DISPLAY_WIDTH,
    ) -> PetSettings:
        """从 JSON 对象创建配置；无效字段独立回退到默认值。"""
        source = value or {}
        safe_default_width = max(
            MIN_DISPLAY_WIDTH,
            min(MAX_DISPLAY_WIDTH, default_width),
        )
        raw_position = source.get("position")
        position = None
        if (
            isinstance(raw_position, (list, tuple))
            and len(raw_position) == 2
            and all(type(coordinate) is int for coordinate in raw_position)
        ):
            position = (raw_position[0], raw_position[1])

        return cls(
            width=_bounded_int(
                source.get("width"),
                safe_default_width,
                MIN_DISPLAY_WIDTH,
                MAX_DISPLAY_WIDTH,
            ),
            position=position,
            sound=_boolean(source.get("sound"), True),
            volume=_bounded_int(source.get("volume"), DEFAULT_VOLUME, 0, 100),
            idle=_boolean(source.get("idle"), False),
            snap=_boolean(source.get("snap"), True),
        )

    def to_mapping(self) -> dict[str, object]:
        """返回可由 JSON 直接序列化的配置对象。"""
        return {
            "width": self.width,
            "position": list(self.position) if self.position is not None else None,
            "sound": self.sound,
            "volume": self.volume,
            "idle": self.idle,
            "snap": self.snap,
        }
