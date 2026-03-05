from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List


def default_reason(book: Dict[str, Any], similar_book: Dict[str, Any] | None) -> str:
    if similar_book:
        return (
            f"Because they liked {similar_book['title']}, which shares {book['genre']} themes"
        )
    return f"Popular right now among students who enjoy {book['genre']} stories"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def next_id(prefix: str, existing_ids: Iterable[str], width: int = 4) -> str:
    max_num = 0
    for item in existing_ids:
        if not item.startswith(prefix):
            continue
        suffix = item[len(prefix) :]
        if suffix.isdigit():
            max_num = max(max_num, int(suffix))
    return f"{prefix}{max_num + 1:0{width}d}"


def split_list(value: str | None) -> List[str]:
    if not value:
        return []
    separators = [";", ","]
    working = value
    for sep in separators:
        working = working.replace(sep, "|")
    return [item.strip() for item in working.split("|") if item.strip()]


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\s-]", " ", text.lower()).strip()


def extract_filters(
    message: str,
    onboarding_profile: Dict[str, Any] | None,
    book_genres: List[str],
) -> Dict[str, Any]:
    text = normalize(message)
    filters: Dict[str, Any] = {}

    if "available" in text or "available now" in text or "in stock" in text:
        filters["availability"] = "Available"
    if "on hold" in text:
        filters["availability"] = "On Hold"
    if "checked out" in text:
        filters["availability"] = "Checked Out"

    if "spanish" in text:
        filters["language"] = "Spanish"
    if "english" in text:
        filters["language"] = "English"

    level_match = re.search(r"(\d)\s*-\s*(\d)", text)
    if level_match:
        filters["reading_level"] = f"{level_match.group(1)}-{level_match.group(2)}"

    genres = [genre for genre in book_genres if genre.lower() in text]
    if genres:
        filters["genres"] = genres

    if onboarding_profile:
        preferred = split_list(onboarding_profile.get("preferred_genres"))
        if preferred and "genres" not in filters:
            preferred_lower = {item.lower() for item in preferred}
            matched = [genre for genre in book_genres if genre.lower() in preferred_lower]
            if matched:
                filters["genres"] = matched
        if onboarding_profile.get("reading_level") and "reading_level" not in filters:
            filters["reading_level"] = onboarding_profile["reading_level"]

    return filters


def format_concierge_reply(
    message: str,
    recommendations: List[Dict[str, Any]],
    use_llm: bool,
) -> str:
    if not recommendations:
        return "I couldn't find matches for that request yet. Try a genre, interest, or reading level."
    if use_llm:
        return ""

    lead = "Here are a few librarian-ready picks"
    if "available" in normalize(message):
        lead += " that are available now"
    lead += ": "
    titles = ", ".join([rec["book"]["title"] for rec in recommendations[:3]])
    return f"{lead}{titles}."


def build_continuation_recommendations(
    continuation: Dict[str, Any] | None,
    *,
    limit: int = 6,
) -> List[Dict[str, Any]]:
    if not continuation:
        return []
    results = continuation.get("results") or []
    if not results:
        return []

    mode = continuation.get("mode")
    series = continuation.get("series")
    author = continuation.get("author")
    target = continuation.get("target_book")
    if mode == "series" and series:
        reason = f"Another title in the {series} series."
    elif author:
        reason = f"Another book by {author}."
    else:
        reason = "Related title from the catalog."

    recommendations: List[Dict[str, Any]] = []
    for book in results[:limit]:
        recommendations.append(
            {
                "book": book,
                "score": 0.0,
                "similar_to": target,
                "reason": reason,
            }
        )
    return recommendations


def parse_token_usage(usage: Any | None) -> Dict[str, int]:
    if not usage:
        return {}
    if isinstance(usage, dict):
        data = usage
    elif hasattr(usage, "model_dump"):
        data = usage.model_dump()
    else:
        data = {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
        }

    input_tokens = data.get("input_tokens")
    if input_tokens is None:
        input_tokens = data.get("prompt_tokens")
    output_tokens = data.get("output_tokens")
    if output_tokens is None:
        output_tokens = data.get("completion_tokens")
    total_tokens = data.get("total_tokens")
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    usage_out: Dict[str, int] = {}
    if input_tokens is not None:
        usage_out["input_tokens"] = int(input_tokens)
    if output_tokens is not None:
        usage_out["output_tokens"] = int(output_tokens)
    if total_tokens is not None:
        usage_out["total_tokens"] = int(total_tokens)
    return usage_out


def estimate_token_cost(
    usage: Dict[str, int],
    *,
    model: str | None = None,
) -> Dict[str, float]:
    if not usage:
        return {}

    default_input = float(os.getenv("OPENAI_COST_INPUT_PER_1K", "0.0005"))
    default_output = float(os.getenv("OPENAI_COST_OUTPUT_PER_1K", "0.0015"))
    input_rate = default_input
    output_rate = default_output

    if model:
        normalized = model.upper().replace("-", "_").replace(".", "_")
        model_input = os.getenv(f"OPENAI_COST_INPUT_PER_1K_{normalized}")
        model_output = os.getenv(f"OPENAI_COST_OUTPUT_PER_1K_{normalized}")
        if model_input:
            input_rate = float(model_input)
        if model_output:
            output_rate = float(model_output)

    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    input_cost = (input_tokens / 1000.0) * input_rate
    output_cost = (output_tokens / 1000.0) * output_rate
    total_cost = input_cost + output_cost

    return {
        "input_usd": round(input_cost, 6),
        "output_usd": round(output_cost, 6),
        "total_usd": round(total_cost, 6),
        "input_per_1k": input_rate,
        "output_per_1k": output_rate,
    }
