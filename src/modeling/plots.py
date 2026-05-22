import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless backend; no DISPLAY needed
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)


def plot_per_class(
    per_class: dict[str, dict[str, float]],
    output_path: Path,
    title: str = "Per-class metrics",
) -> None:
    """Grouped bar chart of P / R / F1 per entity class.

    ``per_class`` is the seqeval ``classification_report(output_dict=True)`` shape,
    e.g. ``{"CHARACTER": {"precision": ..., "recall": ..., "f1-score": ..., "support": ...}, ...}``.
    Synthetic seqeval rows like ``"micro avg"`` are filtered out by the caller.
    """
    classes = sorted(per_class.keys())
    precision = [per_class[c].get("precision", 0.0) for c in classes]
    recall = [per_class[c].get("recall", 0.0) for c in classes]
    f1 = [per_class[c].get("f1-score", 0.0) for c in classes]

    x = np.arange(len(classes))
    width = 0.27

    fig, ax = plt.subplots(figsize=(max(6, len(classes) * 1.2), 5))
    ax.bar(x - width, precision, width, label="Precision")
    ax.bar(x, recall, width, label="Recall")
    ax.bar(x + width, f1, width, label="F1")

    ax.set_xticks(x)
    ax.set_xticklabels(classes, rotation=30, ha="right")
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Score")
    ax.set_title(title)
    ax.legend(loc="lower right")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    logger.info(f"Wrote per-class plot to {output_path}")


def plot_confusion(
    matrix: np.ndarray,
    labels: list[str],
    output_path: Path,
    title: str = "Entity-level confusion matrix",
) -> None:
    """Heatmap of an entity-level confusion matrix.

    ``matrix[i, j]`` = number of entities with true label ``labels[i]`` predicted as ``labels[j]``.
    ``labels`` should include sentinel buckets like ``"MISS"`` (gold span without a matching pred)
    and ``"SPURIOUS"`` (pred span without a matching gold).
    """
    fig, ax = plt.subplots(
        figsize=(max(6, len(labels) * 0.7), max(5, len(labels) * 0.7))
    )
    im = ax.imshow(matrix, cmap="Blues", aspect="auto")
    fig.colorbar(im, ax=ax)

    ax.set_xticks(np.arange(len(labels)))
    ax.set_yticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Gold")
    ax.set_title(title)

    threshold = matrix.max() / 2.0 if matrix.size else 0.0
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = int(matrix[i, j])
            if value:
                ax.text(
                    j,
                    i,
                    str(value),
                    ha="center",
                    va="center",
                    color="white" if value > threshold else "black",
                    fontsize=9,
                )

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    logger.info(f"Wrote confusion plot to {output_path}")


def plot_learning_curves_aggregate(
    curves: dict[str, list[dict]],
    output_path: Path,
    title: str = "Learning curves across pipelines",
) -> None:
    """Two side-by-side subplots: dev_f1 vs fraction (left) and train_loss_avg vs fraction (right).

    ``curves`` maps pipeline_name -> list of {"fraction", "train_loss_avg", "dev_f1"} dicts.
    Pipelines containing "from_base" get dashed lines; the rest get solid lines, so the
    EWT-vs-base ablation reads at a glance.
    """
    fig, (ax_f1, ax_loss) = plt.subplots(1, 2, figsize=(13, 5))

    for name in sorted(curves.keys()):
        points = sorted(curves[name], key=lambda p: p["fraction"])
        if not points:
            logger.warning(
                f"Pipeline '{name}' has no learning-curve points; skipping in aggregate plot"
            )
            continue
        xs = [p["fraction"] for p in points]
        f1s = [p["dev_f1"] for p in points]
        losses = [p["train_loss_avg"] for p in points]
        linestyle = "--" if "from_base" in name else "-"
        ax_f1.plot(xs, f1s, marker="o", linestyle=linestyle, label=name)
        ax_loss.plot(xs, losses, marker="o", linestyle=linestyle, label=name)

    for ax, ylabel, subtitle in (
        (ax_f1, "Dev span F1", "Dev F1 vs training progress"),
        (ax_loss, "Train loss (running avg)", "Train loss vs training progress"),
    ):
        ax.set_xlabel("Fraction of training")
        ax.set_ylabel(ylabel)
        ax.set_title(subtitle)
        ax.grid(linestyle="--", alpha=0.4)

    ax_f1.set_ylim(0.0, 1.0)
    handles, labels = ax_f1.get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=min(3, len(labels)),
        bbox_to_anchor=(0.5, -0.02),
    )
    fig.suptitle(title)
    fig.tight_layout(rect=(0, 0.05, 1, 0.97))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Wrote aggregate learning-curves plot to {output_path}")
