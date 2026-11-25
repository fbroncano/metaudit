# Tutorial: finding a channel-specific instrument failure with `metaudit`

This tutorial runs the diagnostic procedure of the article twice: first on a
synthetic network where the answer is known, then on the real residuals of the
27 Spanish EPN stations, where it reproduces the antenna analysis of the
article (Tables 3, S4 and S6, Figure 4). Neither part needs the database or any
GNSS file. Each command runs in a few seconds from the repository root.

The question the procedure answers is: *one measurement channel is degraded at
some instruments; is the cause an instrument attribute, and which one?* It needs
two channels measured by the same instruments, one suspect and one reference,
and a record of the instrument attributes over time.

## 1. A synthetic network

`metaudit.synthetic.make_network` builds 30 units observed for 200 days on two
channels, `ref` and `sus`. Every unit has a site effect that scales both
channels. The three units with instrument model `LEGACY` multiply the error of
`sus` by 8. Receiver `R1` accompanies the legacy units and eight modern ones,
so it is related to the failure without causing it. Unit `U03` replaces its
legacy instrument half way through.

```bash
python -m metaudit --synthetic
```

The output, abridged:

```
31 unit periods, 30 units
invariance: between-unit dispersion of the log error is 2.2 times larger for sus than for ref

=== Attributes ranked by the variance of the log ratio they explain ===
 attribute  groups   eta2  p_eta2  range  p_range
instrument       4 0.9964  0.0004 2.0912   0.0051
  receiver       3 0.1921  0.0856 0.0489   0.2335

=== Contrast instrument in ['LEGACY'] against the rest ===
 log_difference  ratio_of_medians      p  n_group  n_rest
         2.0748            7.9627 0.0038        3      28
```

How to read it:

- **Invariance.** The suspect channel varies between units twice as much as the
  reference. A cause acting on the site would move both channels together.
- **Ranking.** The instrument model explains almost all the variance of the
  log ratio; the receiver, which shares units with it, explains little and is
  not significant. The procedure does not blame the confounded attribute.
- **Contrast.** The pre-specified group recovers the factor of 8 put into the
  simulation.
- **Periods.** `U03` contributes two rows, one per instrument, so its
  replacement does not average two instruments into one.

The last table compares this run with a second one generated without the
failure (`degraded=False`): the ratio of the legacy units falls by a factor of
8 and nothing else moves. In a real case, the second run is the same data
processed again with one processing choice changed.

## 2. The case of the article

`examples/epn/` contains the daily 3D error of GPS (`G`) and Galileo (`E`) at
the 27 stations over 1 001 days, with the robust estimator `weighted_mad`, in
the two processing sets of the article:

| File | Galileo pair | Role |
|---|---|---|
| `residuals_e5a.csv` | E1/E5a | where the degradation appears |
| `residuals_e5b.csv` | E1/E5b | the same data with one processing choice changed |
| `metadata.csv` | | antenna model, radome, antenna serial, receiver model and firmware, with validity periods, from the EPN site logs |

### 2.1 From the command line

```bash
python -m metaudit examples/epn/residuals_e5a.csv examples/epn/metadata.csv \
    --channel E --reference G \
    --attributes antenna_type receiver_type \
    --contrast antenna_type LEIAT504GG TRM29659.00 LEIAR25 \
    --compare examples/epn/residuals_e5b.csv --out results/epn
```

It prints the figures of Section 4.2 and supplementary S4 of the article:
invariance 4.3; antenna model η² = 0.907 (p = 0.0001) against receiver model
0.142 (p = 0.19); the 95 % intervals of Table S4; a legacy-against-modern ratio
of 8.09 (p = 0.0002); and, unit by unit, the E1/E5b test of Table S6. The CSV
files are written with the prefix given in `--out`.

### 2.2 Step by step from Python

```python
import pandas as pd
import metaudit

res = pd.read_csv("examples/epn/residuals_e5a.csv", parse_dates=["date"])
meta = pd.read_csv("examples/epn/metadata.csv")

# Step 1: the antenna and receiver in force on each day.
data = metaudit.assign_metadata(res, meta, ["antenna_type", "receiver_type"])

# Step 2: Galileo/GPS ratio per station and instrument period, and invariance.
ratios = metaudit.unit_ratios(data, "E", "G", ["antenna_type", "receiver_type"])
per_station = metaudit.unit_ratios(data, "E", "G")
metaudit.invariance(per_station, "E", "G")          # 4.3
```

