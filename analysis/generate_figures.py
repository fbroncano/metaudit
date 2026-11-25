"""Figures 3, 4 and 5 of the article.

The three figures are drawn from the CSV files in `analysis/figure_data/`,
written by `exportar_figuras.py`, without touching the PostGIS database, so
they can be regenerated on any machine with the repository. Every number shown
comes from those files; explanatory figures go in the captions.

    figures/Figure3.pdf  accuracy against reliability
    figures/Figure4.pdf  the degradation is specific to E1/E5a at the legacy antennas
    figures/Figure5.pdf  CACE series around the antenna replacement, both Galileo pairs

Figures 1 and 2 of the article (station map and pipeline diagram) were drawn by
hand and are not produced by this script.

Design decisions worth keeping:

  - Navy for GPS, orange for Galileo, dark outline with warm fill for GEC and
    for the legacy antennas.
  - Everything encoded with colour is also encoded with shape or a direct
    label: the article may be printed in greyscale.
  - Panel b of Figure 3 is a range chart, not a four-point scatter: the range
    from the median to the 99th percentile turns the tail into length, which
    is the magnitude the argument of the section rests on.
  - Figure 4 joins the E1/E5a and E1/E5b solutions of each degraded station
    with an arrow: the same station and days with another frequency pair is
    the evidence, so it is drawn as a movement and not as two scatters.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(AQUI, ".."))
DATOS = os.path.join(AQUI, "figure_data")
# Figures are written with their submission names (Figure3.pdf...) to figures/.
SALIDA = os.path.join(REPO, "figures")
os.makedirs(SALIDA, exist_ok=True)

# The two complementary fill colours.
FRIO = "#c4cff3"
CALIDO = "#f3e8c4"

# Both fills have a contrast of only 1.6 and 1.2 against white, so on their own
# they would be the least visible element exactly where the reader should look.
# Emphasis is carried by the dark outline, not the fill, which also survives
# greyscale printing.
CONTORNO = "#52514e"

# Series. GEC takes the dark outline with warm fill, the highlight treatment.
GPS = "#1f4e79"
GALILEO = "#d1663c"
GEC = CONTORNO
BEIDOU = "#7a8899"
NEUTRO = "#c3c2b7"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
APAGADO = "#898781"

ORDEN_METODO = ["mean", "weighted", "median", "mad", "weighted_mad"]

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8.5,
    "axes.edgecolor": APAGADO,
    "axes.labelcolor": TINTA,
    "axes.linewidth": 0.7,
    "xtick.color": TINTA_2,
    "ytick.color": TINTA_2,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "pdf.fonttype": 42,
})


def limpiar(ax, dejar=("left", "bottom")):
    for lado, spine in ax.spines.items():
        spine.set_visible(lado in dejar)


def miles(x):
    """66071.657 -> '66,072'. The article uses a thousands separator."""
    return f"{round(x):,}"


# --------------------------------------------------------------------------
# Figure 3: accuracy against reliability
# --------------------------------------------------------------------------

def figura_3():
    crudo = pd.read_csv(os.path.join(DATOS, "F2_estimadores.csv"), header=[0, 1], index_col=0)
    crudo = crudo.drop(index="metodo", errors="ignore").astype(float)

    const = pd.read_csv(os.path.join(DATOS, "F4_constelaciones.csv"))
    const = const.set_index("constelacion")

    fig = plt.figure(figsize=(6.95, 5.75))
    gs = fig.add_gridspec(
        2, 3, height_ratios=[1.0, 0.92], hspace=0.62, wspace=0.30,
        left=0.145, right=0.965, top=0.90, bottom=0.085,
    )

    # ---- panel (a): per estimator ------------------------------------------
    columnas = [
        ("mediana", "Median 3D error (m)", False),
        ("p99", "99th percentile (m)", True),
        ("fallo_10m_pct", "Days with error > 10 m (%)", False),
    ]
    y = np.arange(len(ORDEN_METODO))[::-1]  # mean on top

    ejes_a = []
    for i, (metrica, etiqueta, log) in enumerate(columnas):
        ax = fig.add_subplot(gs[0, i])
        ejes_a.append(ax)
        # GPS drawn above GEC: where both are zero, the filled triangle used
        # to hide the blue dot.
        ax.scatter(crudo[(metrica, "G")].reindex(ORDEN_METODO), y,
                   marker="o", s=34, color=GPS, zorder=5, label="GPS")
        ax.scatter(crudo[(metrica, "GEC")].reindex(ORDEN_METODO), y,
                   marker="^", s=44, facecolors=CALIDO, edgecolors=GEC,
                   linewidths=1.2, zorder=3, label="Multi-constellation (GEC)")
        if log:
            ax.set_xscale("log")
        ax.set_yticks(y)
        ax.set_yticklabels(ORDEN_METODO if i == 0 else [])
        ax.set_ylim(-0.7, len(ORDEN_METODO) - 0.3)
        ax.set_xlabel(etiqueta, fontsize=8.5)
        ax.axhline(2.5, color=APAGADO, lw=0.7, ls=(0, (4, 3)), zorder=1)
        ax.tick_params(length=2.5)
        limpiar(ax)

    ejes_a[0].text(-0.60, 0.965, "non-robust", transform=ejes_a[0].transAxes,
                   ha="left", va="center", fontsize=7.5, style="italic", color=APAGADO)
    ejes_a[0].text(-0.60, 0.60, "robust", transform=ejes_a[0].transAxes,
                   ha="left", va="center", fontsize=7.5, style="italic", color=APAGADO)


    fig.text(0.018, 0.975, "(a)", fontsize=10, fontweight="bold", va="top")
    fig.legend(
        handles=[
            Line2D([], [], marker="o", ls="none", color=GPS, markersize=6, label="GPS"),
            Line2D([], [], marker="^", ls="none", markerfacecolor=CALIDO,
                   markeredgecolor=GEC, markeredgewidth=1.2, markersize=7.5,
                   label="Multi-constellation (GEC)"),
        ],
        loc="upper center", bbox_to_anchor=(0.57, 1.005), ncol=2,
        frameon=False, fontsize=8.5, handletextpad=0.4, columnspacing=1.8,
    )

    # ---- panel (b): ranges per constellation ------------------------------
    ax = fig.add_subplot(gs[1, :])
    # The two numeric margin columns live outside the data area, so the axis is
    # narrowed to make room for them without overlapping the "max" labels.
    caja = ax.get_position()
    ax.set_position([caja.x0, caja.y0, caja.width * 0.775, caja.height])
    filas = [
        ("GPS", "G", GPS, FRIO),
        ("Galileo", "E", GALILEO, CALIDO),
        ("Multi-constellation", "GEC", GEC, CALIDO),
        ("BeiDou", "C", BEIDOU, FRIO),
    ]
    yy = np.arange(len(filas))[::-1]

    for (nombre, clave, color, pastel), yi in zip(filas, yy):
        r = const.loc[clave]
        ax.plot([r["mediana_3d"], r["p99_3d"]], [yi, yi], color=color, lw=3.2,
                solid_capstyle="round", zorder=2)
        ax.plot([r["p99_3d"], r["max_3d"]], [yi, yi], color=color, lw=0.8,
                ls=(0, (1.5, 1.5)), zorder=2)
        ax.plot([r["max_3d"]], [yi], marker="|", markersize=6, color=color,
                markeredgewidth=1.1, zorder=3)
        ax.plot([r["mediana_3d"]], [yi], marker="o", markersize=7, color=color, zorder=4)
        ax.plot([r["p99_3d"]], [yi], marker="o", markersize=7, markerfacecolor=pastel,
                markeredgecolor=color, markeredgewidth=1.6, zorder=4)

    ax.set_xscale("log")
    ax.set_xlim(0.8 * const["mediana_3d"].min(), 1.5 * const["max_3d"].max())
    ax.set_ylim(-1.0, len(filas) - 0.3)
    ax.set_yticks(yy)
    ax.set_yticklabels([n for n, _, _, _ in filas])
    marcas = [m for m in [0.2, 0.5, 1, 2, 5, 10, 20, 50, 100]
              if ax.get_xlim()[0] <= m <= ax.get_xlim()[1]]
    ax.set_xticks(marcas)
    ax.set_xticklabels([f"{m:g}" for m in marcas])
    ax.set_xlabel("Median 3D error  →  99th percentile (m), logarithmic", fontsize=8.5)
    ax.tick_params(length=2.5)
    limpiar(ax)

    # Two numeric margin columns give the third and fourth figures without extra
    # axes. The satellite column supports the "2.6 times more" statement.
    x_fallo, x_sat = 1.105, 1.265
    ax.text(x_fallo, 1.02, "days\n> 10 m", transform=ax.transAxes, fontsize=7.5,
            color=TINTA_2, ha="center", va="bottom", linespacing=1.3)
    ax.text(x_sat, 1.02, "sat per\nepoch", transform=ax.transAxes, fontsize=7.5,
            color=TINTA_2, ha="center", va="bottom", linespacing=1.3)
    for (nombre, clave, color, pastel), yi in zip(filas, yy):
        r = const.loc[clave]
        frac = (yi - ax.get_ylim()[0]) / (ax.get_ylim()[1] - ax.get_ylim()[0])
        resaltar = r["fallo_10m_%"] == 0
        ax.text(x_fallo, frac, f"{r['fallo_10m_%']:.2f} %", transform=ax.transAxes,
                fontsize=8, ha="center", va="center",
                color=TINTA if resaltar else TINTA_2,
                fontweight="bold" if resaltar else "normal")
        ax.text(x_sat, frac, f"{r['n_sat']:.1f}", transform=ax.transAxes,
                fontsize=8, ha="center", va="center", color=TINTA_2)


    fig.text(0.018, 0.455, "(b)", fontsize=10, fontweight="bold", va="top")

    destino = os.path.join(SALIDA, "Figure3.pdf")
    fig.savefig(destino, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    return destino


# --------------------------------------------------------------------------
# Figure 4: E1/E5a degrades Galileo at the legacy antennas, E1/E5b does not
# --------------------------------------------------------------------------

# Legacy antennas carry the warm fill; CACE, which replaced its legacy antenna
# during the period, the cold one; the rest are open.
ESTILO_ANTENA = {
    "heredada": dict(marker="o", s=50, facecolors=CALIDO, edgecolors=CONTORNO,
                     linewidths=1.3, zorder=5),
    "sustituida": dict(marker="D", s=44, facecolors=FRIO, edgecolors=CONTORNO,
                       linewidths=1.3, zorder=4),
    "moderna": dict(marker="o", s=30, facecolors="none", edgecolors=APAGADO,
                    linewidths=1.0, zorder=3),
}


def figura_4():
    est = pd.read_csv(os.path.join(DATOS, "F3_N1_por_estacion.csv"))
    ant = pd.read_csv(os.path.join(DATOS, "F5_por_antena.csv"))

    fig, (ax_a, ax_b) = plt.subplots(
        1, 2, figsize=(8.25, 3.70), gridspec_kw=dict(width_ratios=[1.0, 1.0], wspace=0.42)
    )
    fig.subplots_adjust(left=0.085, right=0.975, top=0.86, bottom=0.155)

    # ---- panel (a): each station with E1/E5a and with E1/E5b --------------
    # E1/E5a solutions with the antenna-status marker; E1/E5b solutions as
    # small dark dots. The degraded stations are joined by an arrow, which
    # carries the result: the same station, the same days, another frequency pair.
    for estado, kw in ESTILO_ANTENA.items():
        sub = est[est["estado_antena"] == estado]
        ax_a.scatter(sub["G_e5a"], sub["E_e5a"], **kw)
    ax_a.scatter(est["G_e5b"], est["E_e5b"], marker="o", s=9, color=TINTA_2,
                 linewidths=0, zorder=6)
    for _, r in est[est["estado_antena"] != "moderna"].iterrows():
        ax_a.annotate("", xy=(r["G_e5b"], r["E_e5b"]), xytext=(r["G_e5a"], r["E_e5a"]),
                      arrowprops=dict(arrowstyle="-|>", color=APAGADO, lw=0.7,
                                      shrinkA=4, shrinkB=2, mutation_scale=7),
                      zorder=2)
        ax_a.text(r["G_e5a"] + 0.012, r["E_e5a"], r["station_id"], fontsize=7,
                  color=TINTA_2, ha="left", va="center")

    lim = np.array([0.15, 15])
    ax_a.plot(lim, lim, ls=(0, (5, 4)), color=NEUTRO, lw=0.9, zorder=1)
    ax_a.set_yscale("log")
    ax_a.set_xlim(0.2, 0.75)
    ax_a.set_ylim(*lim)
    ax_a.set_yticks([0.2, 0.5, 1, 2, 5, 10])
    ax_a.set_yticklabels(["0.2", "0.5", "1", "2", "5", "10"])
    ax_a.set_xlabel("Median 3D error, GPS (m)", fontsize=8.5)
    ax_a.set_ylabel("Median 3D error, Galileo (m)", fontsize=8.5)
    ax_a.tick_params(length=2.5)
    limpiar(ax_a)
    ax_a.legend(
        handles=[
            Line2D([], [], marker="o", ls="none", markerfacecolor=CALIDO,
                   markeredgecolor=CONTORNO, markeredgewidth=1.3, markersize=7,
                   label="legacy antenna, E1/E5a"),
            Line2D([], [], marker="D", ls="none", markerfacecolor=FRIO,
                   markeredgecolor=CONTORNO, markeredgewidth=1.3, markersize=6,
                   label="replaced in 2025, E1/E5a"),
            Line2D([], [], marker="o", ls="none", markerfacecolor="none",
                   markeredgecolor=APAGADO, markersize=6, label="other, E1/E5a"),
            Line2D([], [], marker="o", ls="none", color=TINTA_2, markersize=3.5,
                   label="all stations, E1/E5b"),
        ],
        loc="lower left", bbox_to_anchor=(-0.02, 1.0), ncol=2, frameon=False,
        fontsize=7.3, handletextpad=0.3, columnspacing=1.0, borderaxespad=0.2,
    )

    # ---- panel (b): per antenna model, E1/E5a to E1/E5b ------------------
    ant = ant.sort_values("EG_e5a", ascending=True).reset_index(drop=True)
    yb = np.arange(len(ant))
    for yi, r in ant.iterrows():
        destacada = r["EG_e5a"] >= 2.0
        ax_b.plot([r["EG_e5a"], r["EG_e5b"]], [yi, yi], color=APAGADO, lw=0.9, zorder=2)
        ax_b.scatter([r["EG_e5a"]], [yi], marker="o", s=46 if destacada else 30,
                     facecolors=CALIDO if destacada else "white",
                     edgecolors=CONTORNO if destacada else APAGADO,
                     linewidths=1.3 if destacada else 1.0, zorder=4)
        ax_b.scatter([r["EG_e5b"]], [yi], marker="o", s=16, color=TINTA_2, zorder=5)
        ax_b.text(max(r["EG_e5a"], r["EG_e5b"]) * 1.30, yi,
                  f"{r['EG_e5a']:.2f} → {r['EG_e5b']:.2f}  ({r['n_est']})",
                  va="center", ha="left", fontsize=7.5, color=TINTA_2)

    ax_b.axvline(1.0, color=APAGADO, lw=0.8, zorder=1)
    ax_b.set_xscale("log")
    ax_b.set_xlim(0.4, 150)
    ax_b.set_xticks([0.5, 1, 2, 5, 10, 20])
    ax_b.set_xticklabels(["0.5", "1", "2", "5", "10", "20"])
    ax_b.set_yticks(yb)
    ax_b.set_yticklabels(ant["antenna_type"])
    ax_b.set_ylim(-0.7, len(ant) - 0.3)
    ax_b.set_xlabel("E/G ratio of the median 3D error, logarithmic", fontsize=8.5)
    ax_b.text(1.06, len(ant) - 0.45, "Galileo = GPS", fontsize=7, color=APAGADO,
              ha="left", va="center")
    ax_b.legend(
        handles=[
            Line2D([], [], marker="o", ls="none", markerfacecolor=CALIDO,
                   markeredgecolor=CONTORNO, markeredgewidth=1.3, markersize=7,
                   label="E1/E5a"),
            Line2D([], [], marker="o", ls="none", color=TINTA_2, markersize=4.5,
                   label="E1/E5b"),
        ],
        loc="lower left", bbox_to_anchor=(-0.02, 1.0), ncol=2, frameon=False,
        fontsize=7.5, handletextpad=0.3, columnspacing=1.2, borderaxespad=0.2,
    )
    ax_b.tick_params(length=2.5)
    limpiar(ax_b)

    fig.text(0.012, 0.985, "(a)", fontsize=10, fontweight="bold", va="top")
    fig.text(0.535, 0.985, "(b)", fontsize=10, fontweight="bold", va="top")

    destino = os.path.join(SALIDA, "Figure4.pdf")
    fig.savefig(destino, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    return destino


# --------------------------------------------------------------------------
# Figure 5: CACE series
# --------------------------------------------------------------------------

CAMBIO_CACE = pd.Timestamp("2025-03-19")

# GPS, and Galileo with each frequency pair. Every series differs from the
# others in colour and in line pattern, for greyscale printing.
SERIES_CACE = [
    ("G", "GPS", GPS, "-"),
    ("E_e5a", "Galileo E1/E5a", GALILEO, (0, (5, 2))),
    ("E_e5b", "Galileo E1/E5b", GALILEO, (0, (1, 1.2))),
]


def medianas_cace(s):
    """Median of each CACE series before and after the antenna replacement."""
    antes = s[s["date"] < CAMBIO_CACE].groupby("serie")["err_3d"].median()
    despues = s[s["date"] >= CAMBIO_CACE].groupby("serie")["err_3d"].median()
    return antes, despues


def figura_5():
    s = pd.read_csv(os.path.join(DATOS, "F6_cace_serie.csv"), parse_dates=["date"])

    fig, ax = plt.subplots(figsize=(7.30, 3.25))
    fig.subplots_adjust(left=0.085, right=0.985, top=0.88, bottom=0.135)

    ax.axvspan(CAMBIO_CACE, s["date"].max(), color=CALIDO, alpha=0.55, lw=0, zorder=0)

    for clave, nombre, color, trazo in SERIES_CACE:
        d = s[s["serie"] == clave].sort_values("date")
        ax.scatter(d["date"], d["err_3d"], s=2.2, color=color, alpha=0.18,
                   linewidths=0, zorder=2)
        movil = (d.set_index("date")["err_3d"]
                   .rolling("15D", center=True, min_periods=5).median())
        ax.plot(movil.index, movil.values, color=color, lw=1.4, ls=trazo,
                zorder=4, label=nombre)

    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[4, 10]))
    ax.set_yscale("log")
    ax.set_ylabel("Daily 3D error (m)", fontsize=8.5)
    ax.set_ylim(0.03, 10)
    ax.set_xlim(s["date"].min() - pd.Timedelta(days=15),
                s["date"].max() + pd.Timedelta(days=15))
    ax.tick_params(length=2.5)
    limpiar(ax)

    ax.axvline(CAMBIO_CACE, color=TINTA, lw=0.9, ls=(0, (6, 3)), zorder=5)


    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 1.13), ncol=3, frameon=False,
              fontsize=8.5, handletextpad=0.6, columnspacing=1.6, handlelength=2.6)

    destino = os.path.join(SALIDA, "Figure5.pdf")
    fig.savefig(destino, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    return destino


def comprobar_medianas():
    """Prints the CACE medians written on Figure 5, and the E/G of each pair."""
    s = pd.read_csv(os.path.join(DATOS, "F6_cace_serie.csv"), parse_dates=["date"])
    print("\nCACE before and after the antenna replacement of 2025-03-19")
    for nombre, med in zip(["before", "after"], medianas_cace(s)):
        print(f"  {nombre:6s}  GPS {med['G']:.3f}  Galileo E1/E5a {med['E_e5a']:.3f} "
              f"(E/G {med['E_e5a'] / med['G']:.2f})  Galileo E1/E5b {med['E_e5b']:.3f} "
              f"(E/G {med['E_e5b'] / med['G']:.2f})")


if __name__ == "__main__":
    comprobar_medianas()
    print("\n" + figura_3())
    print(figura_4())
    print(figura_5())
