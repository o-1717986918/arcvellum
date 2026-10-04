"""Work-level content-word TF-IDF for topic diagnostics.

This is an explicitly specified TF-IDF variant, not a claim to duplicate
unpublished preprocessing choices in a reference paper.
"""

from __future__ import annotations

from collections import Counter
from math import log
from typing import Any

import jieba
import jieba.posseg as pseg

from .corpus import Corpus, HAN


def content_keywords(corpus: Corpus, limit: int = 15) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("keyword limit must be positive")
    works: dict[str, list[str]] = {}
    for source in corpus.sources:
        if source.split == "train":
            works.setdefault(source.work_id, []).append(source.text)
    counts: dict[str, Counter[str]] = {}
    document_frequency: Counter[str] = Counter()
    for work_id, chunks in sorted(works.items()):
        tokens = [token.word for token in pseg.cut("\n".join(chunks), HMM=False)
                  if token.flag and token.flag[0] in {"n", "v", "a"}
                  and len(token.word) >= 2
                  and all(HAN.fullmatch(char) for char in token.word)]
        counts[work_id] = Counter(tokens)
        document_frequency.update(counts[work_id].keys())
    document_count = len(counts)
    rows = []
    for work_id, frequencies in sorted(counts.items()):
        token_count = sum(frequencies.values())
        scored = []
        for term, frequency in frequencies.items():
            tf = frequency / token_count if token_count else 0.0
            idf = log((document_count + 1) / (document_frequency[term] + 1)) + 1
            scored.append((term, frequency, round(tf * idf, 8)))
        scored.sort(key=lambda item: (-item[2], -item[1], item[0]))
        rows.append({"work_id": work_id, "content_token_count": token_count,
                     "unique_content_terms": len(frequencies),
                     "keywords": [{"term": term, "count": frequency, "tf_idf": score}
                                  for term, frequency, score in scored[:limit]]})
    return {
        "schema": "content-keyword-diagnostics/v1",
        "training_work_count": document_count,
        "tokenizer": {"name": "jieba.posseg", "version": jieba.__version__, "HMM": False},
        "definition": "train works only; noun/verb/adjective Han tokens >=2 characters; "
                      "tf=count/selected-token-count; idf=ln((N+1)/(df+1))+1; "
                      "no vocabulary or IDF fitted on holdout",
        "works": rows,
        "warning": "关键词主要反映题材和人物；不作为提示词风格目标或作者归属证据。",
    }
