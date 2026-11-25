"""Synthetic network with a known channel-specific failure.

Used by the tests and the tutorial. It reproduces the structure of the case of
the article without any GNSS data:

  - every unit has a site effect common to both channels, so the error varies
    between units for reasons unrelated to the instrument;
  - the units of one instrument model (`LEGACY`) multiply the error of the
    suspect channel only, by `factor`;
  - one receiver model accompanies the legacy units and also several modern
    ones, so the receiver is related to the failure but does not cause it;
  - one legacy unit replaces its instrument and receiver half way through the
    period, as CACE did.

With `degraded=False` the same network is generated without the failure: it
plays the role of the second processing run, in which the processing choice
that exposed the failure has been changed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

REFERENCE, SUSPECT = "ref", "sus"
LEGACY = "LEGACY"


def make_network(n_days: int = 200, factor: float = 8.0, degraded: bool = True,
                 seed: int = 1) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (residuals, metadata) in the long formats of `metaudit.core`.

    residuals  columns unit, date, channel, error
    metadata   columns unit, attribute, value, valid_from, valid_to
    """
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2024-01-01")
    dates = pd.date_range(start, periods=n_days, freq="D")
    change = dates[n_days // 2]

    # (unit, instrument, receiver); U03 replaces its instrument on `change`.
    units = (
        [(f"U{i:02d}", LEGACY, "R1") for i in range(1, 4)]
        + [(f"U{i:02d}", "M1", "R1") for i in range(4, 12)]
        + [(f"U{i:02d}", "M2", "R2") for i in range(12, 20)]
        + [(f"U{i:02d}", "M3", "R2") for i in range(20, 26)]
        + [(f"U{i:02d}", "M3", "R3") for i in range(26, 31)]
    )

    meta_rows, res_rows = [], []
    for unit, instrument, receiver in units:
        site = rng.lognormal(mean=np.log(0.4), sigma=0.25)
        replaced = unit == "U03"
        periods = [(start, change if replaced else None, instrument, receiver)]
        if replaced:
            periods.append((change, None, "M1", "R2"))
        for frm, to, inst, rec in periods:
            for attr, val in (("instrument", inst), ("receiver", rec)):
                meta_rows.append({"unit": unit, "attribute": attr, "value": val,
                                  "valid_from": frm, "valid_to": to})
        for d in dates:
            inst = instrument if not (replaced and d >= change) else "M1"
            for ch in (REFERENCE, SUSPECT):
                err = site * rng.lognormal(0.0, 0.3)
                if degraded and ch == SUSPECT and inst == LEGACY:
                    err *= factor
                res_rows.append({"unit": unit, "date": d, "channel": ch, "error": err})

    return pd.DataFrame(res_rows), pd.DataFrame(meta_rows)
