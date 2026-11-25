"""metaudit: metadata-grouped residual audit for networks of instruments.

Finds a failure that affects one measurement channel of some instruments by
grouping the residuals on an instrument attribute the processing does not
consume, and checking that a reference channel of the same instruments stays
invariant. See `metaudit.core` for the procedure and docs/USER_GUIDE.md for
the input formats and options.
"""
from metaudit.core import (assign_metadata, attribute_effects, audit, compare_runs,
                           confusion, contrast, group_intervals, invariance,
                           permutation_test, unit_ratios)

__all__ = ["assign_metadata", "attribute_effects", "audit", "compare_runs", "confusion",
           "contrast", "group_intervals", "invariance", "permutation_test", "unit_ratios"]
__version__ = "1.0.0"
