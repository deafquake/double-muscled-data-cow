import os
import json
import base64
import glob as _glob
from pathlib import Path
from openai import OpenAI

from tools import get_current_scene_transcript, get_current_scene_keyframes, get_currentscene

_SHARED          = Path(os.environ.get("SHARED_DIR", "/app/shared"))
_TRANSCRIPT_BASE = _SHARED / "deepspeechout"
_KEYFRAME_BASE   = _SHARED / "objectdetectorout"

_LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://10.0.5.222:1234/v1")
_LLM_MODEL    = os.environ.get("LLM_MODEL", "gemma-4")


def _scene_count(name_of_video: str) -> int:
    """Return the number of scenes available for a video (based on transcript files)."""
    pattern = str(_TRANSCRIPT_BASE / name_of_video / f"{name_of_video}_*.txt")
    return len(_glob.glob(pattern))


class Orchestrator:
    """Meeting analysis pipeline.

    Flow
    ----
    analyse_video(name_of_video)
        1. For each segment 0..N-1:
              a. Load transcript + keyframe(s) via tools.py
              b. Call the LLM with the compact running state + new segment data
              c. LLM returns an UPDATED running state and a per-segment entry
        2. After all segments, make one final aggregation call to produce a
           plain-text meeting summary (decisions, action items, people, topics).
        3. Save and return the final output.
    """

    def __init__(self, model: str = _LLM_MODEL):
        self.model = model
        self.client = OpenAI(base_url=_LLM_BASE_URL, api_key="lm-studio")

    # ------------------------------------------------------------------
    # Low-level: image + text call
    # ------------------------------------------------------------------

    def chat_with_image(self, prompt: str, image_path: str, **kwargs) -> str:
        """Send a text prompt alongside a single local image and return the reply."""
        return self.chat_with_images(prompt, [image_path], **kwargs)

    def chat_with_images(self, prompt: str, image_paths: list[str], **kwargs) -> str:
        """Send a text prompt alongside one or more local images (base64-encoded) and return the reply."""
        content: list[dict] = [{"type": "text", "text": prompt}]
        for image_path in image_paths:
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            ext = Path(image_path).suffix.lstrip(".").lower()
            mime = f"image/{ext}" if ext in ("jpg", "jpeg", "png", "webp", "gif") else "image/jpeg"
            content.append(
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
            )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": content}],
            **kwargs,
        )
        return response.choices[0].message.content

    def chat(self, prompt: str, **kwargs) -> str:
        """Plain text chat (no image)."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        return response.choices[0].message.content

    # ------------------------------------------------------------------
    # Per-scene update
    # ------------------------------------------------------------------

    def _update_metadata_for_scene(
        self,
        running_state: dict,
        scene_number: int,
        transcript: str,
        keyframes: list[str],
    ) -> tuple[dict, dict]:
        """Update the compact running state with one meeting segment.

        Only the compact running state is sent to the LLM each turn — never
        the growing segment list — so context size stays flat across segments.

        Returns:
            (updated_running_state, segment_entry)
        """
        frame_note = (
            f"{len(keyframes)} frame(s) from this segment are attached as images."
            if keyframes
            else "No images are available for this segment."
        )

        compact_str = json.dumps(running_state, indent=2)

        prompt = f"""You are a business meeting analyst building a structured record of a meeting incrementally.

ACCUMULATED STATE SO FAR:
{compact_str}

SEGMENT {scene_number} TRANSCRIPT:
\"\"\"{transcript}\"\"\"

VISUAL CONTEXT: {frame_note}

Return a single JSON object with exactly TWO top-level keys:

1. "running_state": the updated accumulated knowledge containing ONLY these fields:

   - "participants": dict of person name → object with:
       * "role": their role or title (e.g. "Host", "Engineer", "Guest")
       * "shared": list of things they have shared/presented/contributed so far (append, never overwrite)
       * "decisions": list of decisions they personally made or drove (append)
       * "action_items": list of tasks assigned to them so far (append, format: "task description")

   - "relationships": dict of "PersonA & PersonB" (alphabetical order) → object with:
       * "topics": list of topics these two people have discussed together (append new ones)
       * "notes": running narrative of how their interaction has evolved — APPEND new developments,
                  do not erase prior history. Each new interaction adds to the end of this string.

   - "topics_discussed": list of all topics covered so far across the whole meeting (add new ones)
   - "decisions_made": list of all decisions taken so far — short statements (add new ones)
   - "action_items": list of all tasks assigned so far — format "Name: task" (add new ones)
   - "calendar_items": list of all calendar-relevant items so far — deadlines, scheduled meetings, follow-ups
   - "context": one short paragraph summarising meeting purpose and flow UP TO AND INCLUDING this segment

2. "segment_entry": a dict for THIS segment only:
   - "segment_number": {scene_number}
   - "summary": 1-2 sentence description of what was discussed
   - "participants_present": list of names speaking or visible in this segment
   - "topics": list of topics raised in this segment
   - "decisions": list of decisions made in this segment (empty list if none)
   - "action_items": list of action items from this segment (empty list if none)
   - "calendar_items": list of calendar-relevant items from this segment (empty list if none)
   - "tone": the conversational tone (e.g. "collaborative", "tense", "brainstorming", "formal")

