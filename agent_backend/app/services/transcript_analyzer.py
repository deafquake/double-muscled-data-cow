import json
import re
from datetime import datetime, timedelta

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from ..config.config import LMSTUDIO_BASE_URL, OPENAI_API_KEY, CONTEXT_SUMMARIZATION_MODEL
from ..utils.logger import get_logger

logger = get_logger(__name__)

_EXTRACTION_SYSTEM = """You are a calendar event extraction assistant. Today is {today}.

Extract every calendar event mentioned in the transcript. Output ONLY valid JSON with this exact structure:
{{
  "events": [
    {{
      "title": "event title",
      "start_datetime": "YYYY-MM-DDTHH:MM:SS",
      "end_datetime": "YYYY-MM-DDTHH:MM:SS",
      "description": "details or null",
      "location": "location or null",
      "timezone": "UTC",
      "source_excerpt": "the transcript sentence(s) that mention this event"
    }}
  ]
}}

Rules:
- If no events are found, output {{"events": []}}
- Infer missing times from context; if only a date is given use 09:00–10:00
- If no year is mentioned assume {year}
- Keep start_datetime strictly before end_datetime
- Output ONLY JSON, no prose"""


def analyze_transcript(
    transcript_text: str,
    user_id,
    reference_datetime: str | None = None,
    preextracted_events: list[dict] | None = None,
) -> list[dict]:
    """
    Extract calendar events from a transcript and persist them as candidates.

    Parameters
    ----------
    transcript_text : str
        Raw transcript to extract events from.
    user_id : int | str | None
        ID of the user to associate candidates with.
        Pass None to skip DB persistence and only return the extracted events.
    reference_datetime : str | None
        ISO datetime string used as "today" when resolving relative time
        references such as "Tuesday" or "next week". Defaults to UTC now.
        Pass the video's recording timestamp so that relative times in the
        transcript resolve correctly against when the video was made.
    preextracted_events : list[dict] | None
        Calendar events already extracted by the orchestrator (with relative
        "relative_time" fields). When provided, these are included in the LLM
        prompt as context hints so the model can cross-reference them while
        resolving times to absolute datetimes.

    Returns
    -------
    list[dict]  — saved calendar event dicts (empty list on failure).
    """
    from ..db import SessionLocal
    from ..models.chat_models import CalendarEventCandidate

    llm = ChatOpenAI(
        model=CONTEXT_SUMMARIZATION_MODEL,
        base_url=LMSTUDIO_BASE_URL,
        api_key=OPENAI_API_KEY,
        temperature=0,
    )

    # Use the video's recording time as the reference anchor so that relative
    # phrases like "Tuesday" or "tomorrow" resolve correctly.
    if reference_datetime:
        try:
            anchor = datetime.fromisoformat(reference_datetime.replace("Z", "+00:00"))
        except ValueError:
            logger.warning("Could not parse reference_datetime '%s', falling back to UTC now", reference_datetime)
            anchor = datetime.utcnow()
    else:
        anchor = datetime.utcnow()

    today = anchor.strftime("%Y-%m-%d")
    year = today[:4]

    human_parts = [f"Extract calendar events from this transcript:\n\n{transcript_text}"]

    if preextracted_events:
        hints = json.dumps(preextracted_events, indent=2)
        human_parts.append(
            f"\nContext: the following events were already identified with relative "
            f"time references. Use them as hints when resolving times to absolute "
            f"datetimes — do not duplicate them, just ensure each appears once with "
            f"a resolved start_datetime and end_datetime:\n{hints}"
        )

    messages = [
        SystemMessage(content=_EXTRACTION_SYSTEM.format(today=today, year=year)),
        HumanMessage(content="\n".join(human_parts)),
    ]

    try:
        response = llm.invoke(messages)
        content = response.content
    except Exception as exc:
        logger.error("LLM call failed in transcript_analyzer: %s", exc)
        raise RuntimeError(f"LLM call failed: {exc}") from exc

    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if not json_match:
        logger.warning("No JSON found in LLM response: %s", content[:200])
        return []

    try:
        data = json.loads(json_match.group())
        events_data = data.get("events", [])
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse JSON from LLM response: %s", exc)
        return []

    # Validate and normalise datetimes before touching the DB.
    validated: list[dict] = []
    for event in events_data:
        try:
            start_dt = datetime.fromisoformat(event["start_datetime"])
            end_dt = datetime.fromisoformat(event["end_datetime"])
        except (KeyError, ValueError) as exc:
            logger.warning("Skipping event with bad datetimes: %s — %s", event, exc)
            continue

        if end_dt <= start_dt:
            end_dt = start_dt + timedelta(hours=1)

        validated.append({**event, "start_datetime": start_dt, "end_datetime": end_dt})

    # Skip DB persistence when no user context is available (e.g. background
    # video ingestion without an authenticated request).
    if user_id is None:
        logger.info("No user_id provided — skipping DB persistence, returning %d events", len(validated))
        return [
            {**e, "start_datetime": e["start_datetime"].isoformat(), "end_datetime": e["end_datetime"].isoformat()}
            for e in validated
        ]

    db = SessionLocal()
    saved: list[dict] = []
    try:
        for event in validated:
            candidate = CalendarEventCandidate(
                user_id=user_id,
                title=event.get("title", "Untitled Event")[:256],
                start_datetime=event["start_datetime"],
                end_datetime=event["end_datetime"],
                description=event.get("description") or None,
                location=event.get("location") or None,
                timezone=event.get("timezone", "UTC"),
                source_excerpt=event.get("source_excerpt") or None,
            )
            db.add(candidate)
            db.flush()
            saved.append(candidate.to_dict())

        db.commit()
        logger.info("Saved %d calendar candidates for user %s", len(saved), user_id)
    except Exception as exc:
        db.rollback()
        logger.error("DB error saving candidates: %s", exc)
        raise
    finally:
        db.close()

    return saved
