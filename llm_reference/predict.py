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

from llm_reference.prompt import ENTITY_SCHEMA, IOB_TAGS, SYSTEM_PROMPT
from src.common.iob2 import Sentence, read_iob2, write_iob2

logger = logging.getLogger(__name__)

OPENAI_MODEL = "gpt-4o"
MAX_CONCURRENT_REQUESTS = 2


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, openai.RateLimitError):
        return True
    if isinstance(exc, openai.APIStatusError) and exc.status_code >= 500:
        return True
    return False


def _validate_prediction(tokens: list[str], response_data: dict) -> list[str]:
    """Validate the model response and ensure exact token-by-token alignment."""
    if not isinstance(response_data, dict):
        raise ValueError("Invalid response: expected JSON object")

    token_labels = response_data.get("token_labels")
    token_count = response_data.get("token_count")

    if not isinstance(token_count, int):
        raise ValueError("Invalid token_count: expected integer")
    if token_count != len(tokens):
        raise ValueError(
            f"Invalid token_count: {token_count} does not match tokens length {len(tokens)}"
        )

    if not isinstance(token_labels, list):
        raise ValueError("Invalid token_labels: expected list")
    if len(token_labels) != len(tokens):
        raise ValueError(
            f"Invalid token_labels length: {len(token_labels)} does not match tokens length {len(tokens)}"
        )

    labels: list[str] = []
    for idx, item in enumerate(token_labels):
        if not isinstance(item, dict):
            raise ValueError("Invalid token_labels: each item must be an object")
        token = item.get("token")
        label = item.get("label")

        if token != tokens[idx]:
            raise ValueError(
                f"Token mismatch at position {idx}: expected {tokens[idx]!r}, got {token!r}"
            )
        if not isinstance(label, str):
            raise ValueError("Invalid label: expected string")
        if label not in IOB_TAGS:
            raise ValueError("Invalid labels: all labels must be valid IOB2 tags")

        labels.append(label)

    return labels


@retry(
    wait=wait_exponential(min=2, max=60),
    stop=stop_after_attempt(8),
    retry=retry_if_exception(_is_retryable),
)
async def _predict_one(
    client: openai.AsyncOpenAI,
    semaphore: asyncio.Semaphore,
    sentence_idx: int,
    tokens: list[str],
) -> list[str]:
    async with semaphore:
        for attempt in range(3):
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps({"tokens": tokens})},
                ],
                temperature=0,
                seed=42 + attempt,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "ner", "schema": ENTITY_SCHEMA, "strict": True},
                },
            )
            content = response.choices[0].message.content
            try:
                response_data = json.loads(content)
                return _validate_prediction(tokens, response_data)
            except (json.JSONDecodeError, ValueError) as exc:
                if attempt == 2:
                    raise
                logger.warning(
                    "sentence %d attempt %d invalid response (%s); retrying",
                    sentence_idx,
                    attempt + 1,
                    exc,
                )
                continue


async def _predict_all(token_lists: list[list[str]]) -> list[list[str]]:
    client = openai.AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    tasks = [
        _predict_one(client, semaphore, idx, sent)
        for idx, sent in enumerate(token_lists)
    ]
    label_lists = await asyncio.gather(*tasks, return_exceptions=True)
    predictions: list[list[str]] = []
    for idx, (sent, labels) in enumerate(zip(token_lists, label_lists)):
        if isinstance(labels, BaseException):
            logger.error("sentence %d failed (%s); writing O-only tags", idx, labels)
            predictions.append(["O"] * len(sent))
        else:
            predictions.append(labels)
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

