"""Question deduplication using TF-IDF similarity."""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("qbank_v2_worker")


def _normalize_text(text: str) -> str:
    """Strip LaTeX, punctuation, and extra spaces for comparison."""
    text = re.sub(r'\$[^$]+\$', ' MATH ', text)  # Replace LaTeX blocks
    text = re.sub(r'[^\w\s]', ' ', text)           # Strip punctuation
    return re.sub(r'\s+', ' ', text).strip().lower()


def find_duplicates(
    new_questions: list[dict[str, Any]],
    existing_texts: list[str],
    threshold: float = 0.80,
) -> list[int]:
    """
    Return indices of new_questions that are duplicates of existing ones.

    Uses TF-IDF cosine similarity. Falls back gracefully if scikit-learn
    is not installed (returns empty list, i.e. no dedup).

    Args:
        new_questions: List of question dicts with 'question' key.
        existing_texts: List of existing question text strings.
        threshold: Cosine similarity threshold (0.80 = 80% similar).

    Returns:
        List of indices into new_questions that are duplicates.
    """
    if not existing_texts or not new_questions:
        return []

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
    except ImportError:
        logger.warning(
            "scikit-learn not installed — skipping duplicate detection. "
            "Install with: pip install scikit-learn"
        )
        return []

    new_texts = [_normalize_text(q.get("question", "")) for q in new_questions]
    all_texts = [_normalize_text(t) for t in existing_texts] + new_texts

    # Skip if all texts are empty after normalization
    if not any(all_texts):
        return []

    vectorizer = TfidfVectorizer(max_features=5000, stop_words="english")
    try:
        tfidf_matrix = vectorizer.fit_transform(all_texts)
    except ValueError:
        return []

    n_existing = len(existing_texts)
    duplicate_indices: list[int] = []

    for i in range(len(new_texts)):
        new_idx = n_existing + i
        similarities = cosine_similarity(
            tfidf_matrix[new_idx : new_idx + 1],
            tfidf_matrix[:n_existing],
        )
        max_sim = float(np.max(similarities)) if similarities.size > 0 else 0.0
        if max_sim >= threshold:
            duplicate_indices.append(i)
            logger.debug(
                "Duplicate detected (%.2f similarity): '%s'",
                max_sim,
                new_texts[i][:80],
            )

    return duplicate_indices
