import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from ...utils.logger import get_logger
from ...db import SessionLocal
from ...models.chat_models import CalendarEventCandidate

logger = get_logger(__name__)

_LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://10.0.5.222:1234/v1")
_LLM_MODEL = os.environ.get("LLM_MODEL", "gemma-4")

_SYSTEM = """You are a calendar event extraction assistant. Today is {today}.

For every calendar event in the transcript, call store_calendar_event once per event.
Resolve all relative dates ("Tuesday", "next week") to absolute YYYY-MM-DDTHH:MM:SS datetimes, extract the names of the coinvolved parties and try to include their names except the users name ("Martin") in the title of the event.
Assume year {year} when none is stated. Default to 09:00-10:00 when only a date is given.
Call the tool once per unique event. Do not output prose."""


def analyze_transcript(
    transcript_text: str,
    user_id,
    reference_datetime: str | None = None,
    preextracted_events: list[dict] | None = None,
) -> list[dict]:
    """
    Extract calendar events from a transcript and persist them as candidates.

    Uses a LangGraph ReAct agent that calls store_calendar_event for each event
    it finds. The tool writes directly to the DB, so there is no JSON parsing.

    Parameters
    ----------
    transcript_text : str
        Raw transcript to extract events from.
    user_id : int | str | None
        User to associate candidates with. Pass None to skip DB persistence.
    reference_datetime : str | None
        ISO datetime of the recording; anchors relative date resolution.
    preextracted_events : list[dict] | None
        Events pre-identified by the orchestrator, included as hints.

    Returns
    -------
    list[dict] — stored calendar event dicts (empty on failure).
    """
    db = SessionLocal() if user_id is not None else None
    saved: list[dict] = []

    @tool
    def store_calendar_event(
        title: str,
        start_datetime: str,
        end_datetime: str,
        timezone: str = "UTC",
        description: Optional[str] = None,
        location: Optional[str] = None,
        source_excerpt: Optional[str] = None,
    ) -> str:
        """Store a single calendar event candidate extracted from the transcript.

        Args:
            title: Short descriptive event title try to include the name of the parties involved except the users name which is Martin.
            start_datetime: Start time as YYYY-MM-DDTHH:MM:SS.
            end_datetime: End time as YYYY-MM-DDTHH:MM:SS.
            timezone: IANA timezone name e.g. 'Europe/Berlin'. Defaults to UTC.
            description: Optional longer description or agenda.
            location: Optional physical or virtual location.
            source_excerpt: The sentence(s) from the transcript that mention this event.
        """
        try:
            start_dt = datetime.fromisoformat(start_datetime)
            end_dt = datetime.fromisoformat(end_datetime)
        except ValueError as exc:
            logger.warning("Bad datetimes for '%s': %s", title, exc)
            return f"Skipped (bad datetimes): {title}"

        if end_dt <= start_dt:
            end_dt = start_dt + timedelta(hours=1)

        if db is not None:
            candidate = CalendarEventCandidate(
                user_id=user_id,
                title=title[:256],
                start_datetime=start_dt,
                end_datetime=end_dt,
                description=description or None,
                location=location or None,
                timezone=timezone,
                source_excerpt=source_excerpt or None,
            )
            db.add(candidate)
            saved.append({
                "title": title[:256],
                "start_datetime": start_dt.isoformat(),
                "end_datetime": end_dt.isoformat(),
                "timezone": timezone,
                "description": description,
                "location": location,
                "source_excerpt": source_excerpt,
            })
        else:
            saved.append({
                "title": title,
                "start_datetime": start_dt.isoformat(),
                "end_datetime": end_dt.isoformat(),
                "timezone": timezone,
                "description": description,
                "location": location,
                "source_excerpt": source_excerpt,
            })

        return f"Stored: {title}"

    if reference_datetime:
        try:
            anchor = datetime.fromisoformat(reference_datetime.replace("Z", "+00:00"))
        except ValueError:
            logger.warning(
                "Could not parse reference_datetime '%s', using UTC now",
                reference_datetime,
            )
            anchor = datetime.now(timezone.utc)
    else:
        anchor = datetime.now(timezone.utc)

    today = anchor.strftime("%Y-%m-%d")
    year = today[:4]

    human_parts = [f"Extract calendar events from this transcript:\n\n{transcript_text}"]
    if preextracted_events:
        hints = json.dumps(preextracted_events, indent=2)
        human_parts.append(
            f"\nThese events were pre-identified with relative times — resolve each "
            f"to an absolute datetime and call store_calendar_event for each:\n{hints}"
        )

    llm = ChatOpenAI(
        model=_LLM_MODEL,
        base_url=_LLM_BASE_URL,
        api_key="lm-studio",
        temperature=0,
    )

    agent = create_react_agent(
        llm,
        tools=[store_calendar_event],
        prompt=SystemMessage(content=_SYSTEM.format(today=today, year=year)),
    )

    try:
        agent.invoke({"messages": [HumanMessage(content="\n".join(human_parts))]})
    except Exception as exc:
        logger.error("Agent failed in transcript_analyzer: %s", exc)
        if db is not None:
            db.rollback()
            db.close()
        raise RuntimeError(f"Agent failed: {exc}") from exc

    if db is not None:
        try:
            db.commit()
            logger.info(
                "Saved %d calendar candidates for user %s", len(saved), user_id
            )
        except Exception as exc:
            db.rollback()
            logger.error("DB error saving candidates: %s", exc)
            raise
        finally:
            db.close()
    else:
        logger.info(
            "No user_id — returning %d events without DB persistence", len(saved)
        )

    return saved
