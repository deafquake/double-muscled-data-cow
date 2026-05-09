import { useEffect, useState } from "react";
import { themeOptions, type ThemeId } from "../theme";

interface SettingsPanelProps {
  isOpen: boolean;
  onClose: () => void;
  theme: ThemeId;
  onThemeChange: (theme: ThemeId) => void;
  apiBase: string;
}

type CalendarStatus = "loading" | "connected" | "disconnected" | "unavailable";

const IconCalendar = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M19 4h-1V2h-2v2H8V2H6v2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm0 16H5V10h14v10zm0-12H5V6h14v2z" fill="currentColor"/>
  </svg>
);

const SettingsPanel = ({ isOpen, onClose, theme, onThemeChange, apiBase }: SettingsPanelProps) => {
  const [calendarStatus, setCalendarStatus] = useState<CalendarStatus>("loading");
  const [calendarLoading, setCalendarLoading] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    checkCalendarStatus();
  }, [isOpen]);

  const checkCalendarStatus = async () => {
    setCalendarStatus("loading");
    try {
      const res = await fetch(`${apiBase}/auth/google/calendar/status`, {
        credentials: "include",
      });
      if (res.status === 503) {
        setCalendarStatus("unavailable");
        return;
      }
      if (res.ok) {
        const data = await res.json() as { connected: boolean };
        setCalendarStatus(data.connected ? "connected" : "disconnected");
      } else {
        setCalendarStatus("disconnected");
      }
    } catch {
      setCalendarStatus("disconnected");
    }
  };

  const handleConnect = async () => {
    setCalendarLoading(true);
    try {
      const res = await fetch(`${apiBase}/auth/google/calendar`, {
        credentials: "include",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({})) as { error?: string };
        alert(data.error ?? "Failed to start Google Calendar authorization.");
        return;
      }
      const { auth_url } = await res.json() as { auth_url: string };
      window.location.href = auth_url;
    } catch {
      alert("Could not reach the server. Please try again.");
    } finally {
      setCalendarLoading(false);
    }
  };

  const handleDisconnect = async () => {
    if (!confirm("Disconnect Google Calendar? The agent will no longer be able to access your calendar.")) return;
    setCalendarLoading(true);
    try {
      await fetch(`${apiBase}/auth/google/calendar/disconnect`, {
        method: "POST",
        credentials: "include",
      });
      setCalendarStatus("disconnected");
    } catch {
      alert("Failed to disconnect. Please try again.");
    } finally {
      setCalendarLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="settings-overlay" role="dialog" aria-modal="true">
      <div className="settings-panel">
        <header className="settings-header">
          <h2>Workspace Settings</h2>
          <button className="ghost-button" onClick={onClose}>
            Close
          </button>
        </header>

        <section className="settings-section">
          <h3>Appearance</h3>
          <label className="settings-field theme-picker">
            <span>Theme</span>
            <select
              className="theme-select"
              value={theme}
              onChange={(e) => onThemeChange(e.target.value as ThemeId)}
            >
              {themeOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </section>

        <section className="settings-section">
          <h3>Integrations</h3>
          <div className="settings-field integration-row">
            <span className="integration-label">
              <IconCalendar />
              Google Calendar
            </span>
            <span className={`integration-badge ${calendarStatus}`}>
              {calendarStatus === "loading" && "Checking…"}
              {calendarStatus === "connected" && "Connected"}
              {calendarStatus === "disconnected" && "Not connected"}
              {calendarStatus === "unavailable" && "Not configured"}
            </span>
            {calendarStatus === "connected" ? (
              <button
                className="ghost-button integration-action"
                onClick={handleDisconnect}
                disabled={calendarLoading}
              >
                {calendarLoading ? "Disconnecting…" : "Disconnect"}
              </button>
            ) : calendarStatus === "disconnected" ? (
              <button
                className="ghost-button integration-action"
                onClick={handleConnect}
                disabled={calendarLoading}
              >
                {calendarLoading ? "Redirecting…" : "Connect"}
              </button>
            ) : null}
          </div>
        </section>

        <section className="settings-section">
          <h3>Session</h3>
          <label className="settings-field">
            <span>API Base URL</span>
            <input type="text" placeholder="https://api.example.com" />
          </label>
          <label className="settings-field">
            <span>API Key</span>
            <input type="password" placeholder="••••••••" />
          </label>
        </section>

        <section className="settings-section">
          <h3>Conversation</h3>
          <label className="settings-field">
            <span>Temperature</span>
            <input type="number" min="0" max="1" step="0.1" defaultValue={0.2} />
          </label>
          <label className="settings-field">
            <span>Max Turns</span>
            <input type="number" min="1" max="20" defaultValue={6} />
          </label>
        </section>
      </div>
    </div>
  );
};

export default SettingsPanel;
