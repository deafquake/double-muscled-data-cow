import { useState, useEffect, useCallback } from "react";

interface CalendarEvent {
  title: string;
  type: string;
  relative_time: string;
  details: string;
  context: string;
  location: string | null;
  with: string[];
}

interface PersonEncountered {
  name: string;
  relationship: string;
  conversation_summary: string;
  action_items_for_them: string[];
  action_items_for_martin: string[];
}

interface Segment {
  segment_number: number;
  summary: string;
  people_present: string[];
  topics: string[];
  tone: string;
  action_items: string[];
  calendar_events: CalendarEvent[];
  martins_decisions: string[];
}

interface Transcript {
  video: string;
  timestamp: string;
  created_at: string;
  brief_summary: string;
  segments: Segment[];
  people_encountered: PersonEncountered[];
  calendar_events: CalendarEvent[];
  martins_action_items: string[];
  total_segments: number;
}

interface FrameData {
  filename: string;
  data_url: string;
}

interface VideoIngestionPageProps {
  fetchJson: <T>(path: string, init?: RequestInit) => Promise<T>;
}

const HOURS = Array.from({ length: 24 }, (_, i) => i);

const padZ = (n: number) => n.toString().padStart(2, "0");

const formatHour = (h: number) => `${padZ(h)}:00`;

const formatDate = (d: Date) =>
  d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });

const toISODate = (d: Date) =>
  `${d.getFullYear()}-${padZ(d.getMonth() + 1)}-${padZ(d.getDate())}`;

const getHourMinute = (t: Transcript): [number, number] => {
  const ts = t.timestamp || t.created_at;
  if (!ts) return [0, 0];
  const d = new Date(ts);
  return [d.getHours(), d.getMinutes()];
};

const formatTime = (t: Transcript) => {
  const [h, m] = getHourMinute(t);
  return `${padZ(h)}:${padZ(m)}`;
};

