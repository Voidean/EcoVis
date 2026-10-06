import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

from pyglm import glm

from rendering.textures.texture import Texture
from util.paths import TEXTURES
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Gradient:
    display_name: str
    texture: Texture
    color_start: glm.vec4
    color_end: glm.vec4


def load_gradients() -> list[Gradient]:
    result = []
    gradient_path = Path(TEXTURES / "gradients")

    for file in sorted(gradient_path.iterdir()):
        if not file.is_file(): continue
        try:
            texture = Texture.from_file(f"gradients/{file.name}", repeat_s=False, repeat_t=False)

            # Open with PIL to get edge pixels for the UI
            with Image.open(file).convert("RGBA") as img:
                start_px = glm.vec4(img.getpixel((0, 0)))
                end_px = glm.vec4(img.getpixel((img.width - 1, 0)))

            result.append(Gradient(
                display_name=file.stem,
                texture=texture,
                color_start=start_px,
                color_end=end_px
            ))
        except Exception as e:
            logger.error("Failed to load gradient %s", file.name, exc_info=True)

    return result

GRADIENTS: List = load_gradients()


def get_default_gradient() -> Gradient | None:
    for gradient in GRADIENTS:
        if gradient.display_name.lower() == "inferno":
            return gradient

    return GRADIENTS[0] if GRADIENTS else None
