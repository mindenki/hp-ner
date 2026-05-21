"""Run GPT-4o NER on a gold IOB2 file and write predictions back as IOB2.

Exposes a single high-level entry point, ``gpt4o_reference_entrypoint(input_path, output_path)``,
which is invoked from ``scripts/train_and_evaluate.py``'s ``gpt4o_reference`` step.
"""
import asyncio
import json
import logging
import os
from pathlib import Path

import openai
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from llm_reference.prompt import ENTITY_SCHEMA, SYSTEM_PROMPT
from src.common.iob2 import Sentence, read_iob2, write_iob2

logger = logging.getLogger(__name__)

OPENAI_MODEL = "gpt-4o"
MAX_CONCURRENT_REQUESTS = 8


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, openai.RateLimitError):
        return True
    if isinstance(exc, openai.APIStatusError) and exc.status_code >= 500:
        return True
    return False


def _token_index_spans_to_iob2(n_tokens: int, spans: list[dict]) -> list[str]:
    """Project GPT-4o's token-index spans into IOB2 tags.

    GPT-4o returns ``{"start": int, "end": int, "label": str}`` where the offsets
    are **token indices** (not char offsets). Distinct from
    ``src/common/spans.py``'s span helpers, which work in character space.
    """
    tags = ["O"] * n_tokens
    for span in sorted(spans, key=lambda s: s["start"]):
        label = span["label"]
        start, end = span["start"], span["end"]
        tags[start] = f"B-{label}"
        for i in range(start + 1, end):
            tags[i] = f"I-{label}"
    return tags


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


async def _predict_all(token_lists: list[list[str]]) -> list[list[str]]:
    client = openai.AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    tasks = [_predict_one(client, semaphore, sent) for sent in token_lists]
    span_lists = await asyncio.gather(*tasks, return_exceptions=True)
    predictions: list[list[str]] = []
    for idx, (sent, spans) in enumerate(zip(token_lists, span_lists)):
        if isinstance(spans, BaseException):
            logger.error("sentence %d failed (%s); writing O-only tags", idx, spans)
            predictions.append(["O"] * len(sent))
        else:
            predictions.append(_token_index_spans_to_iob2(len(sent), spans))
    return predictions


def gpt4o_reference_entrypoint(input_path: Path, output_path: Path) -> None:
    """Predict NER tags for every sentence in ``input_path`` and write IOB2 to ``output_path``.

    Reuses ``src.common.iob2.read_iob2`` / ``write_iob2`` so the file format matches
    the rest of the pipeline.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY must be set to run gpt4o_reference")

    sentences = read_iob2(input_path, validate=False)
    token_lists = [s.words for s in sentences]
    logger.info("GPT-4o: predicting on %d sentences from %s", len(sentences), input_path)
    predicted_tags = asyncio.run(_predict_all(token_lists))
    predicted_sentences = [
        Sentence(words=tokens, labels=tags)
        for tokens, tags in zip(token_lists, predicted_tags)
    ]
    write_iob2(predicted_sentences, output_path, ewt_columns=True)
    logger.info("GPT-4o: wrote predictions to %s", output_path)
