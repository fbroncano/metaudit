"""Which Galileo clock does the processor use, and what would the wrong one cost?

The navigation files carry two Galileo messages for the same satellite and
epoch: I/NAV, whose clock refers to the E1/E5b ionosphere-free combination, and
F/NAV, whose clock refers to E1/E5a. `manage_files.clean_nav_df` keeps one record
per (epoch, satellite), the first one in the file, without looking at the
message. This script measures, over a sample of station-days:

  1. the share of I/NAV and F/NAV among the records the processor keeps, and
  2. the difference between the I/NAV and F/NAV clocks of the same satellite
     and epoch, in metres. It bounds the error of combining E1/E5a with an
     I/NAV clock (or E1/E5b with an F/NAV one) without group delay correction.

The RINEX `DataSrc` field identifies the message: bit 0 or 2 for I/NAV
(E1-B, E5b-I), bit 1 for F/NAV (E5a-I).

    python -m analysis.relojes_galileo [--salida results/relojes_galileo.csv]

The navigation files are downloaded from the IGN server into data/nav/.
"""
import argparse
import os
from datetime import date

import numpy as np
import pandas as pd
import requests

import analysis._paths  # noqa: F401  (puts processor/ on sys.path)
from analysis._paths import REPO
from analysis.dataset import ESTACIONES
from manage_files import clean_nav_df, load_files
from utils import nav_filename

C = 299_792_458.0
DIAS = [date(2025, 1, 15), date(2025, 4, 15), date(2025, 7, 15), date(2025, 10, 15)]
CARPETA = REPO / "data" / "nav"
URL = "https://datos-geodesia.ign.es/ERGNSS/diario_30s/{year}/{ymd}/{name}"


def mensaje(datasrc):
    """'I/NAV', 'F/NAV' or None from the RINEX DataSrc bits."""
    if not np.isfinite(datasrc):
        return None
    bits = int(datasrc)
    if bits & 0b010:
        return "F/NAV"
    if bits & 0b101:
        return "I/NAV"
    return None


def descargar(station, dia):
    nombre = nav_filename(station, dia.day, dia.month, dia.year)
    ruta = CARPETA / nombre
    if ruta.exists():
        return ruta
    url = URL.format(year=dia.year, ymd=dia.strftime("%Y%m%d"), name=nombre)
    for _ in range(3):
        try:
            r = requests.get(url, timeout=60)
        except requests.exceptions.RequestException:
            continue
        if r.status_code != 200:
            return None
        ruta.write_bytes(r.content)
        return ruta
    print(f"  {nombre}: server not responding, skipped")
    return None


def analizar(ruta):
    crudo, _ = load_files(str(ruta), navigation=True)
    gal = crudo[crudo.index.get_level_values("sv").str.startswith("E")]
    todas = gal.dropna(how="all").reset_index()
    todas["sv"] = todas["sv"].str.split("_").str[0]
    todas["msg"] = todas["DataSrc"].map(mensaje)

    # What the processor keeps: the same deduplication as clean_nav_df.
    usadas = clean_nav_df(gal).reset_index()
    usadas["msg"] = usadas["DataSrc"].map(mensaje)

    # Same satellite and epoch with both messages: clock difference.
    pares = todas.pivot_table(index=["time", "sv"], columns="msg",
                              values="SVclockBias", aggfunc="first")
    pares = pares.dropna(subset=[c for c in ["I/NAV", "F/NAV"] if c in pares])
    dif = ((pares["I/NAV"] - pares["F/NAV"]) * C).to_numpy() if len(pares) else np.array([])
    return usadas["msg"].value_counts(), dif


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--salida", default=None, help="CSV with the per-file counts")
    args = parser.parse_args()
    CARPETA.mkdir(parents=True, exist_ok=True)

    filas, difs = [], []
    for dia in DIAS:
        for station in ESTACIONES:
            ruta = descargar(station, dia)
            if ruta is None:
                continue
            cuenta, dif = analizar(ruta)
            filas.append({"station_id": station, "date": dia,
                          "inav": int(cuenta.get("I/NAV", 0)),
                          "fnav": int(cuenta.get("F/NAV", 0)),
                          "pairs": len(dif)})
            difs.append(dif)

    tabla = pd.DataFrame(filas)
    dif = np.concatenate(difs)
    total = tabla["inav"].sum() + tabla["fnav"].sum()
    print(f"{len(tabla)} navigation files, {tabla['station_id'].nunique()} stations, {len(DIAS)} days")
    print(f"records kept by the processor: I/NAV {tabla['inav'].sum()} "
          f"({100 * tabla['inav'].sum() / total:.1f} %), F/NAV {tabla['fnav'].sum()} "
          f"({100 * tabla['fnav'].sum() / total:.1f} %)")
    print(f"I/NAV - F/NAV clock, same satellite and epoch, n = {len(dif)}: "
          f"median {np.median(dif):+.3f} m, median |d| {np.median(np.abs(dif)):.3f} m, "
          f"p95 |d| {np.percentile(np.abs(dif), 95):.3f} m, max |d| {np.abs(dif).max():.3f} m")
    if args.salida:
        tabla.to_csv(args.salida, index=False)


if __name__ == "__main__":
    main()