const VideoIngestionPage = ({ fetchJson }: VideoIngestionPageProps) => {
  const [selectedDate, setSelectedDate] = useState(() => new Date());
  const [transcripts, setTranscripts] = useState<Transcript[]>([]);
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Transcript | null>(null);
  const [frames, setFrames] = useState<Record<number, FrameData[]>>({});
  const [loadingFrames, setLoadingFrames] = useState<Set<number>>(new Set());

  const loadTranscripts = useCallback(
    async (date: Date) => {
      setLoading(true);
      setApiError(null);
      setSelected(null);
      setFrames({});
      try {
        const data = await fetchJson<{ transcripts: Transcript[] }>(
          `/videos/transcripts?date=${toISODate(date)}`
        );
        setTranscripts(data.transcripts);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        console.error("Failed to load transcripts:", msg);
        setApiError(msg);
        setTranscripts([]);
      } finally {
        setLoading(false);
      }
    },
    [fetchJson]
  );

  useEffect(() => {
    loadTranscripts(selectedDate);
  }, [selectedDate, loadTranscripts]);

  const changeDay = (delta: number) => {
    setSelectedDate((prev) => {
      const next = new Date(prev);
      next.setDate(next.getDate() + delta);
      return next;
    });
  };

  const loadSegmentFrames = useCallback(
    async (videoId: string, segNum: number) => {
      if (frames[segNum] !== undefined) return;
      setLoadingFrames((prev) => new Set(prev).add(segNum));
      try {
        const data = await fetchJson<{ frames: FrameData[] }>(
          `/videos/${videoId}/segment/${segNum}/frames`
        );
        setFrames((prev) => ({ ...prev, [segNum]: data.frames }));
      } catch (err) {
        console.error("Failed to load frames for segment", segNum, err);
        setFrames((prev) => ({ ...prev, [segNum]: [] }));
      } finally {
        setLoadingFrames((prev) => {
          const next = new Set(prev);
          next.delete(segNum);
          return next;
        });
      }
    },
    [fetchJson, frames]
  );

  const handleSelectTranscript = (t: Transcript) => {
    setSelected(t);
    setFrames({});
    if (t.segments) {
      t.segments.forEach((seg) => {
        loadSegmentFrames(t.video, seg.segment_number);
      });
    }
  };

  // Group transcripts by hour
  const byHour: Record<number, Transcript[]> = {};
  transcripts.forEach((t) => {
    const [h] = getHourMinute(t);
    if (!byHour[h]) byHour[h] = [];
    byHour[h].push(t);
  });

  const hasAnyTranscripts = transcripts.length > 0;

  return (
    <div className="ingestion-page">
      <div className="ingestion-date-nav">
        <button className="ingestion-nav-btn" onClick={() => changeDay(-1)}>
          &#8249;
        </button>
        <span className="ingestion-date-label">{formatDate(selectedDate)}</span>
        <button className="ingestion-nav-btn" onClick={() => changeDay(1)}>
          &#8250;
        </button>
      </div>

      <div className="ingestion-body">
        <div className="ingestion-timeline">
          {loading ? (
            <div className="ingestion-empty">Loading&hellip;</div>
          ) : apiError ? (
            <div className="ingestion-error">
              <strong>Failed to load transcripts</strong>
              <span>{apiError}</span>
            </div>
          ) : !hasAnyTranscripts ? (
            <div className="ingestion-empty">No video ingestions for this day.</div>
          ) : null}

          {HOURS.map((h) => {
            const entries = byHour[h] || [];
            return (
              <div key={h} className={`ingestion-hour-row ${entries.length > 0 ? "has-entries" : ""}`}>
                <div className="ingestion-hour-label">{formatHour(h)}</div>
                <div className="ingestion-hour-track">
                  <div className="ingestion-hour-line" />
                  {entries.map((t, i) => {
                    const [, m] = getHourMinute(t);
                    const topOffset = (m / 60) * 56;
                    return (
                      <button
                        key={i}
                        className={`ingestion-card ${selected === t ? "ingestion-card--active" : ""}`}
                        style={{ top: `${topOffset}px` }}
                        onClick={() => handleSelectTranscript(t)}
                      >
                        <span className="ingestion-card-time">{formatTime(t)}</span>
                        <span className="ingestion-card-summary">{t.brief_summary}</span>
                        {t.people_encountered?.length > 0 && (
                          <span className="ingestion-card-people">
                            {t.people_encountered.map((p) => p.name).join(", ")}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {selected && (
          <div className="ingestion-detail">
            <div className="ingestion-detail-header">
              <h2 className="ingestion-detail-title">
                {formatTime(selected)} &mdash; {selected.video}
              </h2>
              <button
                className="ingestion-detail-close"
                onClick={() => setSelected(null)}
                aria-label="Close detail"
              >
                &#10005;
              </button>
            </div>

            <p className="ingestion-detail-summary">{selected.brief_summary}</p>

            {selected.people_encountered?.length > 0 && (
              <div className="ingestion-section">
                <h3 className="ingestion-section-title">People</h3>
                <div className="ingestion-people-list">
                  {selected.people_encountered.map((p, i) => (
                    <div key={i} className="ingestion-person">
                      <strong>{p.name}</strong>
                      <span className="ingestion-person-role">{p.relationship}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {selected.martins_action_items?.length > 0 && (
              <div className="ingestion-section">
                <h3 className="ingestion-section-title">Action Items</h3>
                <ul className="ingestion-list">
                  {selected.martins_action_items.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="ingestion-section">
              <h3 className="ingestion-section-title">
                Segments ({selected.segments?.length ?? 0})
              </h3>
              <div className="ingestion-segments">
                {selected.segments?.map((seg) => (
                  <div key={seg.segment_number} className="ingestion-segment">
                    <div className="ingestion-segment-header">
                      <span className="ingestion-segment-num">#{seg.segment_number}</span>
                      {seg.tone && (
                        <span className="ingestion-segment-tone">{seg.tone}</span>
                      )}
                      {seg.topics?.length > 0 && (
                        <span className="ingestion-segment-topics">
                          {seg.topics.join(" · ")}
                        </span>
                      )}
                    </div>

                    {seg.summary && seg.summary !== "PARSE ERROR" && (
                      <p className="ingestion-segment-summary">{seg.summary}</p>
                    )}

                    {loadingFrames.has(seg.segment_number) ? (
                      <div className="ingestion-frames-loading">Loading frames&hellip;</div>
                    ) : frames[seg.segment_number]?.length > 0 ? (
                      <div className="ingestion-frames">
                        {frames[seg.segment_number].map((f, fi) => (
                          <img
                            key={fi}
                            src={f.data_url}
                            alt={f.filename}
                            className="ingestion-frame"
                          />
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default VideoIngestionPage;
