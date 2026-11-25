# User guide

The repository has three parts, which can be used separately:

| Part | What it does | Needs |
|---|---|---|
| `processor/` | SPP pipeline: daily positions of each station from its own RINEX files | PostgreSQL/PostGIS, network access to the IGN server |
| `analysis/` | The analysis of the article: error against NGL, tables, figures | the database filled by `processor/` |
| `metaudit/` | The diagnostic procedure of the article, independent of GNSS | only pandas and NumPy |

`metaudit` and the example data in `examples/epn/` reproduce the antenna
analysis of the article without the database; see [TUTORIAL.md](TUTORIAL.md).

---

## 1. `metaudit`: metadata-grouped residual audit

### Inputs

**Residuals** (CSV or DataFrame), one row per unit, day and channel:

| Column | Type | Meaning |
|---|---|---|
| `unit` | text | instrument or station identifier |
| `date` | date | day of the measurement |
| `channel` | text | measurement channel (constellation, frequency, component...) |
| `error` | float > 0 | discrepancy with an external reference |

**Metadata** (CSV or DataFrame), long format, one row per record of an attribute:

| Column | Type | Meaning |
|---|---|---|
| `unit` | text | as in the residuals |
| `attribute` | text | name of the attribute (`antenna_type`, `firmware`...) |
| `value` | text | value of the attribute in the record |
| `valid_from` | date or timestamp | start of validity |
| `valid_to` | date, timestamp or empty | end of validity; empty while in force |

Intervals are half-open on whole days, `[valid_from, valid_to)`: the day of a
change belongs to the new record. Each attribute may change on its own dates.

### Command line

```
python -m metaudit RESIDUALS METADATA --channel CH --reference REF --attributes A [B ...]
                   [--period-attributes A [B ...]] [--contrast ATTR VALUE [VALUE ...]]
                   [--compare RESIDUALS_AFTER] [--out PREFIX] [--n N] [--seed SEED]
python -m metaudit --synthetic [--out PREFIX]
```

| Option | Meaning |
|---|---|
| `--channel` | suspect channel |
| `--reference` | reference channel, measured by the same units |
| `--attributes` | attributes whose effect on the ratio is tested |
| `--period-attributes` | attributes that define an instrument period (default: `--attributes`) |
| `--contrast` | pre-specified two-group contrast: an attribute and the values of the first group |
| `--compare` | residuals of the same data processed with one choice changed |
| `--out` | prefix of the output CSV files |
| `--n` | permutations and bootstrap replicates (default 10 000) |
| `--seed` | random seed (default 20260921, the one of the article) |
| `--synthetic` | run on the synthetic network of `metaudit.synthetic` |

### Outputs

Printed, and written as `PREFIX_<table>.csv` with `--out`:

| Table | Columns | Meaning |
|---|---|---|
| `ratios` | `unit`, period attributes, reference, channel, `ratio` | median of each channel per unit and period, and their ratio |
| `effects` | `attribute`, `groups`, `eta2`, `p_eta2`, `range`, `p_range` | share of the variance of the log ratio explained by each attribute, with permutation p-values |
| `intervals_<attribute>` | attribute, `n`, `ratio`, `low`, `high` | ratio of each group with a 95 % interval resampling units; NaN bounds for single-unit groups |
| `compare` | keys, `*_before`, `*_after`, `ratio_change`, `reference_shift` | the two runs unit by unit |

The invariance (between-unit dispersion of the log error of the suspect channel
over that of the reference) and the contrast are printed only.

### Python interface

| Function | Step |
|---|---|
| `assign_metadata(residuals, metadata, attributes)` | 1. attributes in force on each date |
| `unit_ratios(data, channel, reference, period_attributes)` | 2. ratio per unit and period |
| `invariance(ratios, channel, reference)` | 2. dispersion of the suspect over the reference channel |
| `attribute_effects(ratios, attributes)` | 3. ranking of attributes by permutation |
| `permutation_test(ratios, attribute)` | 3. the test of one attribute, with its null distribution |
| `confusion(ratios, a, b)` | 3. can two attributes be separated? |
| `group_intervals(ratios, attribute, channel, reference)` | 3. bootstrap intervals per group |
| `contrast(ratios, attribute, group)` | 3. pre-specified two-group contrast |
| `compare_runs(before, after, channel, reference, keys)` | 4. one processing choice changed |
| `audit(residuals, metadata, channel, reference, attributes)` | steps 1 to 3 at once |

### Interpreting the results, and limits

- The unit, not the day, is the replicated observation: all tests resample or
  permute units. Days of one unit share instrument and site and are not
  independent.
- `eta2` weights groups by size; `range` describes the effect but has little
  power with many small groups. Single-unit groups get no interval and should
  not support conclusions on their own.
- Correlations between the ratio and its components are deliberately not
  computed: they are spurious by construction.
