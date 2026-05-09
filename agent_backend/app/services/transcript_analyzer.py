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


def analyze_transcript(transcript_text: str, user_id) -> list[dict]:
    """Use an LLM to extract calendar event candidates from transcript_text and persist them."""
    from ..db import SessionLocal
    from ..models.chat_models import CalendarEventCandidate

    llm = ChatOpenAI(
        model=CONTEXT_SUMMARIZATION_MODEL,
        base_url=LMSTUDIO_BASE_URL,
        api_key=OPENAI_API_KEY,
        temperature=0,
    )

    today = datetime.utcnow().strftime("%Y-%m-%d")
    year = today[:4]

    messages = [
        SystemMessage(content=_EXTRACTION_SYSTEM.format(today=today, year=year)),
        HumanMessage(content=f"Extract calendar events from this transcript:\n\n{transcript_text}"),
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

    db = SessionLocal()
    saved: list[dict] = []
    try:
        for event in events_data:
            try:
                start_dt = datetime.fromisoformat(event["start_datetime"])
                end_dt = datetime.fromisoformat(event["end_datetime"])
            except (KeyError, ValueError) as exc:
                logger.warning("Skipping event with bad datetimes: %s — %s", event, exc)
                continue

            if end_dt <= start_dt:
                end_dt = start_dt + timedelta(hours=1)

            candidate = CalendarEventCandidate(
                user_id=user_id,
                title=event.get("title", "Untitled Event")[:256],
                start_datetime=start_dt,
                end_datetime=end_dt,
                description=event.get("description") or None,
                location=(event.get("location") or None),
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
