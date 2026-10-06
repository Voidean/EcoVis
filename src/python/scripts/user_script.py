from abc import ABC, abstractmethod
from typing import TypeAlias, override

import numpy as np


PlotData: TypeAlias = tuple[np.ndarray, np.ndarray, int]
"""One plot series as ``(x_values, y_values, point_count)``."""

GraphResult: TypeAlias = dict[str, PlotData]
"""Graph result mapped from its visible series label to its data."""

ExecVar: TypeAlias = PlotData | float | int
"""A value supplied to :meth:`UserScript.execute` by the application."""

class UserScript(ABC):
    """Base class for data-processing scripts.

    Declare every argument of :meth:`execute` in ``exec_vars``.  The key must
    match the argument name and its value determines the input control:

    * ``PlotData`` displays a selector for an existing plot series.
    * ``float`` displays a numeric field with a default of ``0.0``.
    * ``int`` displays a numeric field with a default of ``0``.

    ``execute`` must return a :class:`GraphResult`.  Each dictionary key is
    used as the label of a resulting plot series.

    Set ``description`` to explain the script's purpose to users.  It is
    shown above the script's input controls.
    """

    exec_vars: dict[str, type] = {}
    description: str = ""

    @abstractmethod
    def execute(self, **_: ExecVar) -> GraphResult:
        """Transform the selected inputs into labelled plot series."""
        raise NotImplementedError

    @property
    def display_name(self):
        return ""

class TestUserScript(UserScript):
    description = (
        "Calculates the point-by-point difference between a measurement and "
        "a prognosis series."
    )

    exec_vars = {
        "measurements": PlotData,
        "prognosis": PlotData,
    }

    @override
    def execute(
            self,
            measurements: PlotData,
            prognosis: PlotData,
    ) -> GraphResult:
        x1, y1, _ = measurements
        x2, y2, _ = prognosis

        x_common, idx1, idx2 = np.intersect1d(
            x1,
            x2,
            return_indices=True,
        )

        y_diff = y1[idx1] - y2[idx2]

        return {
            "Power [kW]": (
                x_common,
                y_diff,
                len(x_common),
            )
        }

    @override
    @property
    def display_name(self):
        return "Measurement-Prognosis difference"


class YieldLossAdjustmentUserScript(UserScript):
    """Estimate the effect of weather- or plant-related production losses.

    ``loss_percent`` can represent, for example, soiling, snow cover,
    curtailment, or availability losses.  A value of ``0.0`` leaves the input
    series unchanged; ``10.0`` reduces every power value by ten percent.
    """

    exec_vars = {
        "power": PlotData,
        "loss_percent": float,
    }
    description = (
        "Estimates the effect of weather- or plant-related production losses, "
        "such as soiling, snow cover, curtailment, or limited availability."
    )

    @override
    def execute(
            self,
            power: PlotData,
            loss_percent: float,
    ) -> GraphResult:
        if not 0 <= loss_percent <= 100:
            raise ValueError("loss_percent must be between 0 and 100")

        x_values, y_values, point_count = power
        adjusted_power = y_values * (1 - loss_percent / 100)
        return {
            f"Power after {loss_percent:g}% losses [kW]": (
                x_values,
                adjusted_power,
                point_count,
            ),
        }

    @override
    @property
    def display_name(self):
        return "Yield loss adjustment"


class RollingRMSEUserScript(UserScript):
    description = (
        "Calculates the rolling Root Mean Squared Error (RMSE) over a moving window "
        "between a measurement and a prognosis series."
    )

    exec_vars = {
        "measurements": PlotData,
        "prognosis": PlotData,
        "window_size": int,
    }

    @override
    def execute(
            self,
            measurements: PlotData,
            prognosis: PlotData,
            window_size: int = 24,
    ) -> GraphResult:
        if window_size < 1:
            raise ValueError("window_size must be at least 1")

        x1, y1, _ = measurements
        x2, y2, _ = prognosis

        x_common, idx1, idx2 = np.intersect1d(
            x1,
            x2,
            return_indices=True,
        )

        if len(x_common) == 0:
            return {"Rolling RMSE": (np.array([]), np.array([]), 0)}

        squared_errors = (y1[idx1] - y2[idx2]) ** 2

        cumsum = np.cumsum(np.insert(squared_errors, 0, 0.0))


        window_counts = np.minimum(np.arange(1, len(squared_errors) + 1), window_size)
        window_starts = np.maximum(0, np.arange(1, len(squared_errors) + 1) - window_size)

        rolling_mse = (cumsum[1:] - cumsum[window_starts]) / window_counts
        rolling_rmse = np.sqrt(rolling_mse)

        return {
            f"Rolling RMSE (N={window_size})": (
                x_common,
                rolling_rmse,
                len(x_common),
            )
        }

    @override
    @property
    def display_name(self):
        return "Rolling RMSE"

USER_SCRIPTS = [TestUserScript(), YieldLossAdjustmentUserScript(), RollingRMSEUserScript()]
