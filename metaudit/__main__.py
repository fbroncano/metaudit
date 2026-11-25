"""Command-line interface.

    python -m metaudit RESIDUALS METADATA --channel E --reference G \
        --attributes antenna_type receiver_type [--period-attributes ...] \
        [--compare RESIDUALS_AFTER] [--contrast antenna_type LEIAT504GG TRM29659.00] \
        [--out PREFIX] [--n 10000] [--seed 20260921]

    python -m metaudit --synthetic [--out PREFIX]

RESIDUALS is a CSV with columns unit, date, channel, error; METADATA a CSV with
columns unit, attribute, value, valid_from, valid_to. See docs/USER_GUIDE.md.
"""
import argparse
import sys

import pandas as pd

from metaudit import core, synthetic


def _print(title, table):
    print(f"\n=== {title} ===")
    print(table.round(4).to_string(index=False) if isinstance(table, pd.DataFrame) else table)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m metaudit", description=__doc__.splitlines()[0])
    p.add_argument("residuals", nargs="?")
    p.add_argument("metadata", nargs="?")
    p.add_argument("--channel", help="suspect channel")
    p.add_argument("--reference", help="reference channel, measured by the same units")
    p.add_argument("--attributes", nargs="+", help="attributes to test")
    p.add_argument("--period-attributes", nargs="+", default=None,
                   help="attributes that define an instrument period (default: --attributes)")
    p.add_argument("--compare", default=None,
                   help="residuals of a second processing run of the same data")
    p.add_argument("--contrast", nargs="+", default=None, metavar=("ATTRIBUTE", "VALUE"),
                   help="pre-specified contrast: an attribute and the values of the first group")
    p.add_argument("--out", default=None, help="prefix of the output CSV files")
    p.add_argument("--n", type=int, default=core.N_RESAMPLES, help="permutations and bootstrap replicates")
    p.add_argument("--seed", type=int, default=core.SEED)
    p.add_argument("--synthetic", action="store_true",
                   help="run on the synthetic network of metaudit.synthetic")
    a = p.parse_args(argv)

    if a.synthetic:
        residuals, metadata = synthetic.make_network()
        after, _ = synthetic.make_network(degraded=False)
        a.channel, a.reference = synthetic.SUSPECT, synthetic.REFERENCE
        a.attributes = a.attributes or ["instrument", "receiver"]
        a.contrast = a.contrast or ["instrument", synthetic.LEGACY]
    else:
        if not (a.residuals and a.metadata and a.channel and a.reference and a.attributes):
            p.error("RESIDUALS, METADATA, --channel, --reference and --attributes are required")
        residuals = pd.read_csv(a.residuals, parse_dates=["date"])
        metadata = pd.read_csv(a.metadata)
        after = pd.read_csv(a.compare, parse_dates=["date"]) if a.compare else None

    res = core.audit(residuals, metadata, a.channel, a.reference, a.attributes,
                     a.period_attributes, n=a.n, seed=a.seed)
    print(f"{res['ratios'].shape[0]} unit periods, {res['per_unit'].shape[0]} units")
    print(f"invariance: between-unit dispersion of the log error is "
          f"{res['invariance']:.1f} times larger for {a.channel} than for {a.reference}")
    _print("Attributes ranked by the variance of the log ratio they explain", res["effects"])
    for attr, table in res["intervals"].items():
        _print(f"Ratio per {attr}, 95 % interval resampling units", table)

    tables = {"ratios": res["ratios"], "effects": res["effects"],
              **{f"intervals_{k}": v for k, v in res["intervals"].items()}}

    if a.contrast:
        c = core.contrast(res["ratios"], a.contrast[0], a.contrast[1:], n=a.n, seed=a.seed)
        _print(f"Contrast {a.contrast[0]} in {a.contrast[1:]} against the rest",
               pd.DataFrame([c]))

    if after is not None:
        data_after = core.assign_metadata(after, metadata,
                                          list(a.period_attributes or a.attributes))
        ratios_after = core.unit_ratios(data_after, a.channel, a.reference,
                                        list(a.period_attributes or a.attributes))
        keys = ["unit", *(a.period_attributes or a.attributes)]
        cmp = core.compare_runs(res["ratios"], ratios_after, a.channel, a.reference, keys)
        _print("Second run against the first, unit by unit", cmp)
        tables["compare"] = cmp

    if a.out:
        for name, table in tables.items():
            table.to_csv(f"{a.out}_{name}.csv", index=False)
        print(f"\ntables written with prefix {a.out}_")
    return 0


if __name__ == "__main__":
    sys.exit(main())
