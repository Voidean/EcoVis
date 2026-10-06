from typing import override

from PIL import Image
from imgui_bundle import imgui

from rendering.textures.texture import load_image_data, Texture
from ui.components.base_component import Component, ViewModelComponent
from ui.viewmodels.windrose_view_model import WindroseViewModel


class ImageComponent(Component):
    """Own and render a reusable GPU texture for dynamically supplied images."""

    def __init__(self, fit_to_available_space: bool = True):
        super().__init__()
        self._texture: Texture | None = None
        self.fit_to_available_space = fit_to_available_space

    @property
    def has_image(self) -> bool:
        return self._texture is not None

    def set_image(self, image: Image.Image):
        img_data = load_image_data(image.transpose(Image.FLIP_TOP_BOTTOM))

        if self._texture is None:
            self._texture = Texture(img_data, mipmaps=False)
        else:
            self._texture.update_data(img_data)

    def clear_image(self):
        if self._texture is not None:
            self._texture.delete()
            self._texture = None

    @override
    def render(self):
        if self._texture is None:
            return

        width = float(self._texture.width)
        height = float(self._texture.height)
        if self.fit_to_available_space:
            available = imgui.get_content_region_avail()
            scales = [1.0]
            if available.x > 0:
                scales.append(available.x / width)
            if available.y > 0:
                scales.append(available.y / height)
            scale = min(scales)
            width *= scale
            height *= scale

        imgui.image(
            imgui.ImTextureRef(self._texture.get_id()),
            (width, height),
        )

    @override
    def destroy(self):
        self.clear_image()
        super().destroy()


class WindroseImageComponent(ViewModelComponent[WindroseViewModel]):
    def __init__(self, view_model: WindroseViewModel):
        ViewModelComponent.__init__(self, view_model)
        self._image = ImageComponent()

    @override
    def render(self):
        image = self.view_model.take_pending_image()
        if image is not None:
            self._image.set_image(image)

        if self.view_model.error is not None:
            self._image.clear_image()
            imgui.text_disabled(self.view_model.error)
            return
        elif self.view_model.loading and not self._image.has_image:
            imgui.text_disabled("Loading windrose...")

        self._image.render()

    @override
    def destroy(self):
        self._image.destroy()
        ViewModelComponent.destroy(self)
