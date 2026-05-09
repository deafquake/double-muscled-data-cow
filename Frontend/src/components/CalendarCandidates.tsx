import { useState, useRef } from "react";

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
  onAnalyze: (transcript: string) => Promise<void>;
  onApprove: (id: string) => Promise<void>;
  onReject: (id: string) => Promise<void>;
  isAnalyzing: boolean;
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
  onAnalyze,
  onApprove,
  onReject,
  isAnalyzing,
}: CalendarCandidatesProps) {
  const [expanded, setExpanded] = useState(false);
  const [actioningId, setActioningId] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleAnalyze = async () => {
    const text = textareaRef.current?.value.trim() ?? "";
    if (!text) return;
    await onAnalyze(text);
    if (textareaRef.current) textareaRef.current.value = "";
  };

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
        <span className="calendar-candidates-icon">📅</span>
        <span className="calendar-candidates-title">
          Calendar suggestions
          {candidates.length > 0 && (
            <span className="calendar-candidates-badge">{candidates.length}</span>
          )}
        </span>
        <span className="calendar-candidates-chevron">{expanded ? "▲" : "▼"}</span>
      </div>

      {expanded && (
        <div className="calendar-candidates-body">
          <div className="calendar-analyze-area">
            <textarea
              ref={textareaRef}
              className="calendar-transcript-input"
              placeholder="Paste a transcript or meeting notes here to detect calendar events…"
              rows={4}
            />
            <button
              className="calendar-analyze-btn"
              onClick={handleAnalyze}
              disabled={isAnalyzing}
            >
              {isAnalyzing ? "Analyzing…" : "Find events"}
            </button>
          </div>

          {candidates.length === 0 ? (
            <p className="calendar-candidates-empty">
              No pending event suggestions. Paste a transcript above to find events.
            </p>
          ) : (
            <ul className="calendar-candidates-list">
              {candidates.map((c) => {
                const expired = isExpired(c.start_datetime);
                const busy = actioningId === c.id;
                return (
                  <li key={c.id} className={`calendar-candidate-card ${expired ? "expired" : ""}`}>
                    <div className="candidate-card-main">
                      <span className="candidate-title">{c.title}</span>
                      {expired && <span className="candidate-expired-tag">Expired</span>}
                    </div>
                    <div className="candidate-datetime">
                      {formatDatetime(c.start_datetime)} → {formatDatetime(c.end_datetime)}
                      {c.timezone !== "UTC" && (
                        <span className="candidate-tz"> ({c.timezone})</span>
                      )}
                    </div>
                    {c.location && (
                      <div className="candidate-detail">📍 {c.location}</div>
                    )}
                    {c.description && (
                      <div className="candidate-detail candidate-description">{c.description}</div>
                    )}
                    {c.source_excerpt && (
                      <blockquote className="candidate-excerpt">"{c.source_excerpt}"</blockquote>
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
      )}
    </div>
  );
}