- Two attributes that always vary together (see `confusion`) cannot be
  separated with observational data. The procedure reports both; only an
  intervention, such as `--compare` with one processing choice changed or an
  equipment replacement, can decide.
- The reference channel must be measured by the same units at the same times,
  and must not be affected by the suspect cause. Its shift in `compare` bounds
  the part of the change that does not come from the choice under test.

### Tests

```bash
python -m unittest discover -s tests -v
```

They run on the synthetic network and on small hand-made tables, in about two
seconds, without data or database.

---

## 2. `processor/`: the SPP pipeline

### Configuration

| Setting | Where | Default | Meaning |
|---|---|---|---|
| `SPP_DATASET` | environment | `e5b` | processing set: `e5b` (release 1.4.0, results of the article) or `e5a` (release 1.3.0, antenna analysis) |
| `postgis.cfg`, `postgis_e5a.cfg` | file | | database of each set (template: `postgis.cfg.example`); `POSTGRES_*` environment variables override them |
| `INTERVAL` | `CONSTANTS.py` | 300 s | decimation of the observations |
| `HATCH_EPOCHS` | `CONSTANTS.py` | 10 | Hatch filter window, applied to the ionosphere-free combination |
| `ELEVATION_MASK` | `CONSTANTS.py` | 10° | elevation cut-off |
| `IONOFREE_PAIRS` | `CONSTANTS.py` | GPS L1/L2, Galileo E1/E5b, BeiDou B1I/B3I | frequency pair per system, in order of preference; the first is the clock reference |
| `WEIGHT_MODEL` | `CONSTANTS.py` | `system` | observation weighting: `none`, `system` or `elevation` (set by `SPP_DATASET`) |
| `SYSTEM_SIGMA` | `CONSTANTS.py` | G 1.0, E 0.5, C 1.1 m | relative code noise per system |
| `MAX_WORKERS` | `CONSTANTS.py` | 12 | parallel processes |

`SPP_DATASET` sets the Galileo pair, the weighting, the database and the
software version recorded with every solution, so that the two sets are never
mixed.

### Running

```bash
cd processor
python load_stations.py                       # station catalogue
python load_sitelogs.py --dir <site_logs>     # antenna and receiver history
python main.py [--stations ACOR ...] [--start 2023-10-01] [--end 2026-06-27] [--workers 12]
SPP_DATASET=e5a python main.py                # the E1/E5a set, into its own database
```

Defaults: the 27 stations and the period of the article. Observation and
navigation files are downloaded from the IGN ERGNSS server for each station-day;
a station-day whose files are missing is logged as `[WORKER ERROR]` and does not
stop the run. About 8 h for the whole period with 12 processes.

### Outputs (database)

| Table | Content |
|---|---|
| `runs` | one row per run: software version (`sw_id`), decimation, time |
| `daily_positions` | daily position per station, constellation (`G`, `E`, `C`, `GEC`) and estimator (`mean`, `median`, `weighted`, `mad`, `weighted_mad`), with its standard deviation and epochs used |
| `daily_statistics` | per station, day and constellation: satellites, DOP, residual RMS, clock bias, elevation statistics |

The schema is published in [GeoGNSS-PS](https://github.com/fbroncano/GeoGNSS-PS).

---

## 3. `analysis/`: the article

All scripts run from the repository root with `python -m analysis.<script>`
and read the set selected by `SPP_DATASET` (default `e5b`), except
`exportar_figuras` and `exportar_ejemplo`, which read both.

| Script | Options | Output | Article element |
|---|---|---|---|
| `reference` | `[STATION ...]` | `data/ngl/<STATION>.csv` | NGL reference series |
| `caracterizacion` | `--comun`, `--salida PREFIX`, `--stations`, `--desde`, `--hasta` | 20 combinations, per station and per antenna | Table 2, paired comparison, Table 3 |
| `receptor` | `--salida PREFIX` | antenna × receiver, permutations, intervals | Section 4.2, S4 |
| `observables` | `--cabeceras DIR`, `--salida PREFIX` | code resolved per band, C2S/C2W check | Section 4.2, 5.1, S4 |
| `relojes_galileo` | `--salida FILE` | I/NAV and F/NAV share, clock difference | S5 |
| `exportar_figuras` | | `analysis/figure_data/*.csv` | data of Figures 3–5 |
| `generate_figures` | | `figures/Figure3.pdf` … `Figure5.pdf` | Figures 3–5 |
| `exportar_ejemplo` | | `examples/epn/*.csv` | input of the tutorial |

Some option names and output columns keep their original Spanish names
(`--salida` for the output prefix, `mediana_3d` for the median 3D error...) so
that the outputs match those used to prepare the article. `observables` expects
one text file per station, `<STATION>.txt`, with the header of one of its RINEX
observation files.
