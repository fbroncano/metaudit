"""Exports the CSV files behind Figures 3, 4 and 5 from the two sets of solutions.

    python -m analysis.exportar_figuras

Figure 3 uses only the e5b set (release 1.4.0, the results of the article).
Figures 4 and 5 compare both: with E1/E5a (set e5a) the stations with legacy
antennas show a Galileo-only degradation, and with E1/E5b (set e5b) it is gone.
Each set is read from its own database (`postgis.cfg`, `postgis_e5a.cfg`).

Outputs, in analysis/figure_data/:
    F2_estimadores.csv      Figure 3a: median, p99 and days > 10 m per estimator
    F4_constelaciones.csv   Figure 3b: weighted_mad per constellation
    F3_N1_por_estacion.csv  Figure 4a: median GPS and Galileo error per station, both sets
    F5_por_antena.csv       Figure 4b: E/G per antenna model, both sets
    F6_cace_serie.csv       Figure 5:  daily CACE series, GPS and Galileo with both pairs
"""
import os

import pandas as pd

from analysis.caracterizacion import cargar_todo, marcar_gec_real, por_antena, por_estacion, tabla
from analysis.dataset import SW_IDS, database_for
from analysis.receptor import HEREDADAS

DATOS = os.path.join(os.path.dirname(__file__), "figure_data")

# CACE replaced its legacy antenna on 2025-03-19: it is shown apart in Figure 4a.
SUSTITUIDA = "CACE"


def cargar(dataset):
    df = cargar_todo(db=database_for(dataset), sw_id=SW_IDS[dataset])
    print(f"{dataset}: {len(df)} solutions, {df['station_id'].nunique()} stations")
    return marcar_gec_real(df)


def figura_3(df):
    out = tabla(df)
    est = pd.concat({"mediana": out["mediana_3d"], "p99": out["p99_3d"],
                     "fallo_10m_pct": out["fallo_10m_%"]}, axis=1)
    est = est.unstack("constelacion").astype(float)
    est.to_csv(os.path.join(DATOS, "F2_estimadores.csv"))

    const = out.xs("weighted_mad", level="metodo")[
        ["n", "mediana_3d", "prec_3d", "p99_3d", "max_3d", "fallo_10m_%", "n_sat"]]
    # The maxima of the non-robust estimators, annotated on panel a.
    for metodo in ["mean", "weighted"]:
        const[f"max_{metodo}"] = out.xs(metodo, level="metodo")["max_3d"]
    const.to_csv(os.path.join(DATOS, "F4_constelaciones.csv"))


def figura_4(mejor):
    estaciones = {}
    antenas = {}
    for dataset, sub in mejor.items():
        est = por_estacion(sub)[["G", "E"]]
        est["EG"] = est["E"] / est["G"]
        estaciones[dataset] = est
        ant = por_antena(sub)[["G", "E", "E/G", "n_est", "estaciones"]]
        antenas[dataset] = ant.rename(columns={"E/G": "EG"})

    # Antenna per station: the model in force on most days.
    antena = (mejor["e5b"].groupby("station_id", observed=True)["antenna_type"]
                          .agg(lambda s: s.mode().iat[0]))
    heredada = (mejor["e5b"].groupby("station_id", observed=True)["antenna_type"]
                            .agg(lambda s: s.isin(HEREDADAS).any()))
    est = pd.concat({k: v for k, v in estaciones.items()}, axis=1)
    est.columns = [f"{m}_{d}" for d, m in est.columns]
    est.insert(0, "antena", antena)
    est["estado_antena"] = [
        "sustituida" if s == SUSTITUIDA else ("heredada" if heredada[s] else "moderna")
        for s in est.index]
    est.sort_values("EG_e5a", ascending=False).to_csv(
        os.path.join(DATOS, "F3_N1_por_estacion.csv"), index_label="station_id")

    ant = antenas["e5a"][["n_est", "estaciones"]].copy()
    for dataset, a in antenas.items():
        for col in ["G", "E", "EG"]:
            ant[f"{col}_{dataset}"] = a[col]
    ant.sort_values("EG_e5a", ascending=False).to_csv(
        os.path.join(DATOS, "F5_por_antena.csv"), index_label="antenna_type")


def figura_5(mejor):
    series = {"G": mejor["e5b"], "E_e5a": mejor["e5a"], "E_e5b": mejor["e5b"]}
    filas = []
    for serie, sub in series.items():
        const = "G" if serie == "G" else "E"
        d = sub[(sub["station_id"] == "CACE") & (sub["constellation"] == const)]
        filas.append(d[["date", "err_3d", "d_e", "d_n", "d_u", "std_3d"]].assign(serie=serie))
    out = pd.concat(filas).sort_values(["date", "serie"])
    out[["date", "serie", "err_3d", "d_e", "d_n", "d_u", "std_3d"]].to_csv(
        os.path.join(DATOS, "F6_cace_serie.csv"), index=False)


def main():
    df = {d: cargar(d) for d in ["e5b", "e5a"]}
    mejor = {d: v[v["method"] == "weighted_mad"] for d, v in df.items()}
    figura_3(df["e5b"])
    figura_4(mejor)
    figura_5(mejor)
    print(f"figure data written to {os.path.normpath(DATOS)}")


if __name__ == "__main__":
    main()
