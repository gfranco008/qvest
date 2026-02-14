CHAT_SYSTEM_PROMPT = (
    "You are a helpful librarian assistant. Provide concise, friendly "
    "recommendations and talking points for students and librarians. "
    "Use only the information provided in the system context and chat history. "
    "Do not fabricate titles, reading history, availability, holds, or profile details. "
    "If needed information is missing, say so and ask a focused follow-up question "
    "(e.g., request a student_id or a specific title). "
    "Protect student privacy and avoid sensitive inferences; only reference data that is explicitly provided. "
    "Never claim you saved, placed, or updated anything unless the context explicitly confirms it. "
    "If a hold request result is ambiguous, ask a clarifying question. "
    "If reading history, snapshot, or onboarding summary is provided, summarize it briefly. "
    "If recommendations are provided, only mention those titles. "
    "If asked outside library support, politely redirect to what you can help with."
)

CONCIERGE_SYSTEM_PROMPT = (
    "You are a librarian concierge. Respond in 2-3 short sentences. "
    "Do not use bullet points. Mention availability if relevant. "
    "Use only the information provided in the system context. "
    "Do not fabricate titles, reading history, availability, holds, or profile details. "
    "If needed information is missing, ask a focused question. "
    "Never claim you saved, placed, or updated anything unless the context explicitly confirms it. "
    "If a student_id is not provided, ask for it before saving feedback. "
    "If an onboarding profile exists, ask whether to save changes; otherwise confirm it was saved."
)

CONCIERGE_USER_TEMPLATE = (
    "Request: {request}"
)


def _format_profile_summary(profile: dict, *, fallback: str) -> str:
    parts = []
    if profile.get("preferred_genres"):
        parts.append(f"Genres: {profile['preferred_genres']}")
    if profile.get("reading_level"):
        parts.append(f"Level: {profile['reading_level']}")
    if profile.get("interests"):
        parts.append(f"Interests: {profile['interests']}")
    return " · ".join(parts) if parts else fallback


def build_context_note(context: dict) -> str:
    lines = [f"Known student_id: {context.get('student_id') or 'unknown'}."]

    if context.get("needs_student_id"):
        lines.append(
            "Student_id is missing. Ask for it before recommending or updating records."
        )

    filters = context.get("filters") or {}
    if filters:
        filter_parts = []
        for key, value in filters.items():
            if isinstance(value, list):
                display = ", ".join(value)
            else:
                display = str(value)
            filter_parts.append(f"{key}={display}")
        lines.append("Filters applied: " + "; ".join(filter_parts) + ".")

    available_books = context.get("available_books") or []
    if available_books:
        available_lines = [
            f"{book['title']} by {book['author']} ({book['genre']}, level {book['reading_level']})"
            for book in available_books
        ]
        lines.append(
            "Available titles matching request:\n" + "\n".join(available_lines)
        )

    reading_history = context.get("reading_history") or []
    if reading_history:
        history_lines = [
            f"{item['book']['title']} by {item['book']['author']} ({item['last_checkout'] or 'date unknown'})"
            for item in reading_history
        ]
        lines.append("Reading history:\n" + "\n".join(history_lines))

    hold_result = context.get("hold_result")
    if hold_result:
        status = hold_result.get("status", "unknown")
        message = hold_result.get("message", "")
        if status == "ambiguous":
            matches = hold_result.get("matches", [])
            match_lines = [
                f"{item.get('title')} by {item.get('author')} (ID {item.get('book_id')})"
                for item in matches
            ]
            lines.append(
                "Hold request needs clarification. Matches:\n" + "\n".join(match_lines)
            )
        else:
            lines.append(f"Hold request status: {status}. {message}")

    continuation_recs = context.get("continuation_recs") or []
    continuation_note = context.get("continuation_note")
    if continuation_recs:
        continuation_lines = [
            f"{rec['book']['title']} by {rec['book']['author']} ({rec['book'].get('genre', 'n/a')})"
            for rec in continuation_recs
        ]
        lines.append(
            "Series/author continuation matches:\n" + "\n".join(continuation_lines)
        )
    elif continuation_note:
        lines.append(continuation_note)

    snapshot = context.get("snapshot")
    if snapshot:
        stats = snapshot.get("stats", {})
        top_genres = ", ".join([item["genre"] for item in stats.get("top_genres", [])])
        top_authors = ", ".join([item["author"] for item in stats.get("top_authors", [])])
        recent_titles = ", ".join([item["title"] for item in stats.get("recent_books", [])])
        snapshot_line = (
            f"Student snapshot: total loans {stats.get('total_loans', 0)}, "
            f"unique books {stats.get('unique_books', 0)}, "
            f"last checkout {stats.get('last_checkout') or 'n/a'}."
        )
        if top_genres:
            snapshot_line += f" Top genres: {top_genres}."
        if top_authors:
            snapshot_line += f" Top authors: {top_authors}."
        if recent_titles:
            snapshot_line += f" Recent reads: {recent_titles}."
        lines.append(snapshot_line)

    onboarding_profile = context.get("onboarding_profile")
    existing_profile = context.get("existing_profile")
    onboarding_saved = context.get("onboarding_saved")
    onboarding_pending = context.get("onboarding_pending")
    if onboarding_profile:
        summary = _format_profile_summary(
            onboarding_profile,
            fallback="Profile generated from history.",
        )
        decision_note = ""
        if onboarding_saved:
            decision_note = " Saved."
        elif onboarding_pending:
            decision_note = " A profile already exists; ask to save changes."
        line = f"Onboarding profile summary: {summary}"
        lines.append(line + decision_note)
    elif existing_profile:
        summary = _format_profile_summary(existing_profile, fallback="Profile saved.")
        lines.append(f"Existing onboarding profile: {summary}")
    elif context.get("student_id"):
        lines.append("No saved onboarding profile was found for this student.")

    recommendations = context.get("recommendations") or []
    if recommendations:
        summary_lines = [
            (
                f"{rec['book']['title']} by {rec['book']['author']} "
                f"({rec['book']['genre']}, level {rec['book']['reading_level']})"
            )
            for rec in recommendations
        ]
        lines.append(
            "Recommended titles for reference (use only these in your reply):\n"
            + "\n".join(summary_lines)
        )

    return "\n".join(lines)
