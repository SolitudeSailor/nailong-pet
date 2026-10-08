"""视频帧去背、缩放与 Windows 色键转换。"""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image


COLORKEY_RGB = (255, 0, 255)


def resize_transparent_image(
    image: Image.Image,
    size: tuple[int, int],
) -> Image.Image:
    """以预乘 Alpha 缩放图像，再转换为二值化的 Windows 色键图。"""
    pixels = np.asarray(image.convert("RGBA"), dtype=np.float32)
    alpha = pixels[:, :, 3] / 255.0
    premultiplied = pixels[:, :, :3] * alpha[:, :, None]

    resized_alpha = cv2.resize(alpha, size, interpolation=cv2.INTER_AREA)
    resized_premultiplied = cv2.resize(
        premultiplied,
        size,
        interpolation=cv2.INTER_AREA,
    )

    safe_alpha = np.maximum(resized_alpha[:, :, None], 1e-6)
    resized_rgb = np.clip(resized_premultiplied / safe_alpha, 0, 255)
    binary_alpha = np.where(resized_alpha >= 0.5, 255, 0)
    result = np.dstack((resized_rgb, binary_alpha)).astype(np.uint8)
    return to_colorkey_image(Image.fromarray(result))


def to_colorkey_image(image: Image.Image) -> Image.Image:
    """将 Alpha 透明区转换为 `#ff00ff` 色键，并保护不透明洋红像素。"""
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    rgb = rgba[:, :, :3].copy()
    transparent = rgba[:, :, 3] < 128
    colorkey = np.array(COLORKEY_RGB, dtype=np.uint8)
    opaque_colorkey = ~transparent & np.all(rgb == colorkey, axis=2)
    rgb[opaque_colorkey] = (254, 0, 255)
    rgb[transparent] = colorkey
    return Image.fromarray(rgb)


def remove_connected_background(
    bgr: NDArray[np.uint8],
    chroma_tolerance: int,
) -> NDArray[np.uint8]:
    """移除与边缘连通的灰白背景，同时保留角色内部浅色区域。"""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    brightness = hsv[:, :, 2]
    background_candidate = (
        (saturation <= chroma_tolerance) & (brightness >= 35)
    ).astype(np.uint8)

    _, labels = cv2.connectedComponents(background_candidate, connectivity=8)
    border_labels = np.unique(
        np.concatenate((labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]))
    )
    connected_background = np.isin(labels, border_labels) & (
        background_candidate != 0
    )

    lower_region = np.zeros_like(background_candidate, dtype=bool)
    lower_region[round(bgr.shape[0] * 0.67) :, :] = True
    connected_background |= lower_region & (background_candidate != 0)
    light_floor_noise = np.min(bgr, axis=2) >= 100
    connected_background |= lower_region & light_floor_noise

    alpha = np.where(connected_background, 0, 255).astype(np.uint8)
    return np.dstack((bgr, alpha))
