"""Application-wide visual theme selected at startup."""

from util.config import config


LIGHT = "light"
DARK = "dark"

# The theme is intentionally read only once. Changes to config.json therefore
# take effect after the next application restart.
THEME = str(getattr(config, "theme", DARK)).lower()
if THEME not in (LIGHT, DARK):
    THEME = DARK


def is_dark() -> bool:
    return THEME == DARK


def apply_imgui_theme():
    """Apply the selected theme to the current ImGui context."""
    from imgui_bundle import imgui

    if is_dark():
        imgui.style_colors_dark()
    else:
        imgui.style_colors_light()
        style = imgui.get_style()
        style.set_color_(imgui.Col_.button, imgui.ImVec4(0.78, 0.78, 0.78, 1.0))
        style.set_color_(imgui.Col_.button_hovered, imgui.ImVec4(0.70, 0.70, 0.70, 1.0))
        style.set_color_(imgui.Col_.button_active, imgui.ImVec4(0.62, 0.62, 0.62, 1.0))
        style.set_color_(imgui.Col_.frame_bg, imgui.ImVec4(0.86, 0.86, 0.86, 1.0))
        style.set_color_(imgui.Col_.frame_bg_hovered, imgui.ImVec4(0.80, 0.80, 0.80, 1.0))
        style.set_color_(imgui.Col_.frame_bg_active, imgui.ImVec4(0.74, 0.74, 0.74, 1.0))


def apply_implot_theme():
    """Apply the selected theme to the current ImPlot context."""
    from imgui_bundle import imgui, implot

    if is_dark():
        implot.style_colors_dark()
    else:
        implot.style_colors_light()
        style = implot.get_style()
        style.set_color_(implot.Col_.plot_bg, imgui.ImVec4(1.0, 1.0, 1.0, 1.0))
        style.set_color_(implot.Col_.plot_border, imgui.ImVec4(0.35, 0.35, 0.35, 1.0))
        style.set_color_(implot.Col_.axis_grid, imgui.ImVec4(0.55, 0.55, 0.55, 1.0))
        style.set_color_(implot.Col_.axis_tick, imgui.ImVec4(0.20, 0.20, 0.20, 1.0))
        style.set_color_(implot.Col_.axis_text, imgui.ImVec4(0.10, 0.10, 0.10, 1.0))
        style.set_color_(implot.Col_.title_text, imgui.ImVec4(0.05, 0.05, 0.05, 1.0))
        style.set_color_(implot.Col_.legend_bg, imgui.ImVec4(1.0, 1.0, 1.0, 0.94))
        style.set_color_(implot.Col_.legend_border, imgui.ImVec4(0.35, 0.35, 0.35, 1.0))
        style.set_color_(implot.Col_.legend_text, imgui.ImVec4(0.10, 0.10, 0.10, 1.0))


def apply_theme():
    """Apply the selected theme to the main ImGui and ImPlot contexts."""
    apply_imgui_theme()
    apply_implot_theme()