Return ONLY the JSON object — no markdown fences, no extra text."""

        if keyframes:
            raw = self.chat_with_images(prompt, keyframes)
        else:
            raw = self.chat(prompt)

        print(f"\n[LLM RAW REPLY — segment {scene_number}]\n{raw}\n[END RAW REPLY]\n", flush=True)

        raw = raw.strip()

        # Model reasons first then emits JSON after a delimiter token
        if "<channel|>" in raw:
            raw = raw.split("<channel|>", 1)[1].strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0].strip()

        try:
            parsed = json.loads(raw)
            return parsed["running_state"], parsed["segment_entry"]
        except (json.JSONDecodeError, KeyError):
            error_entry = {
                "segment_number": scene_number,
                "summary": "PARSE ERROR",
                "_raw_reply": raw,
            }
            return running_state, error_entry

    # ------------------------------------------------------------------
    # Final aggregation
    # ------------------------------------------------------------------

    def _final_aggregation(self, running_state: dict, scenes: list[dict]) -> dict:
        """Final pass: distil the accumulated state into a plain-text meeting summary."""

        compact_str = json.dumps(running_state, indent=2)

        prompt = f"""You are a business meeting analyst.

Below is the full accumulated knowledge extracted from a meeting recording:
{compact_str}

Produce a final meeting report as a JSON object with these fields:

- "participants": list of objects, one per person — each with "name", "role", "contributions" (what they shared/drove), "decisions", "action_items"
- "relationships": list of objects, one per pair — each with "pair" (e.g. "Alice & Bob"), "topics", "summary" (plain-text narrative of their interaction arc)
- "topics_discussed": consolidated list of all topics covered in the meeting
- "decisions_made": consolidated list of all decisions (clear, actionable statements)
- "action_items": consolidated list of all tasks with ownership (format: "Name: task")
- "calendar_items": consolidated list of all dates, deadlines, and scheduled events
- "brief_summary": a plain-text paragraph (5-8 sentences) — who attended, what was discussed, what was decided, and what the next steps are

Return ONLY the JSON object — no markdown fences, no extra text."""

        raw = self.chat(prompt)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"brief_summary": raw}


    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def analyse_video(self, name_of_video: str, output_path: str | None = None) -> dict:
        """Iterate over all segments of a meeting recording and build a structured summary.

        Context stays flat by design:
          - The LLM only ever sees the COMPACT running state — never the growing segment list.
          - Per-segment entries are accumulated locally and never fed back to the model.

        After every segment a snapshot is written to:
            /app/shared/<name_of_video>_evolution/segment_<N>.json
        The final JSON is written to:
            /app/shared/<name_of_video>_metadata.json

        Args:
            name_of_video:  folder name under deepspeechout  (e.g. "osc")
            output_path:    where to save the final JSON

        Returns the final metadata dict.
        """
        total_scenes = _scene_count(name_of_video)
        if total_scenes == 0:
            raise ValueError(f"No scenes found for video '{name_of_video}'.")

        evolution_dir = _SHARED / f"{name_of_video}_evolution"
        evolution_dir.mkdir(parents=True, exist_ok=True)

        print(f"[Orchestrator] Starting analysis for '{name_of_video}' — {total_scenes} scenes.")
        print(f"[Orchestrator] Snapshots → {evolution_dir}")

        # Compact running state — this is ALL that gets sent to the LLM each iteration
        running_state: dict = {
            "participants": {},
            "relationships": {},
            "topics_discussed": [],
            "decisions_made": [],
            "action_items": [],
            "calendar_items": [],
            "context": "",
        }

        # Per-scene entries accumulated locally — never sent back to the model
        scenes: list[dict] = []

        # One entry per scene showing how the compact state evolved
        compact_evolution: list[dict] = []

        for scene_num in range(total_scenes):
            print(f"  → Scene {scene_num}/{total_scenes - 1} ...", end=" ", flush=True)

            try:
                scene = get_currentscene(name_of_video, scene_num)
                transcript = scene["transcript"]
                keyframes  = scene["keyframes"]
            except FileNotFoundError as e:
                print(f"SKIP ({e})")
                continue

            running_state, scene_entry = self._update_metadata_for_scene(
                running_state, scene_num, transcript, keyframes
            )
            scenes.append(scene_entry)

            # 1. Full snapshot: compact state + all segments collected so far
            snapshot = {
                "video": name_of_video,
                "segments_processed": scene_num + 1,
                "running_state": running_state,
                "segments": scenes,
            }
            snapshot_path = evolution_dir / f"segment_{scene_num:04d}.json"
            with open(snapshot_path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False)

            # 2. Compact-only evolution: append one entry to compact_evolution.json
            compact_entry = {
                "after_segment": scene_num,
                **running_state,
            }
            compact_evolution.append(compact_entry)
            compact_evo_path = evolution_dir / "compact_evolution.json"
            with open(compact_evo_path, "w", encoding="utf-8") as f:
                json.dump(compact_evolution, f, indent=2, ensure_ascii=False)

            print(f"done.  [snapshot → {snapshot_path.name}]")

        print("[Orchestrator] Running final aggregation pass …")
        final_summary = self._final_aggregation(running_state, scenes)

        # Merge everything into the final output
        metadata = {
            "video": name_of_video,
            "total_segments": total_scenes,
            "running_state": running_state,   # full accumulated knowledge
            "segments": scenes,               # per-segment detail
            **final_summary,                  # participants, decisions, action_items, brief_summary, etc.
        }

        # Save final aggregation snapshot
        final_snapshot = evolution_dir / "final_aggregation.json"
        with open(final_snapshot, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"[Orchestrator] Final aggregation snapshot → {final_snapshot.name}")

        if output_path is None:
            output_path = str(_SHARED / f"{name_of_video}_metadata.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"[Orchestrator] Done. Final metadata → {output_path}")
        print(f"[Orchestrator] Evolution snapshots → {evolution_dir}/")
        return metadata


# ------------------------------------------------------------------
# CLI entry point:  python orchestrator.py osc
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python orchestrator.py <name_of_video>")
        sys.exit(1)
    video_name = sys.argv[1]
    orch = Orchestrator()
    result = orch.analyse_video(video_name)
    print(json.dumps(result, indent=2))
