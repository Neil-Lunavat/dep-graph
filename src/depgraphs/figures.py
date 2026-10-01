"""Draw the paper's figures from the result files.

Like the table rows, the figures are generated, never drawn by hand: each reads the CSV its
numbers come from and writes paper/fig_*.pdf, which the paper includes.

  fig_curves    coverage against lines read, per key           results/study2/curves_mean.csv
  fig_worth     what the issue adds, and the redaction arms    results/study2/dense_tests.csv
  fig_distance  key files by hop distance from the seed        results/study2/distance_profile.csv

The paper is set in Linux Libertine. If that font is not installed, point DEPGRAPHS_FONTS at
a directory holding its .otf files (a TeX distribution has them); otherwise another serif is
used and only the lettering differs.

Usage:  python -m depgraphs.figures
"""
from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager

from depgraphs.lexfeat import ROOT
from depgraphs.study2 import OUT

PAPER = ROOT / "paper"
WIDTH = 5.48                      # text width of acmsmall, in inches

# categorical slots, checked for colour-vision separation; identity never rests on colour
# alone (markers, line styles and labels repeat it)
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GREY, RULE = "#0b0b0b", "#52514e", "#8a8984", "#dddcd7"
HOPS = {"1": "#104281", "2": "#2a78d6", "3+": "#86b6ef", "unreachable": "#c9c8c3"}

NAME = {"oracle": "oracle", "random": "random order",
        "rrf_pprpl_issue_path": "the fusion", "ppr_und_pl": "length-aware walk",
        "path_issue": "path matching"}
KEY = {"co_edited": "Co-edited key", "symbol": "Symbol key"}


def setup():
    fonts = os.environ.get("DEPGRAPHS_FONTS")
    if fonts:
        for p in Path(fonts).glob("LinLibertine_*.otf"):
            font_manager.fontManager.addfont(str(p))
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Linux Libertine O", "Linux Libertine", "Palatino Linotype",
                       "DejaVu Serif"],
        "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8, "legend.fontsize": 8,
        "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
        "axes.edgecolor": GREY, "axes.linewidth": 0.6, "axes.labelcolor": MUTED,
        "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": RULE, "grid.linewidth": 0.5, "axes.axisbelow": True,
        "lines.linewidth": 1.4, "lines.markersize": 4.2, "legend.frameon": False,
        "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
    })


def save(fig, stem: str):
    p = PAPER / ("fig_%s.pdf" % stem)
    # no creation date, so an unchanged figure is an unchanged file
    fig.savefig(p, metadata={"CreationDate": None, "Creator": None, "Producer": None})
    plt.close(fig)
    print("wrote", p.name)


def curves_figure():
    """Mean coverage of the key against lines read, over the scored tasks of each key."""
    cur = pd.read_csv(OUT / "curves_mean.csv")
    style = [("oracle", GREY, "--", None), ("rrf_pprpl_issue_path", BLUE, "-", "o"),
             ("ppr_und_pl", ORANGE, "-", "s"), ("path_issue", AQUA, "-", "^"),
             ("random", GREY, ":", None)]
    fig, axes = plt.subplots(1, 2, figsize=(WIDTH, 2.3), sharey=True)
    for ax, src in zip(axes, ("co_edited", "symbol")):
        g = cur[cur.source == src]
        for meth, colour, ls, marker in style:
            d = g[g.method == meth].sort_values("budget")
            ax.plot(d.budget, d.coverage, color=colour, ls=ls, marker=marker,
                    label=NAME[meth], markeredgecolor="white", markeredgewidth=0.6)
        ax.set_xscale("log", base=2)
        ax.set_xticks([250, 1000, 4000, 16000])
        ax.set_xticklabels(["250", "1,000", "4,000", "16,000"])
        ax.set_xlabel("lines read (budget)")
        ax.set_title(KEY[src], loc="left", color=INK)
        ax.set_ylim(0, 1)
    axes[0].set_ylabel("share of the key covered")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="upper center", ncol=5,
               bbox_to_anchor=(0.5, 1.08), handlelength=2.2, columnspacing=1.3)
    fig.tight_layout()
    save(fig, "curves")


