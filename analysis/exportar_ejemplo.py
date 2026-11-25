"""Exports the residuals and instrument metadata of the article for `metaudit`.

    python -m analysis.exportar_ejemplo

Writes, in examples/epn/:
    residuals_e5b.csv   daily 3D error of GPS (G) and Galileo (E), weighted_mad,
                        Galileo on E1/E5b (release 1.4.0)
    residuals_e5a.csv   the same with Galileo on E1/E5a (release 1.3.0)
    metadata.csv        antenna model, radome, antenna serial, receiver model and
                        firmware of each station, with their validity periods,
                        from the EPN site logs

With these files the antenna analysis of the article (Tables 3, S4 and S6,
Figure 4) can be reproduced without the database; see docs/TUTORIAL.md. The
error is the distance between the SPP daily position and the NGL PPP position
of the same day, reduced to the monument (see `dataset.py`).
"""
from analysis._paths import REPO
from analysis.caracterizacion import cargar_todo
from analysis.dataset import ESTACIONES, SW_IDS, database_for

SALIDA = REPO / "examples" / "epn"

_METADATA = """
SELECT station_id AS unit, attribute, value, valid_from::date AS valid_from,
       valid_to::date AS valid_to
FROM (
    SELECT station_id, 'antenna_type' AS attribute, antenna_type AS value, valid_from, valid_to
      FROM station_antenna
    UNION ALL
    SELECT station_id, 'radome', radome, valid_from, valid_to FROM station_antenna
    UNION ALL
    SELECT station_id, 'antenna_serial', antenna_serial, valid_from, valid_to FROM station_antenna
    UNION ALL
    SELECT station_id, 'receiver_type', receiver_type, valid_from, valid_to FROM station_receiver
    UNION ALL
    SELECT station_id, 'firmware', firmware, valid_from, valid_to FROM station_receiver
) m
WHERE station_id = ANY(%(stations)s)
ORDER BY unit, attribute, valid_from
"""


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    for dataset in ["e5b", "e5a"]:
        df = cargar_todo(db=database_for(dataset), sw_id=SW_IDS[dataset])
        sub = df[(df["method"] == "weighted_mad") & df["constellation"].isin(["G", "E"])]
        out = sub.rename(columns={"station_id": "unit", "constellation": "channel",
                                  "err_3d": "error"})[["unit", "date", "channel", "error"]]
        out["channel"] = out["channel"].astype(str)
        out = out.sort_values(["unit", "date", "channel"])
        ruta = SALIDA / f"residuals_{dataset}.csv"
        out.to_csv(ruta, index=False, date_format="%Y-%m-%d", float_format="%.4f")
        print(f"{len(out)} rows -> {ruta}")

    import pandas as pd
    db = database_for("e5b")
    with db.get_cursor() as cur:
        cur.execute(_METADATA, {"stations": ESTACIONES})
        meta = pd.DataFrame([dict(r) for r in cur.fetchall()])
    ruta = SALIDA / "metadata.csv"
    meta.to_csv(ruta, index=False)
    print(f"{len(meta)} rows -> {ruta}")


if __name__ == "__main__":
    main()
