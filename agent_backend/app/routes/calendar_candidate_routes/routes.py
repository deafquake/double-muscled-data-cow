from datetime import datetime, timezone as dt_tz

from flask import g, jsonify, request

from ...db import SessionLocal
from ...models.chat_models import CalendarEventCandidate, CandidateStatus
from ...routes.auth_routes.auth_extensions import token_auth
from ...services.transcript_analyzer import analyze_transcript
from ...services.agent.calendar_agent.tools import _get_user_calendar_service
from ...utils.logger import get_logger
from . import candidate_bp

logger = get_logger(__name__)


@candidate_bp.get("/calendar-candidates")
@token_auth.login_required
def list_candidates():
    user = g.user
    db = SessionLocal()
    try:
        candidates = (
            db.query(CalendarEventCandidate)
            .filter_by(user_id=user.id, status=CandidateStatus.PENDING)
            .order_by(CalendarEventCandidate.created_at.desc())
            .all()
        )
        return jsonify({"candidates": [c.to_dict() for c in candidates]})
    finally:
        db.close()


@candidate_bp.post("/calendar-candidates/analyze")
@token_auth.login_required
def analyze():
    user = g.user
    data = request.get_json(silent=True) or {}
    transcript = (data.get("transcript") or "").strip()
    if not transcript:
        return jsonify({"error": "No transcript provided"}), 400

    try:
        candidates = analyze_transcript(transcript, user.id)
        return jsonify({"candidates": candidates})
    except Exception as exc:
        logger.error("Transcript analysis failed: %s", exc)
        return jsonify({"error": str(exc)}), 500


@candidate_bp.post("/calendar-candidates/<candidate_id>/approve")
@token_auth.login_required
def approve_candidate(candidate_id: str):
    user = g.user
    db = SessionLocal()
    try:
        candidate = (
            db.query(CalendarEventCandidate)
            .filter_by(id=candidate_id, user_id=user.id)
            .first()
        )
        if not candidate:
            return jsonify({"error": "Candidate not found"}), 404

        now = datetime.now(dt_tz.utc)
        start = candidate.start_datetime
        if start.tzinfo is None:
            from datetime import timezone
            start = start.replace(tzinfo=timezone.utc)

        if start < now:
            candidate.status = CandidateStatus.APPROVED
            db.commit()
            return jsonify({
                "message": "Approved — event date has already passed, not added to calendar.",
                "expired": True,
            })

        try:
            service = _get_user_calendar_service(str(user.id))
            fmt = "%Y-%m-%dT%H:%M:%S"
            event_body: dict = {
                "summary": candidate.title,
                "start": {"dateTime": candidate.start_datetime.strftime(fmt), "timeZone": candidate.timezone},
                "end": {"dateTime": candidate.end_datetime.strftime(fmt), "timeZone": candidate.timezone},
            }
            if candidate.description:
                event_body["description"] = candidate.description
            if candidate.location:
                event_body["location"] = candidate.location

            created = service.events().insert(calendarId="primary", body=event_body).execute()
            candidate.google_event_id = created["id"]
            candidate.status = CandidateStatus.APPROVED
            db.commit()
            return jsonify({
                "message": "Event added to Google Calendar.",
                "google_event_id": created["id"],
                "google_event_link": created.get("htmlLink"),
            })

        except RuntimeError as exc:
            # Calendar not connected — approve locally without pushing to Google
            candidate.status = CandidateStatus.APPROVED
            db.commit()
            return jsonify({
                "message": "Approved locally. Google Calendar is not connected.",
                "calendar_error": str(exc),
            })

    finally:
        db.close()


@candidate_bp.post("/calendar-candidates/<candidate_id>/reject")
@token_auth.login_required
def reject_candidate(candidate_id: str):
    user = g.user
    db = SessionLocal()
    try:
        candidate = (
            db.query(CalendarEventCandidate)
            .filter_by(id=candidate_id, user_id=user.id)
            .first()
        )
        if not candidate:
            return jsonify({"error": "Candidate not found"}), 404

        candidate.status = CandidateStatus.REJECTED
        db.commit()
        return jsonify({"message": "Candidate rejected."})
    finally:
        db.close()
