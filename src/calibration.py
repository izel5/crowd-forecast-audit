"""
First-pass calibration audit: Brier scores, binned calibration with 95% Wilson
intervals, and a calibration plot per horizon.

Usage: python src/calibration.py
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from db import ROOT, connect

FIG_DIR = ROOT / "figures"
BINS = np.linspace(0, 1, 11)


def wilson(k, n, z=1.96):
    if n == 0:
        return np.nan, np.nan
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return centre - half, centre + half


def calibration_table(df):
    df = df.assign(bin=pd.cut(df.price, BINS, include_lowest=True))
    g = df.groupby("bin", observed=True).agg(n=("resolved_yes", "size"),
                                             hits=("resolved_yes", "sum"),
                                             mean_forecast=("price", "mean"))
    g["observed"] = g.hits / g.n
    g[["ci_low", "ci_high"]] = [wilson(k, n) for k, n in zip(g.hits, g.n)]
    g["gap"] = g.observed - g.mean_forecast
    return g


def main():
    con = connect()
    f = con.execute("SELECT * FROM forecasts").df()
    if f.empty:
        raise SystemExit("forecasts table is empty: run build_forecasts.py first")
    FIG_DIR.mkdir(exist_ok=True)

    summary = (f.assign(sq_err=(f.price - f.resolved_yes) ** 2,
                        naive=(f.resolved_yes.mean() - f.resolved_yes) ** 2)
                 .groupby("days")
                 .agg(n=("sq_err", "size"), brier=("sq_err", "mean"), brier_base_rate=("naive", "mean")))
    summary["skill_vs_base_rate"] = 1 - summary.brier / summary.brier_base_rate
    print("\nBrier score by horizon (lower is better; skill > 0 beats always guessing the base rate)")
    print(summary.round(4).to_string())

    horizons = sorted(f.days.unique())
    fig, axes = plt.subplots(1, len(horizons), figsize=(5 * len(horizons), 5), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, d in zip(axes, horizons):
        t = calibration_table(f[f.days == d])
        print(f"\nCalibration, {d} day(s) before resolution")
        print(t[["n", "mean_forecast", "observed", "ci_low", "ci_high", "gap"]].round(3).to_string())
        ax.plot([0, 1], [0, 1], ls="--", lw=1, color="grey", label="perfect calibration")
        ax.errorbar(t.mean_forecast, t.observed,
                    yerr=[(t.observed - t.ci_low).clip(lower=0), (t.ci_high - t.observed).clip(lower=0)],
                    fmt="o-", capsize=3, label="markets (95% CI)")
        ax.set_title(f"{d} day(s) before resolution  (n={int(t.n.sum()):,})")
        ax.set_xlabel("Market-implied probability")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    axes[0].set_ylabel("Share that actually happened")
    axes[0].legend(loc="upper left")
    fig.tight_layout()
    out = FIG_DIR / "calibration_by_horizon.png"
    fig.savefig(out, dpi=150)
    print(f"\nSaved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
