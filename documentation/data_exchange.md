# NumPy Time-Series Export

EcoVis exports the time series that are already loaded in a Data view. Open a
Data view and expand its NumPy export controls. Select as many of the available
time series as needed, choose a destination, and export them to one `.npz` file.

Each selected series is stored as a numeric NumPy array with shape `(N, 2)`:

- column 0 contains Unix timestamps in seconds;
- column 1 contains the corresponding values.

The arrays can have different lengths. Load and inspect them without pickle
support. Archive keys keep the selection order and a filesystem-safe form of
the displayed series name, for example `series_000_Weather_Temperature`:

```python
import numpy as np

with np.load("data-view-export.npz", allow_pickle=False) as exported:
    for name in exported.files:
        series = exported[name]
        timestamps = series[:, 0]
        values = series[:, 1]
```

The archive contains only numeric arrays and is intended for processing in
external Python scripts or notebooks. EcoVis does not provide a data-import
function for these files.
