"""Metadata-grouped residual audit.

The procedure of Section 4.2 of the article, independent of GNSS. It looks for
a failure that affects one measurement channel of some instruments and is
invisible to any grouping derived from the data themselves. Four steps:

1. `assign_metadata`: attach to every residual the instrument attributes in
   force on its date (antenna model, receiver, firmware, calibration date...).
2. `unit_ratios` and `invariance`: per instrument and period, the ratio
   between the suspect channel and a reference channel measured by the same
   instrument, and how much each channel varies between instruments. A cause
   acting on the site or on the whole instrument would affect both channels;
   a ratio that varies while the reference does not points to the channel.
3. `attribute_effects`, `group_intervals` and `contrast`: which attribute
   explains the between-instrument variance of the log ratio, by permutation
   of the labels, with bootstrap intervals per group and a pre-specified
   two-group contrast.
4. `compare_runs`: the same instruments processed twice, changing a single
   processing choice, compared unit by unit.

Terminology:
    unit       the replicated instrument (a station, a sensor)
    channel    one of several measurements of the same unit (a constellation,
               a frequency, a component)
    period     a stretch of time with constant attributes; a unit that
               replaced its equipment contributes one row per period

Inputs are pandas DataFrames in long format; see `assign_metadata`.
"""
from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np
import pandas as pd

SEED = 20260921
N_RESAMPLES = 10_000


# ---------------------------------------------------------------------------
# Step 1: attributes in force on each date
# ---------------------------------------------------------------------------

def assign_metadata(residuals: pd.DataFrame, metadata: pd.DataFrame,
                    attributes: Sequence[str] | None = None,
                    unit: str = "unit", date: str = "date") -> pd.DataFrame:
    """Adds one column per attribute with the value in force on each date.

    residuals  one row per measurement, with columns `unit` and `date`.
    metadata   long format, one row per (unit, attribute, value, valid_from,
               valid_to); `valid_to` empty means still in force. Each
               attribute may change on its own dates, as antenna and receiver
               do in a GNSS site log.

    Intervals are half-open on whole days, [valid_from, valid_to), so the day
    of a change falls in the new record. Dates without a record get NaN.
    """
    out = residuals.copy()
    out[date] = pd.to_datetime(out[date]).dt.normalize()
    meta = metadata.copy()
    meta["valid_from"] = pd.to_datetime(meta["valid_from"], utc=True).dt.tz_localize(None).dt.normalize()
    meta["valid_to"] = pd.to_datetime(meta["valid_to"], utc=True).dt.tz_localize(None).dt.normalize()
    if attributes is None:
        attributes = list(dict.fromkeys(meta["attribute"]))

    for attr in attributes:
        rec = meta[meta["attribute"] == attr]
        values = pd.Series(np.nan, index=out.index, dtype=object)
        for u, recs in rec.groupby("unit"):
            rows = out.index[out[unit] == u]
            if len(rows) == 0:
                continue
            d = out.loc[rows, date]
            for _, r in recs.sort_values("valid_from").iterrows():
                until = r["valid_to"] if pd.notna(r["valid_to"]) else pd.Timestamp.max
                in_force = (d >= r["valid_from"]) & (d < until)
                values.loc[rows[in_force.to_numpy()]] = r["value"]
        out[attr] = values
    return out


# ---------------------------------------------------------------------------
# Step 2: ratio between channels, per unit and period, and invariance
# ---------------------------------------------------------------------------

def unit_ratios(data: pd.DataFrame, channel: str, reference: str,
                period_attributes: Sequence[str] = (), unit: str = "unit",
                channel_col: str = "channel", value: str = "error") -> pd.DataFrame:
    """Median of each channel and their ratio, per unit and period.

    The period is the combination of `period_attributes` in force, so a unit
    that replaced its equipment contributes one row per configuration and
    is never averaged over two instruments. Only rows with both channels are
    kept. The median, not the mean, because the tail of the error is
    precisely what must not drive the comparison.
    """
    keys = [unit, *period_attributes]
    med = (data[data[channel_col].isin([channel, reference])]
           .groupby(keys + [channel_col], observed=True)[value].median()
           .unstack(channel_col))
    med.columns = med.columns.astype(str)
    med = med[[reference, channel]].dropna()
    med["ratio"] = med[channel] / med[reference]
    return med.reset_index()