def worth_figure():
    """The decomposition of Table `tab:decomp`: issue worth by stratum, and the three arms."""
    t = pd.read_csv(OUT / "dense_tests.csv")
    t = t[t.family == "decomposition"]

    def delta(what, stratum, src):
        return float(t[(t.what == what) & (t.stratum == stratum) & (t.source == src)]
                     .iloc[0].delta)

    fusions = [("BM25", "rrf_pprpl_issue_path"), ("dense", "rrf_pprpl_dense_path")]
    groups = [(src, word, meth) for src in ("co_edited", "symbol") for word, meth in fusions]
    fig, ax = plt.subplots(figsize=(WIDTH, 2.45))
    w = 0.34
    for i, (src, word, meth) in enumerate(groups):
        named = delta("issue worth, %s fusion" % word, "explicit", src)
        rest = delta("issue worth, %s fusion" % word, "no_explicit", src)
        ax.bar(i - w / 2 - 0.01, named, w, color=BLUE,
               label="issue names a key file" if i == 0 else None)
        ax.bar(i + w / 2 + 0.01, rest, w, color=GREY,
               label="issue names none" if i == 0 else None)
        ax.text(i - w / 2 - 0.01, named + 0.004, "%+.3f" % named, ha="center", fontsize=7)
        ax.text(i + w / 2 + 0.01, rest + 0.004, "%+.3f" % rest, ha="center", fontsize=7)
        for sfx, arm in (("_rd", "names"), ("_rdp", "paths"), ("_rds", "symbols")):
            a = delta("names cost (%s), %s" % (sfx, meth), "explicit", src)
            for colour, lw in (("white", 1.6), (INK, 0.7)):
                ax.plot([i - w - 0.01, i - 0.01], [a, a], color=colour, lw=lw,
                        solid_capstyle="butt")
            if i == 0:
                ax.text(i - w - 0.04, a, arm, ha="right", va="center", fontsize=6.5,
                        color=MUTED)
    ax.plot([], [], color=INK, lw=0.7, label="part lost under each redaction arm")
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels(["%s fusion\n%s" % (word, KEY[src].lower()) for src, word, _ in groups])
    ax.set_xlim(-0.75, len(groups) - 0.45)
    ax.set_ylim(0, 0.2)
    ax.set_ylabel("AUC the issue adds to the fusion")
    ax.grid(axis="x", visible=False)
    fig.legend(*ax.get_legend_handles_labels(), loc="upper center", ncol=3,
               bbox_to_anchor=(0.5, 1.07), columnspacing=1.4)
    fig.tight_layout()
    save(fig, "worth")


def distance_figure():
    """Key files by undirected hop distance from the seed, per key."""
    d = pd.read_csv(OUT / "distance_profile.csv")
    d["hops"] = d.hops.astype(str)
    label = {"1": "one hop", "2": "two hops", "3+": "three or more",
             "unreachable": "unreachable"}
    fig, ax = plt.subplots(figsize=(WIDTH, 1.45))
    for y, src in enumerate(("symbol", "co_edited")):
        left = 0.0
        for h, colour in HOPS.items():
            v = 100 * float(d[(d.source == src) & (d.hops == h)].share.iloc[0])
            ax.barh(y, v - 0.5, left=left + 0.25, height=0.55, color=colour,
                    label=label[h] if y == 0 else None)
            if v > 6:
                ax.text(left + v / 2, y, "%.1f%%" % v, ha="center", va="center", fontsize=7,
                        color="white" if h in ("1", "2") else INK)
            left += v
    ax.set_yticks([0, 1])
    ax.set_yticklabels([KEY["symbol"].lower(), KEY["co_edited"].lower()])
    ax.tick_params(axis="y", colors=INK)
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.5, 1.5)
    ax.set_xlabel("key files by distance from the seed in the import graph (%)")
    ax.grid(visible=False)
    fig.legend(*ax.get_legend_handles_labels(), loc="upper center", ncol=4,
               bbox_to_anchor=(0.55, 1.12), columnspacing=1.4)
    fig.tight_layout()
    save(fig, "distance")


def main():
    setup()
    curves_figure()
    worth_figure()
    distance_figure()


if __name__ == "__main__":
    main()
