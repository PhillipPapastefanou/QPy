"""Diagnostic plots, mirroring the figures in Pinnington et al. (2020):
Fig. 1 (gradient test), Fig. 6/13 (prior vs. posterior parameter
distributions), and the RMSE-reduction tables (Tables 2/4/5).
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plot_gradient_test(out_path, eta_to_ferr):
    etas = sorted(eta_to_ferr.keys())
    vals = [eta_to_ferr[e] for e in etas]
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.loglog(etas, vals, marker="o")
    ax.set_xlabel(r"$\eta$")
    ax.set_ylabel(r"$|f(\eta) - 1|$")
    ax.set_title("Gradient test of the 4D-En-Var cost function")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_parameter_distributions(out_path, prior_members, posterior_members, param_specs):
    """prior_members/posterior_members are in each parameter's internal
    space (log10 for ParameterSpec.scale=='log', unchanged otherwise) --
    the same space the ensemble is actually drawn/perturbed in -- so a
    log-scaled parameter's histogram is titled accordingly rather than
    silently plotting log10 values on an axis labelled in natural units."""
    n = len(param_specs)
    ncols = min(4, n)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.2 * ncols, 2.6 * nrows))
    axes = np.atleast_1d(axes).ravel()
    for i, spec in enumerate(param_specs):
        ax = axes[i]
        ax.hist(prior_members[:, i], bins=20, color="lightgrey", alpha=0.8, label="prior")
        ax.hist(posterior_members[:, i], bins=20, color="darkorange", alpha=0.6, label="posterior")
        title = spec.name + (" (log10)" if spec.scale == "log" else "")
        ax.set_title(title, fontsize=9)
    for j in range(n, len(axes)):
        axes[j].axis("off")
    axes[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_convergence(config, history):
    if not history:
        return
    df = pd.DataFrame(history)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.5))

    axes[0].plot(df["iteration"], df["cost_prior"], marker="o", label="prior")
    axes[0].plot(df["iteration"], df["cost_posterior"], marker="o", label="posterior")
    axes[0].set_xlabel("iteration")
    axes[0].set_ylabel("4D-En-Var cost J(w)")
    axes[0].legend()

    rmse_cols = [c for c in df.columns if c.startswith("rmse_")]
    for c in rmse_cols:
        axes[1].plot(df["iteration"], df[c], marker="o", label=c.replace("rmse_", ""))
    axes[1].set_xlabel("iteration")
    axes[1].set_ylabel("RMSE")
    axes[1].legend(fontsize=7)

    fig.tight_layout()
    fig.savefig(os.path.join(config.output_root, "convergence.png"), dpi=150)
    plt.close(fig)


def plot_iteration(config, iteration, prior_members, x_analysis, metric_table):
    """Per-iteration RMSE-by-member scatter, useful for sanity-checking that
    the ensemble actually brackets a good solution."""
    if metric_table.empty:
        return
    out_dir = os.path.join(config.output_root, f"iter_{iteration:02d}")
    os.makedirs(out_dir, exist_ok=True)

    metrics = metric_table["metric"].unique()
    fig, axes = plt.subplots(1, len(metrics), figsize=(3.5 * len(metrics), 3), squeeze=False)
    for ax, m in zip(axes[0], metrics):
        sub = metric_table[metric_table["metric"] == m]
        ax.scatter(sub["member"], sub["rmse"], s=12)
        ax.set_title(m, fontsize=9)
        ax.set_xlabel("ensemble member")
        ax.set_ylabel("RMSE")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "rmse_by_member.png"), dpi=150)
    plt.close(fig)
