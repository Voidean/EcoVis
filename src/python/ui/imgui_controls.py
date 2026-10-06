import math
from abc import ABC
from datetime import datetime
from typing import Iterable, Callable

from imgui_bundle import imgui

class ImGuiControls(ABC):
    def __init__(self, state=None):
        self.state = state

    def checkbox(self, attr_name: str, label: str, state=None):
        if not state: state = self.state
        changed, new_value = imgui.checkbox(label, getattr(state, attr_name, False))
        if changed:
            setattr(state, attr_name, new_value)
            state.changed = True
        return changed

    @staticmethod
    def checkbox_value(label: str, value: bool, set_value: Callable[[bool], None]):
        """Render a checkbox bound to a ViewModel command.

        The older attribute helpers remain useful for small, local edit-state
        objects.  ViewModel-backed controls use these value helpers so the
        rendering layer reports intent instead of mutating application state.
        """
        changed, new_value = imgui.checkbox(label, value)
        if changed:
            set_value(new_value)
        return changed

    def slider_int(self, attr_name: str, label: str, min_value: int, max_value: int, state=None, round_digits: int = 0,
                   format: str = "%d", update_immediately=True):
        if not state: state = self.state
        rounding_factor = 10 ** round_digits

        changed, new_value = imgui.slider_int(
            label,
            int(getattr(state, attr_name) // rounding_factor),
            int(min_value // rounding_factor),
            int(max_value // rounding_factor),
            format=format.replace("%d", "%d" + round_digits * "0")
        )
        if changed:
            setattr(state, attr_name, new_value * rounding_factor)
            if update_immediately:
                state.changed = True
        if imgui.is_item_deactivated_after_edit():
            state.changed = True
        return changed

    def slider_power_2(self, attr_name: str, label: str, min_pow: int, max_pow: int, state=None,
                       format: str = "%d", update_immediately=True):
        if not state: state = self.state
        old_value = getattr(state, attr_name)
        old_pow = round(math.log2(old_value))
        changed, new_pow = imgui.slider_int(
            label,
            old_pow,
            min_pow,
            max_pow,
            format=format.replace("%d", f"{old_value}")
        )
        if changed:
            setattr(state, attr_name, 2 ** new_pow)
            if update_immediately:
                state.changed = True
        if imgui.is_item_deactivated_after_edit():
            state.changed = True
        return changed

    def slider_float(self, attr_name: str, label: str, min_value: float, max_value: float, state=None, format: str = "%.3f", update_immediately=True):
        if not state: state=self.state
        changed, new_value = imgui.slider_float(label, float(getattr(state, attr_name)), float(min_value),
                                                float(max_value),
                                                format=format)
        if changed:
            setattr(state, attr_name, new_value)
            if update_immediately:
                state.changed = True
        if imgui.is_item_deactivated_after_edit():
            state.changed = True
        return changed

    @staticmethod
    def slider_float_value(
            label: str,
            value: float,
            min_value: float,
            max_value: float,
            set_value: Callable[[float], None],
            *,
            format: str = "%.3f",
            on_commit: Callable[[], None] | None = None,
    ) -> bool:
        changed, new_value = imgui.slider_float(
            label,
            float(value),
            float(min_value),
            float(max_value),
            format=format,
        )
        if changed:
            set_value(new_value)
        if on_commit is not None and imgui.is_item_deactivated_after_edit():
            on_commit()
        return changed

    @staticmethod
    def color_edit_value(label: str, value, set_value: Callable):
        changed, new_value = imgui.color_edit4(label, value)
        if changed:
            set_value(type(value)(*new_value))
        return changed

    @staticmethod
    def _combo_item_name(item):
        return getattr(item, "display_name", str(item))

    def _combo_control(
            self,
            label: str,
            options: Iterable,
            current,
            set_value: Callable,
            *,
            iter_buttons=False,
            option_value=lambda item: item,
            option_id=None,
            show_current_when_missing=False,
    ) -> bool:
        """Render the shared combo UI independently of value storage."""
        option_items = tuple(options)
        if not option_items:
            return False

        current_idx = next(
            (
                index
                for index, item in enumerate(option_items)
                if option_value(item) == current
            ),
            None,
        )
        current_item = (
            option_items[current_idx]
            if current_idx is not None
            else None
        )
        preview = (
            self._combo_item_name(current_item)
            if current_item is not None
            else self._combo_item_name(current)
            if show_current_when_missing
            else "Select..."
        )
        changed = False

        if imgui.begin_table("stepper_layout", 2, imgui.TableFlags_.sizing_stretch_prop):
            imgui.table_setup_column("combo", imgui.TableColumnFlags_.width_stretch)
            imgui.table_setup_column("buttons", imgui.TableColumnFlags_.width_fixed)

            imgui.table_next_column()
            imgui.align_text_to_frame_padding()
            imgui.set_next_item_width(-1.0)

            if imgui.begin_combo(label, preview):
                for item in option_items:
                    item_value = option_value(item)
                    is_selected = current == item_value
                    item_label = self._combo_item_name(item)
                    if option_id is not None:
                        item_label = f"{item_label}##{option_id(item)}"

                    if imgui.selectable(item_label, is_selected)[0]:
                        set_value(item_value)
                        changed = True
                    if is_selected:
                        imgui.set_item_default_focus()
                imgui.end_combo()

            if iter_buttons:
                imgui.table_next_column()
                index = current_idx if current_idx is not None else 0

                if imgui.arrow_button(f"##{label}_down", imgui.Dir.down):
                    set_value(option_value(option_items[(index - 1) % len(option_items)]))
                    changed = True

                imgui.same_line(0.0, 2.0)

                if imgui.arrow_button(f"##{label}_up", imgui.Dir.up):
                    set_value(option_value(option_items[(index + 1) % len(option_items)]))
                    changed = True

            imgui.end_table()

        return changed

    def combo(
            self,
            attr_name: str,
            label: str,
            options: Iterable,
            state=None,
            iter_buttons=False,
            on_changed=lambda old, new: None,
            *,
            mark_changed=True,
    ):
        if state is None:
            state = self.state

        current = getattr(state, attr_name)
        if not current:
            return False

        changed = self._combo_control(
            label,
            options,
            current,
            lambda value: setattr(state, attr_name, value),
            iter_buttons=iter_buttons,
            show_current_when_missing=True,
        )
        if changed:
            if mark_changed:
                state.changed = True
            on_changed(current, getattr(state, attr_name))

        return changed

    def datepicker(self, datetime_var: str, state = None, precision: list[str] = ["Year", "Month", "Day"], min_date: datetime = None, max_date: datetime = None, same_line: bool = True) -> bool:
        if not state: state = self.state
        changed = False

        item_width = (imgui.get_content_region_avail().x - 34) / len(precision) - 60

        current_datetime: datetime = getattr(state, datetime_var)

        vals = {
            "Year": current_datetime.year,
            "Month": current_datetime.month,
            "Day": current_datetime.day,
            "Hour": current_datetime.hour,
            "Minute": current_datetime.minute
        }

        modulo = {
            "Year": lambda x: x,
            "Month": lambda x: (x - 1) % 12 + 1,
            "Day": lambda x: (x - 1) % 31 + 1,
            "Hour": lambda x: x % 24,
            "Minute": lambda x: x % 60
        }

        first = True
        for unit in precision:
            if not first and same_line:
                imgui.same_line()
            first = False
            label_x = imgui.get_cursor_pos_x()
            imgui.text(f"{unit}:")
            imgui.same_line()
            imgui.set_cursor_pos_x(label_x + 60)
            if same_line: imgui.set_next_item_width(item_width)
            # Read content from input and clamp it to units modulo
            vals[unit] = modulo[unit](imgui.input_int(f"##{unit}_{datetime_var}", vals[unit])[1])

        try:
            new_datetime = datetime(vals["Year"], vals["Month"], vals["Day"], vals["Hour"], vals["Minute"], tzinfo=current_datetime.tzinfo)
            if new_datetime == current_datetime: return False
            if not min_date is None:
                new_datetime = max(new_datetime, min_date)
            if not max_date is None:
                new_datetime = min(new_datetime, max_date)

            setattr(state, datetime_var, new_datetime)
            changed = True
        except ValueError:
            pass

        return changed

    def destroy(self):
        """Release rendering resources when a concrete renderer owns any."""

    def __str__(self) -> str:
        return self.__class__.__name__
