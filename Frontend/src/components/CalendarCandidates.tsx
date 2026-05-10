import { useState } from "react";

export type CalendarCandidate = {
  id: string;
  title: string;
  start_datetime: string;
  end_datetime: string;
  description?: string | null;
  location?: string | null;
  timezone: string;
  source_excerpt?: string | null;
  status: string;
};

interface CalendarCandidatesProps {
  candidates: CalendarCandidate[];
  onApprove: (id: string) => Promise<void>;
  onReject: (id: string) => Promise<void>;
}

function formatDatetime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function isExpired(iso: string): boolean {
  return new Date(iso) < new Date();
}

export default function CalendarCandidates({
  candidates,
  onApprove,
  onReject,
}: CalendarCandidatesProps) {
  const [expanded, setExpanded] = useState(true);
  const [actioningId, setActioningId] = useState<string | null>(null);

  if (candidates.length === 0) return null;

  const handleApprove = async (id: string) => {
    setActioningId(id);
    try {
      await onApprove(id);
    } finally {
      setActioningId(null);
    }
  };

  const handleReject = async (id: string) => {
    setActioningId(id);
    try {
      await onReject(id);
    } finally {
      setActioningId(null);
    }
  };

  return (
    <div className="calendar-candidates-section">
      <div
        className="calendar-candidates-header"
        role="button"
        tabIndex={0}
        onClick={() => setExpanded((v) => !v)}
        onKeyDown={(e) => e.key === "Enter" && setExpanded((v) => !v)}
      >
        <svg className="calendar-candidates-icon" viewBox="0 0 20 20" fill="none" aria-hidden="true" width="15" height="15">
          <rect x="2" y="4" width="16" height="14" rx="2" stroke="currentColor" strokeWidth="2"/>
          <line x1="2" y1="8" x2="18" y2="8" stroke="currentColor" strokeWidth="2"/>
          <line x1="6" y1="2" x2="6" y2="6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          <line x1="14" y1="2" x2="14" y2="6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        </svg>
        <span className="calendar-candidates-title">
          Events to approve
          <span className="calendar-candidates-badge">{candidates.length}</span>
        </span>
        <span className="calendar-candidates-chevron">{expanded ? "▲" : "▼"}</span>
      </div>

      {expanded && (
        <ul className="calendar-candidates-list">
          {candidates.map((c) => {
            const expired = isExpired(c.start_datetime);
            const busy = actioningId === c.id;
            return (
              <li key={c.id} className={`calendar-candidate-card${expired ? " expired" : ""}`}>
                <div className="candidate-card-main">
                  <span className="candidate-title">{c.title}</span>
                  {expired && <span className="candidate-expired-tag">Past</span>}
                </div>
                <div className="candidate-datetime">
                  {formatDatetime(c.start_datetime)} → {formatDatetime(c.end_datetime)}
                  {c.timezone !== "UTC" && (
                    <span className="candidate-tz"> · {c.timezone}</span>
                  )}
                </div>
                {c.location && (
                  <div className="candidate-detail">📍 {c.location}</div>
                )}
                <div className="candidate-actions">
                  <button
                    className="candidate-btn approve"
                    onClick={() => handleApprove(c.id)}
                    disabled={busy}
                  >
                    {busy ? "…" : expired ? "Acknowledge" : "Add to Calendar"}
                  </button>
                  <button
                    className="candidate-btn reject"
                    onClick={() => handleReject(c.id)}
                    disabled={busy}
                  >
                    Dismiss
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