`ratios` has one row per (station, antenna, receiver). Its first rows:

```
unit antenna_type receiver_type     G      E  ratio
IZAN   LEIAT504GG    LEICA GR50 0.561 11.123 19.833
ZARA  TRM29659.00 TRIMBLE NETR9 0.628  8.245 13.125
ALME  TRM29659.00 TRIMBLE NETR9 0.623  5.495  8.818
LEON      LEIAR25    LEICA GR50 0.421  2.868  6.814
CACE  TRM29659.00 TRIMBLE NETR9 0.576  2.186  3.795
ACOR     LEIAT504    LEICA GR50 0.294  0.501  1.705
```

GPS stays between 0.29 and 0.63 m while Galileo spans a factor of forty. Step 3
asks which attribute organises the ratio:

```python
metaudit.attribute_effects(ratios, ["antenna_type", "receiver_type"])
#      attribute  groups   eta2  p_eta2 ...
#   antenna_type       9  0.907  0.0001
#  receiver_type       4  0.142  0.1924

metaudit.confusion(ratios, "antenna_type", "receiver_type")   # can they be separated?
metaudit.group_intervals(ratios, "antenna_type", "E", "G")    # Table S4
metaudit.contrast(ratios, "antenna_type", ["LEIAT504GG", "TRM29659.00", "LEIAR25"])
# ratio_of_medians 8.09, p 0.0002
```

Step 4 is the test that locates the failure. The second file is the same
period processed with Galileo on E1/E5b instead of E1/E5a:

```python
after = pd.read_csv("examples/epn/residuals_e5b.csv", parse_dates=["date"])
data_after = metaudit.assign_metadata(after, meta, ["antenna_type", "receiver_type"])
ratios_after = metaudit.unit_ratios(data_after, "E", "G", ["antenna_type", "receiver_type"])
metaudit.compare_runs(ratios, ratios_after, "E", "G",
                      ["unit", "antenna_type", "receiver_type"])
```

```
unit antenna_type  ratio_before  ratio_after  ratio_change  reference_shift
IZAN   LEIAT504GG        19.833        0.535         0.027           -0.015
ZARA  TRM29659.00        13.125        0.483         0.037           -0.075
ALME  TRM29659.00         8.818        0.508         0.058           -0.048
LEON      LEIAR25         6.814        2.752         0.404           -0.074
CACE  TRM29659.00         3.795        0.560         0.147           -0.042
ACOR     LEIAT504         1.705        1.126         0.660           -0.043
```

The degraded stations fall to the bottom of the network, while the reference
channel, GPS, moves by centimetres (`reference_shift`, between −0.24 and
+0.06 m over all units): the degradation is in the E5a band. LEON keeps a
ratio of 2.75, the residual discussed in the limitations of the article.

### 2.3 Choosing the unit of analysis

The attributes passed as `period_attributes` define when an instrument period
changes. The article uses antenna and receiver, so that a station that replaced
either contributes one row per configuration. Adding more attributes splits
the stations into more periods:

```python
attrs = ["antenna_type", "receiver_type", "radome", "firmware"]
data = metaudit.assign_metadata(res, meta, attrs)
r4 = metaudit.unit_ratios(data, "E", "G", attrs)
metaudit.attribute_effects(r4, attrs)
#     attribute  groups   eta2  p_eta2
#  antenna_type       9  0.890  0.0001
#        radome       6  0.708  0.0001
#      firmware       6  0.118  0.35
# receiver_type       4  0.089  0.23
```

The antenna still leads. The radome also explains much of the variance, but
only because it is nearly determined by the antenna model (`confusion` shows
it); an attribute that is a proxy of another cannot be separated from it with
observational data, and the procedure says so rather than choosing.

## 3. Your own network

Prepare two CSV files:

- **residuals**: `unit, date, channel, error`, one row per instrument, day and
  channel. `error` is any non-negative discrepancy with an external reference
  (the method takes logarithms of ratios of medians).
- **metadata**: `unit, attribute, value, valid_from, valid_to`, one row per
  record of an attribute; `valid_to` empty while still in force. A GNSS site
  log, a seismic station inventory (StationXML) or a calibration register
  convert directly to this format.

Then:

```bash
python -m metaudit residuals.csv metadata.csv --channel <suspect> \
    --reference <reference> --attributes <attr1> <attr2> ...
```

and, if a processing choice is suspected, process the data a second time
changing only that choice and pass it with `--compare`. See
[USER_GUIDE.md](USER_GUIDE.md) for every option and output column.
