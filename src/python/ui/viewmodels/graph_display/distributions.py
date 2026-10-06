"""Statistical distribution fits for graph values."""

import numpy as np
from scipy.stats import beta, weibull_min

from ui.viewmodels.graph_display.base import GraphDisplayViewModel
from ui.viewmodels.plot_view_model import Plots


class DistributionViewModel(GraphDisplayViewModel):
    uses_time_axis = False
    supports_ignore_zeros = True

    @property
    def label_y(self) -> str:
        return "Probability density"

    @property
    def plot_y_label(self) -> str:
        return "Probability density"

    def _transform(self, source_plots: Plots) -> Plots:
        distributions = {}
        for plot_id, (_, raw_values, count) in source_plots.items():
            finite_values = self._finite_values(raw_values, count)
            positive = finite_values[finite_values > 0]
            if len(positive) < 2 or np.ptp(positive) == 0:
                continue
            x_data, density = self._fit(plot_id, positive)
            if not self.ignore_zero_values:
                density *= len(positive) / len(finite_values)
            distributions[plot_id] = (x_data, density, len(x_data))
        return distributions

    def _fit(self, plot_id, positive):
        raise NotImplementedError


class WeibullViewModel(DistributionViewModel):
    display_name = "Weibull"

    def _fit(self, _, positive):
        x_data = np.linspace(positive.max() * 1e-6, positive.max(), 200)
        shape, _, scale = weibull_min.fit(positive, floc=0)
        return x_data, weibull_min.pdf(x_data, shape, scale=scale)


class BetaViewModel(DistributionViewModel):
    display_name = "Beta"

    def _fit(self, plot_id, positive):
        maximum = self.source.distribution_maximum(plot_id, positive)
        normalized = np.clip(positive / maximum, 1e-6, 1 - 1e-6)
        shape_a, shape_b, _, _ = beta.fit(normalized, floc=0, fscale=1)
        normalized_x = np.linspace(1e-6, 1 - 1e-6, 200)
        x_data = normalized_x * maximum
        density = beta.pdf(normalized_x, shape_a, shape_b) / maximum
        return x_data, density


PowerDistributionViewModel = BetaViewModel
