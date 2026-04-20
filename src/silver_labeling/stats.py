"""
Tracks and logs coverage and conflict statistics for silver labeling.
"""

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class SilverStats:
    """
    Counts per-label source counts and conflict counts,
    across all sentences
    """

    def __init__(self):
        self.label_counts = defaultdict(lambda: {"dict": 0, "bert": 0, "both":0, "O": 0})
        
        self.conflict_counts = defaultdict(int)
        self.total_sentences = 0

        # how many sentences have exactly N entities: {0: 412, 1: 823, ...}
        self.entity_count_dist: dict[int, int] = defaultdict(int)

        # how many sentences contain at least one mention of each label
        # e.g. {"CHARACTER": 4231, "SPELL": 1823, ...}
        self.label_sentence_counts: dict[str, int] = defaultdict(int)

        # co-occurrence: how many sentences contain both label A and label B
        # e.g. {frozenset({"CHARACTER","SPELL"}): 412}
        self.label_cooccurrence: dict[frozenset, int] = defaultdict(int)

    def update(
        self,
        merged_tags: list[str],
        sources: list[str],
        entity_count: int,
        entity_types: list[str],
        conflict_counts_batch: dict[str, int],
    ) -> None:

        self.total_sentences += 1
        self.entity_count_dist[entity_count] += 1

        # per-label token source counts
        for tag, source in zip(merged_tags, sources):
            if tag != "O":
                label = tag.split("-")[1]  # e.g. B-CHAR -> CHAR
                self.label_counts[label][source] += 1
        # per-label sentence presence
        for label in entity_types:
            self.label_sentence_counts[label] += 1

        # co-occurrence (all pairs of labels present in this sentence)
        if len(entity_types) >= 2:
            types_set = set(entity_types)
            for i, l1 in enumerate(entity_types):
                for l2 in entity_types[i + 1 :]:
                    self.label_cooccurrence[frozenset({l1, l2})] += (
                        1  # frozenset to ensure order doesn't matter, so (CHAR, SPELL) and (SPELL, CHAR) are counted together
                    )

        for k, v in conflict_counts_batch.items():
            self.conflict_counts[k] += v

    def log_summary(self) -> None:
        total = self.total_sentences
        logger.info("=" * 60)
        logger.info("SILVER LABELING SUMMARY")
        logger.info("=" * 60)
        logger.info("Total sentences: %d", total)

        # ── Entity count distribution ───────────────────────────────────────
        logger.info("\nEntity count distribution:")
        max_n = max(self.entity_count_dist.keys())
        for n in range(0, min(max_n + 1, 11)):
            count = self.entity_count_dist.get(n, 0)
            bar = "█" * (count * 40 // total) if total else ""
            logger.info(
                f"{n:2d} entities: {count:5d} sentences {bar} percentage: {count / total:.1%}"
            )

        above_10 = sum(count for n, count in self.entity_count_dist.items() if n > 10)
        if above_10:
            logger.info(
                f">10 entities: {above_10} sentences percentage: {above_10 / total:.1%}"
            )

        # ── Per-label sentence presence ───────────────────────────────
        logger.info("\nPer-label sentence presence:")
        for label in sorted(self.label_sentence_counts.keys()):
            count = self.label_sentence_counts[label]
            logger.info(f"{label}: {count} sentences percentage: {count / total:.1%}")

        # ── Per-label token coverage ───────────────────────────────────────
        logger.info("\nPer-label token coverage:")
        total_tagged = sum(
            sum(source_counts.values())
            for source_counts in self.label_counts.values()
        )
        for label in sorted(self.label_counts):
            d = self.label_counts[label].get("dict", 0)
            b = self.label_counts[label].get("bert", 0)
            both = self.label_counts[label].get("both", 0)
            label_total = b + d + both
            logger.info(f"{label}: dict {d} tokens ({d/label_total:.1%}), bert {b} tokens ({b/label_total:.1%}), both {both} tokens ({both/label_total:.1%}), total {total_tagged} tokens")
            
        # ── Co-occurrence ────────────────────────────────────────────
        logger.info("\nLabel co-occurrence:")
        sorted_cooc = sorted(self.label_cooccurrence.items(), key=lambda x: -x[1])

        for pair, count in sorted_cooc[:20]:  # Top 20 co-occurring pairs
            l1, l2 = sorted(pair)
            logger.info(
                f"{l1} & {l2}: {count} sentences percentage: {count / total:.1%}"
            )

        # ── Conflict counts ─────────────────────────────────────
        logger.info("\nConflict counts (BERT label -> Dict label):")
        if self.conflict_counts:
            for conflict, count in sorted(
                self.conflict_counts.items(), key=lambda x: -x[1]
            ):
                logger.info(
                    f"{conflict}: {count} tokens percentage: {count / total:.1%}"
                )
        else:
            logger.info("No conflicts between BERT and Dict labels.")

        total_conflicts = sum(self.conflict_counts.values())
        if total_tagged:
            logger.info(
                f"\nTotal conflicts: {total_conflicts} tokens percentage of all tagged tokens: {total_conflicts / total_tagged:.1%}"
            )

        logger.info("=" * 60)
