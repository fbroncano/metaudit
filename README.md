# metaudit: metadata-grouped residual audit

With the SPP pipeline audited over the Spanish EPN stations.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23282342.svg)](https://doi.org/10.5281/zenodo.23282342)

Code accompanying the article:

> F. Broncano, M. Botejara-Antúnez, P. G. Rodríguez, A. Caro and A. Cuartero,
> *Diagnosing silent failures in GNSS network processing through metadata-grouped residual audits*
> (submitted).

It contains three things:

- **`metaudit/`**, the diagnostic procedure of the article as a reusable,
  GNSS-independent module. Given the residuals of a network of instruments on
  two channels and the history of their metadata, it finds which instrument
  attribute organises a failure that affects one channel only, and tests a
  processing change unit by unit.
- **`processor/`**, the standard point positioning (SPP) pipeline that was
  audited. It computes daily positions of each station from its own RINEX
  observation and navigation files, without precise products, for GPS,
  Galileo, BeiDou and their combination, with five daily estimators. Its
  method is described in F. Broncano, P. G. Rodríguez, A. Caro,
  J. A. Torrecilla-Pinero and A. Cuartero, *A Multi-Constellation Standard
  Point Positioning Pipeline and Its Validation over the Spanish Geodetic
  Network*, IEEE Access, 2026,
  [doi:10.1109/ACCESS.2026.3751207](https://doi.org/10.1109/ACCESS.2026.3751207).
- **`analysis/`**, the analysis that compares those positions with the daily
  PPP series of the Nevada Geodetic Laboratory (NGL) and produces the tables
  and figures of the article.

## Quick start, without database

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m unittest discover -s tests -v       # tests, about 2 s
python -m metaudit --synthetic                # the procedure on a synthetic network
python -m metaudit examples/epn/residuals_e5a.csv examples/epn/metadata.csv \
    --channel E --reference G --attributes antenna_type receiver_type \
    --contrast antenna_type LEIAT504GG TRM29659.00 LEIAR25 \
    --compare examples/epn/residuals_e5b.csv  # the antenna analysis of the article
```

The last command reproduces, from the files in `examples/epn/`, the antenna
analysis of the article (Section 4.2, Tables 3, S4 and S6, Figure 4) in a few
seconds. [docs/TUTORIAL.md](docs/TUTORIAL.md) walks through it step by step,
and [docs/USER_GUIDE.md](docs/USER_GUIDE.md) documents every input, output and
option.

## Repository structure

```
├── metaudit/                  metadata-grouped residual audit (GNSS-independent)
│   ├── core.py                the four steps of the procedure
│   ├── synthetic.py           synthetic network with a known failure
│   └── __main__.py            command-line interface
├── tests/                     unit tests of metaudit (no data needed)
├── examples/epn/              residuals and instrument metadata of the article
├── docs/                      user guide and tutorial
├── processor/                 SPP pipeline
│   ├── main.py                entry point: processes station-days and writes to PostGIS
│   ├── manage_files.py        download and reading of RINEX files (IGN ERGNSS server)
│   ├── pre_processor.py       observable selection, ionosphere-free combination, group delays, troposphere
│   ├── sv_processor.py        satellite positions from broadcast ephemerides
│   ├── hatchfilter.py         carrier smoothing of the ionosphere-free code (Hatch filter)
│   ├── gnss_processor.py      epoch-wise weighted least-squares solution
│   ├── post_processor.py      daily estimators, DOP and quality statistics
│   ├── glonass.py             GLONASS orbit propagation (not used in the article)
│   ├── utils.py               time, file-name and coordinate utilities
│   ├── CONSTANTS.py           configuration (decimation, Hatch window, frequency pairs, weighting...)
│   ├── dao.py, models.py      data-access layer over PostGIS
│   ├── load_stations.py       loads the station catalogue (estaciones_itrf2014.csv)
│   └── load_sitelogs.py       loads antenna and receiver history from EPN site logs
├── analysis/                  analysis of the article
│   ├── reference.py           downloads the NGL reference series into data/ngl/
│   ├── dataset.py             joins SPP solutions with the reference, ENU error
│   ├── geodesy.py             ECEF/geodetic/ENU conversions
│   ├── caracterizacion.py     the 20 constellation-estimator combinations, per station and per antenna
│   ├── receptor.py            antenna against receiver, intervals and permutation tests (uses metaudit)
│   ├── observables.py         observable resolved per band from the RINEX headers
│   ├── relojes_galileo.py     Galileo I/NAV and F/NAV clocks in the navigation files
│   ├── exportar_figuras.py    data of Figures 3, 4 and 5 from both processing sets
│   ├── exportar_ejemplo.py    writes examples/epn/
│   ├── generate_figures.py    Figures 3, 4 and 5
│   └── figure_data/           CSV files behind Figures 3, 4 and 5
├── patches/
│   └── georinex-nav3.patch    fix for the BeiDou ephemeris defect in georinex 1.16.2
├── postgis.cfg.example        database connection template
└── requirements.txt
```

## Requirements

Python 3.12 or later (the results were produced with 3.14) and the packages in
`requirements.txt`. `metaudit` and its tests need only NumPy and pandas.

**`georinex` must be patched** to run the pipeline. In version 1.16.2, the
RINEX 3 navigation reader discards an entire ephemeris when an empty field is
padded with spaces, which is how BeiDou writes it: without the patch no BeiDou
ephemeris is read, and the only trace is an INFO-level message
(`malformed line for Cxx`). Apply it to the installed package:

```bash
SITE="$(python -c 'import georinex, os; print(os.path.dirname(os.path.dirname(georinex.__file__)))')"
patch -p2 --directory="$SITE" < patches/georinex-nav3.patch
```

(or clone georinex 1.16.2, apply the patch with `patch -p1` and install it with
`pip install .`).

## The two processing sets

The article uses the same 27 stations and 1 001 days processed twice, selected
with the `SPP_DATASET` environment variable:

| `SPP_DATASET` | Galileo pair | Weighting | Release | Used for |
|---|---|---|---|---|
| `e5b` (default) | E1/E5b, reference of the I/NAV clock | by system | 1.4.0 | all results of the article |
| `e5a` | E1/E5a | by elevation and system | 1.3.0 | the antenna analysis (Section 4.2) |

With E1/E5a, stations with certain legacy antennas show a Galileo-only
degradation that disappears with E1/E5b; the article uses the contrast to
locate the failure in the E5a band. The variable sets the Galileo pair, the
weighting, the database (`postgis.cfg` or `postgis_e5a.cfg`) and the software
version recorded with each solution, so the two sets are never mixed.
Recomputing station-days with the published code reproduces the stored
positions of both sets to the millimetre.

## Database

Solutions, quality statistics and station metadata are stored in PostgreSQL
with PostGIS. This repository contains only the data-access layer
(`processor/dao.py`). The schema, the SQL functions used by the DAO and the
containerised deployment are published in
[GeoGNSS-PS](https://github.com/fbroncano/GeoGNSS-PS). Each processing set needs
its own database, because the unique key of `daily_positions` does not include
the run.

```bash
cp postgis.cfg.example postgis.cfg            # E1/E5b set
cp postgis.cfg.example postgis_e5a.cfg        # E1/E5a set
```

Both files are ignored by git. They are looked up from `processor/` upwards,
and any `POSTGRES_*` environment variable overrides them.

## Reproducing the article

```bash
# 1. Station metadata
cd processor
python load_stations.py                           # station catalogue
python load_sitelogs.py --dir <site_logs>         # EPN site logs (https://epncb.oma.be/ftp/station/log/)

# 2. SPP processing of both sets (downloads RINEX files from the IGN server; about 8 h each)
python main.py --start 2023-10-01 --end 2026-06-27 --workers 12
SPP_DATASET=e5a python main.py --start 2023-10-01 --end 2026-06-27 --workers 12
cd ..

# 3. Reference series
python -m analysis.reference

# 4. Analysis
python -m analysis.caracterizacion --salida results/caracterizacion
python -m analysis.caracterizacion --comun --salida results/caracterizacion_comun
SPP_DATASET=e5a python -m analysis.receptor --salida results/receptor_e5a
python -m analysis.observables --cabeceras <headers_dir> --salida results/observables
python -m analysis.relojes_galileo --salida results/relojes_galileo.csv

# 5. Figures 3-5 and the example data
python -m analysis.exportar_figuras
python -m analysis.generate_figures               # written to figures/
python -m analysis.exportar_ejemplo
```

| Article element | Script |
|---|---|
| Table 2 (20 combinations), Figure 3 | `caracterizacion.py` |
| Paired comparison over 23 stations | `caracterizacion.py --comun` |
| Table 3, Figure 4, Table S6 (per antenna and per station, both pairs) | `exportar_figuras.py`, or `metaudit` on `examples/epn/` |
| Permutation tests, intervals, receiver checks (S4) | `receptor.py` (`SPP_DATASET=e5a`) or `metaudit` |
| Observation codes and the C2S/C2W check | `observables.py` |
| Galileo clocks (S5) | `relojes_galileo.py` |
| CACE series, Figure 5 and Table S2 | `exportar_figuras.py` |
| Figures 3, 4 and 5 | `generate_figures.py` |

Figures 1 and 2 (station map and pipeline diagram) were drawn by hand and are
not generated by this code. `observables.py` expects one text file per station
(`<STATION>.txt`) with the header of one of its RINEX observation files.

## Versions

The software version of every run is recorded in the `runs` table, and every
position and statistic carries its run.

| Pipeline release | Change |
|---|---|
| 1.1.0 | Version archived as release 1.0.0 of this repository (Zenodo, October 2026), with the first draft of the article. |
| 1.2.0 | The Hatch filter smooths the ionosphere-free combination instead of each frequency separately. Smoothing each frequency and combining afterwards only cancels the code-carrier ionospheric divergence when both filters share the same history; with 300 s decimation the second frequency was reset about twice as often by the cycle-slip test, and the surviving divergence biased the daily positions by up to 1.7 m, mostly to the east and largest in summer. Detected by comparison with RTKLIB and with the NGL series. |
| 1.3.0 | BeiDou group delays (TGD1, TGD2) applied to the B1I/B3I and B1I/B2I combinations; weighted least squares by elevation and system. The E1/E5a set of the article. |
| 1.4.0 | Galileo processed with E1/E5b, the pair to which the I/NAV clocks refer, instead of E1/E5a; weighting by system only. The results of the article. |

| Repository release | Content |
|---|---|
| 1.0.0 | Pipeline 1.1.0 and the analysis of the first draft. |
| 2.0.0 | Pipeline 1.4.0 with the `SPP_DATASET` switch, `metaudit`, tests, example data, user guide and tutorial. The results of the submitted article. |

## Known defects

- For each band, the pipeline selects the first observation code in the RINEX
  header that matches the band prefix, regardless of the tracking attribute. At
  stations that declare `C2S` before `C2W`, the second GPS frequency is
  resolved to the civil code rather than to the P(Y) code to which the
  broadcast clock refers. The article finds no measurable effect (Section 5.1).
- The navigation files carry two Galileo messages for each satellite and epoch,
  I/NAV and F/NAV, and the pipeline keeps the first record without looking at
  the message. In practice 97.5 % of the records kept are I/NAV
  (`relojes_galileo.py`); the remaining 2.5 % are used with an E1/E5b
  combination their clock does not refer to, at a cost of about 0.2 m on those
  records.

Both behaviours are kept as published so that the results can be reproduced.

## Data sources

- GNSS observation and navigation files: Instituto Geográfico Nacional, ERGNSS
  network (`https://datos-geodesia.ign.es/ERGNSS/`).
- Station site logs: EPN Central Bureau (`https://epncb.oma.be/`).
- Reference series: Nevada Geodetic Laboratory, IGS20 `tenv3` series
  (`https://geodesy.unr.edu/`). Downloaded by `analysis/reference.py`, not
  redistributed.
- `examples/epn/` contains only derived products of this work (daily errors
  against the NGL series) and the metadata of the public EPN site logs.

## Licence and citation

MIT licence (see `LICENSE`). If you use this code, please cite the article and
the archived release: DOI [10.5281/zenodo.23282342](https://doi.org/10.5281/zenodo.23282342)
(all versions; see `CITATION.cff`).