def invariance(ratios: pd.DataFrame, channel: str, reference: str) -> float:
    """Between-unit dispersion of the log error, suspect over reference channel.

    Large values mean that the suspect channel varies between units much more
    than the reference measured by the same units: the cause is not common to
    both.
    """
    return float(np.log(ratios[channel]).std() / np.log(ratios[reference]).std())


# ---------------------------------------------------------------------------
# Step 3: which attribute explains the ratio
# ---------------------------------------------------------------------------

def _eta2_and_range(values: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    s = pd.Series(values)
    medians = s.groupby(labels).median()
    grand = values.mean()
    means = s.groupby(labels).mean()
    sizes = s.groupby(labels).size()
    between = float((sizes * (means - grand) ** 2).sum())
    total = float(((values - grand) ** 2).sum())
    return (between / total if total else np.nan), float(medians.max() - medians.min())


def permutation_test(ratios: pd.DataFrame, attribute: str, n: int = N_RESAMPLES,
                     seed: int = SEED, ratio: str = "ratio"):
    """Permutation test of one attribute on the log ratio.

    Two statistics: `eta2`, the between-group fraction of variance, which
    weights by group size so that a single-unit group cannot dominate it, and
    the range of group medians, which describes the effect but has little
    power with many small groups. The null reassigns the labels across units
    preserving group sizes. Correlations of the ratio with its components are
    deliberately not offered: they are spurious by construction (Pearson, 1897).

    Returns ((eta2, range), (p_eta2, p_range), null distribution).
    """
    rng = np.random.default_rng(seed)
    sub = ratios.dropna(subset=[attribute])
    values = np.log(sub[ratio].to_numpy())
    labels = sub[attribute].to_numpy()
    obs = _eta2_and_range(values, labels)
    null = np.empty((n, 2))
    for i in range(n):
        null[i] = _eta2_and_range(values, rng.permutation(labels))
    p = [(1 + np.sum(null[:, j] >= obs[j])) / (n + 1) for j in range(2)]
    return obs, p, null


def attribute_effects(ratios: pd.DataFrame, attributes: Iterable[str],
                      n: int = N_RESAMPLES, seed: int = SEED) -> pd.DataFrame:
    """Ranks the attributes by the share of variance of the log ratio they explain.

    Each attribute is tested separately with the same seed. An attribute that
    explains much and another that explains little, when both are recorded for
    the same units, is the separation the procedure looks for; two attributes
    that always vary together cannot be separated, and `confusion` shows it.
    """
    rows = []
    for attr in attributes:
        (eta2, rng_), (p_eta2, p_rng), _ = permutation_test(ratios, attr, n=n, seed=seed)
        rows.append({"attribute": attr, "groups": ratios[attr].nunique(),
                     "eta2": eta2, "p_eta2": p_eta2, "range": rng_, "p_range": p_rng})
    return pd.DataFrame(rows).sort_values("eta2", ascending=False).reset_index(drop=True)


def confusion(ratios: pd.DataFrame, a: str, b: str, unit: str = "unit") -> pd.DataFrame:
    """Cross-tabulation of two attributes over units: can they be separated?"""
    per_unit = ratios.groupby(unit)[[a, b]].agg(lambda s: s.mode().iat[0])
    return pd.crosstab(per_unit[a], per_unit[b])


def group_intervals(ratios: pd.DataFrame, attribute: str, channel: str, reference: str,
                    n: int = N_RESAMPLES, seed: int = SEED) -> pd.DataFrame:
    """Ratio of each group with a 95 % interval resampling its units.

    The point value is the ratio of the group medians. Units are resampled
    because the unit, not the day, is the replicated observation. Groups with
    a single unit admit no interval and are returned with NaN bounds, so that
    they are not read as established.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for group, sub in ratios.groupby(attribute, observed=True):
        ref, ch = sub[reference].to_numpy(), sub[channel].to_numpy()
        k = len(sub)
        point = np.median(ch) / np.median(ref)
        if k < 2:
            rows.append({attribute: group, "n": k, "ratio": point, "low": np.nan, "high": np.nan})
            continue
        idx = rng.integers(0, k, size=(n, k))
        reps = np.median(ch[idx], axis=1) / np.median(ref[idx], axis=1)
        lo, hi = np.percentile(reps, [2.5, 97.5])
        rows.append({attribute: group, "n": k, "ratio": point, "low": lo, "high": hi})
    return pd.DataFrame(rows).sort_values("ratio", ascending=False).reset_index(drop=True)


def contrast(ratios: pd.DataFrame, attribute: str, group: Iterable, n: int = N_RESAMPLES,
             seed: int = SEED, ratio: str = "ratio") -> dict:
    """Pre-specified two-group contrast: units whose attribute is in `group` against the rest.

    One degree of freedom instead of one per group, so it has power where the
    omnibus test has little. `group` must be fixed before looking at the
    residuals (in the article, the antenna models designed for GPS L1/L2 only).
    Statistic: difference of the medians of the log ratio; two-sided p.
    """
    rng = np.random.default_rng(seed)
    sub = ratios.dropna(subset=[attribute])
    mask = sub[attribute].isin(set(group)).to_numpy()
    values = np.log(sub[ratio].to_numpy())

    def stat(m):
        return float(np.median(values[m]) - np.median(values[~m]))

    obs = stat(mask)
    null = np.array([stat(rng.permutation(mask)) for _ in range(n)])
    p = (1 + np.sum(np.abs(null) >= abs(obs))) / (n + 1)
    return {"log_difference": obs, "ratio_of_medians": float(np.exp(obs)), "p": p,
            "n_group": int(mask.sum()), "n_rest": int((~mask).sum())}


# ---------------------------------------------------------------------------
# Step 4: one processing choice changed, unit by unit
# ---------------------------------------------------------------------------

def compare_runs(before: pd.DataFrame, after: pd.DataFrame, channel: str, reference: str,
                 keys: Sequence[str] = ("unit",)) -> pd.DataFrame:
    """Joins the unit ratios of two processing runs of the same data.

    `before` and `after` are outputs of `unit_ratios`. The reference channel
    should be unaffected by the change; its own shift, returned as
    `reference_shift`, bounds the part of the change that does not come from
    the processing choice under test.
    """
    keys = list(keys)
    a = before.set_index(keys)[[reference, channel, "ratio"]]
    b = after.set_index(keys)[[reference, channel, "ratio"]]
    out = a.join(b, lsuffix="_before", rsuffix="_after", how="inner")
    out["ratio_change"] = out["ratio_after"] / out["ratio_before"]
    out["reference_shift"] = out[f"{reference}_after"] - out[f"{reference}_before"]
    return out.reset_index().sort_values("ratio_before", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# All steps at once
# ---------------------------------------------------------------------------

def audit(residuals: pd.DataFrame, metadata: pd.DataFrame, channel: str, reference: str,
          attributes: Sequence[str], period_attributes: Sequence[str] | None = None,
          n: int = N_RESAMPLES, seed: int = SEED) -> dict:
    """Runs steps 1 to 3 and returns every table in a dictionary.

    `period_attributes` defines the instrument period (default: `attributes`).
    """
    period_attributes = list(attributes if period_attributes is None else period_attributes)
    needed = list(dict.fromkeys([*attributes, *period_attributes]))
    data = assign_metadata(residuals, metadata, needed)
    ratios = unit_ratios(data, channel, reference, period_attributes)
    per_unit = unit_ratios(data, channel, reference)
    effects = attribute_effects(ratios, attributes, n=n, seed=seed)
    intervals = {a: group_intervals(ratios, a, channel, reference, n=n, seed=seed)
                 for a in attributes}
    return {"data": data, "ratios": ratios, "per_unit": per_unit,
            "invariance": invariance(per_unit, channel, reference),
            "effects": effects, "intervals": intervals}
