from imgui_bundle import imgui

from util.config import config
from util.paths import FONT_PATH


BASE_FONT_SIZE = 16


def apply_imgui_scaling(scale):
    ui_scale = scale if config.window.enable_ui_scaling else 1.0

    imgui.get_io().fonts.clear()
    imgui.get_io().fonts.add_font_from_file_ttf(
        FONT_PATH,
        round(BASE_FONT_SIZE * ui_scale),
    )

    if config.window.enable_ui_scaling:
        style = imgui.get_style()
        style.scale_all_sizes(scale)
