"""Run GPT-4o NER on a gold IOB2 file and write predictions back as IOB2.

Usage:
    OPENAI_API_KEY=... uv run gpt4o-predict \
        --input data/selected/gold/gold.iob2 \
        --output outputs/llm/predictions.iob2
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path

import openai
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from llm_reference.prompt import ENTITY_SCHEMA, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

OPENAI_MODEL = "gpt-4o"
MAX_CONCURRENT_REQUESTS = 8


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, openai.RateLimitError):
        return True
    if isinstance(exc, openai.APIStatusError) and exc.status_code >= 500:
        return True
    return False


def read_tokens(path: Path) -> list[list[str]]:
    """Pull the token column out of an IOB2 file.

    Handles both the raw 2-col `token\\tlabel` gold file and the 5-col EWT-style
    `idx\\ttoken\\tlabel\\t-\\t-` splits emitted by `split-gold`.
    """
    sentences: list[list[str]] = []
    current: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            continue
        if line == "":
            if current:
                sentences.append(current)
                current = []
            continue
        parts = line.split("\t")
        current.append(parts[1] if len(parts) >= 3 else parts[0])
    if current:
        sentences.append(current)
    return sentences


def spans_to_iob2(n_tokens: int, spans: list[dict]) -> list[str]:
    """Project schema-valid spans onto a list of BIO tags."""
    tags = ["O"] * n_tokens
    for span in sorted(spans, key=lambda s: s["start"]):
        label = span["label"]
        start, end = span["start"], span["end"]
        tags[start] = f"B-{label}"
        for i in range(start + 1, end):
            tags[i] = f"I-{label}"
    return tags


def write_iob2(path: Path, sentences: list[list[str]], tags: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for tokens, sent_tags in zip(sentences, tags):
        for i, (word, tag) in enumerate(zip(tokens, sent_tags), start=1):
            lines.append(f"{i}\t{word}\t{tag}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


@retry(
    wait=wait_exponential(min=1, max=10),
    stop=stop_after_attempt(5),
    retry=retry_if_exception(_is_retryable),
)
async def _predict_one(
    client: openai.AsyncOpenAI,
    semaphore: asyncio.Semaphore,
    tokens: list[str],
) -> list[dict]:
    async with semaphore:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({"tokens": tokens})},
            ],
            temperature=0,
            seed=42,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "ner", "schema": ENTITY_SCHEMA, "strict": True},
            },
        )
    return json.loads(response.choices[0].message.content)["labels"]


async def _run(sentences: list[list[str]]) -> list[list[str]]:
    client = openai.AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    tasks = [_predict_one(client, semaphore, sent) for sent in sentences]
    span_lists = await asyncio.gather(*tasks, return_exceptions=True)

    predictions: list[list[str]] = []
    for idx, (sent, spans) in enumerate(zip(sentences, span_lists)):
        if isinstance(spans, BaseException):
            logger.error("sentence %d failed (%s); writing O-only tags", idx, spans)
            predictions.append(["O"] * len(sent))
        else:
            predictions.append(spans_to_iob2(len(sent), spans))
    return predictions


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    parser = argparse.ArgumentParser(description="GPT-4o NER zero-shot reference.")
    parser.add_argument("--input", required=True, type=Path, help="Gold IOB2 file (2-col or 5-col)")
    parser.add_argument("--output", required=True, type=Path, help="Where to write predictions (IOB2)")
    parser.add_argument("--limit", type=int, default=None, help="Optional cap for smoke tests")
    args = parser.parse_args()

    sentences = read_tokens(args.input)
    if args.limit is not None:
        sentences = sentences[: args.limit]
    logger.info("Predicting on %d sentences from %s", len(sentences), args.input)

    predictions = asyncio.run(_run(sentences))
    write_iob2(args.output, sentences, predictions)
    logger.info("Wrote predictions to %s", args.output)


if __name__ == "__main__":
    main()
