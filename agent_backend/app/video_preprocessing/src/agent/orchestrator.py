import os
import json
import base64
import glob as _glob
from pathlib import Path
from openai import OpenAI

from .tools import get_current_scene_transcript, get_current_scene_keyframes, get_currentscene

_SHARED          = Path(os.environ.get("SHARED_DIR", "/app/shared"))
_TRANSCRIPT_BASE = _SHARED / "deepspeechout"
_KEYFRAME_BASE   = _SHARED / "objectdetectorout"

_LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://10.0.5.222:1234/v1")
_LLM_MODEL    = os.environ.get("LLM_MODEL", "gemma-4")


def _scene_count(name_of_video: str) -> int:
    """Return the number of scenes available for a video (based on transcript files)."""
    pattern = str(_TRANSCRIPT_BASE / name_of_video / f"{name_of_video}*.txt")
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
        print(f"[Orchestrator] Initializing with model '{model}' and LLM base URL '{_LLM_BASE_URL}'")
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

        prompt = f"""You are Martin's personal AI assistant. Martin is wearing a lapel camera and you are watching/listening to everything he experiences. Your job is to track his day incrementally — who he talks to, what decisions he makes, and what calendar events arise from his conversations.

IMPORTANT RULES:
•⁠  ⁠Everything is from Martin's perspective. He is the subject.
•⁠  ⁠Relative time references ("tomorrow", "next Friday", "in two weeks") are fine — do not guess absolute dates.
•⁠  ⁠Only extract calendar events that are explicitly mentioned or clearly implied in the conversation.
•⁠  ⁠Calendar event types: "meeting" (work/professional), "reservation" (restaurant, bar, hotel, etc.), "ticket" (travel, concert, sports, etc.), "event" (social, personal, other).
•⁠  ⁠When the same person appears again in a later segment, APPEND new conversation details — never erase history.

MARTIN'S ACCUMULATED STATE SO FAR:
{compact_str}

SEGMENT {scene_number} TRANSCRIPT:
\"\"\"{transcript}\"\"\"

VISUAL CONTEXT: {frame_note}

Return a single JSON object with exactly TWO top-level keys:

1.⁠ ⁠"running_state": updated accumulated knowledge with ONLY these fields:

   - "people": dict of person name → object with:
       * "relationship": how they relate to Martin (e.g. "colleague", "client", "friend", "stranger")
       * "conversation_log": list of short strings, one per segment where they appeared — APPEND, never overwrite
         (e.g. ["Segment 0: discussed Q3 targets", "Segment 3: agreed on Friday deadline"])
       * "action_items_for_martin": list of things Martin agreed to do for/because of this person
       * "action_items_for_them": list of things this person agreed to do

   - "martins_decisions": list of decisions Martin made himself (append new ones)
   - "martins_action_items": list of things Martin needs to do — regardless of who triggered it (append)

   - "calendar_events": list of calendar event objects (append new ones, never remove existing):
       * "type": "meeting" | "reservation" | "ticket" | "event"
       * "title": short descriptive title
       * "with": list of person names involved (empty list if solo)
       * "location": place or platform if mentioned (null if unknown)
       * "relative_time": time reference as spoken (e.g. "tomorrow at 3pm", "next Monday", null if not mentioned)
       * "details": any extra info — table size, ticket type, agenda, link, etc. (null if none)
       * "context": one sentence on how this event came up in conversation

   - "context": one short paragraph describing what Martin has been doing so far today

2.⁠ ⁠"segment_entry": a dict for THIS segment only:
   - "segment_number": {scene_number}
   - "summary": 1-2 sentence description of what happened in this segment from Martin's perspective
   - "people_present": list of names Martin interacted with in this segment
   - "topics": list of topics discussed
   - "martins_decisions": decisions Martin made in this segment (empty list if none)
   - "action_items": action items that came up in this segment (empty list if none)
   - "calendar_events": calendar events that came up in this segment (empty list if none)
   - "tone": conversational tone (e.g. "casual", "formal", "tense", "friendly")

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
        if raw.startswith("⁠ "):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit(" ⁠", 1)[0].strip()

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

        prompt = f"""You are Martin's personal AI assistant. Below is everything you tracked from his day via his lapel camera.

ACCUMULATED STATE:
{compact_str}

Produce Martin's final daily report as a JSON object with these fields:

•⁠  ⁠"people_encountered": list of objects, one per person Martin interacted with:
    * "name": person's name
    * "relationship": their relationship to Martin
    * "conversation_summary": plain-text summary of what was discussed across all interactions
    * "action_items_for_martin": things Martin agreed to do for/because of this person
    * "action_items_for_them": things this person agreed to do

•⁠  ⁠"martins_decisions": consolidated list of all decisions Martin made today

•⁠  ⁠"martins_action_items": consolidated list of everything Martin needs to do

•⁠  ⁠"calendar_events": the full list of calendar events to create — each with:
    * "type": "meeting" | "reservation" | "ticket" | "event"
    * "title": short descriptive title
    * "with": list of people involved
    * "location": place or platform (null if unknown)
    * "relative_time": time reference as spoken (null if not mentioned)
    * "details": any additional info
    * "context": one sentence on how it came up

•⁠  ⁠"brief_summary": plain-text paragraph (5-8 sentences) — a narrative of Martin's day: who he met, what was discussed, decisions he made, and what's on his calendar

Return ONLY the JSON object — no markdown fences, no extra text."""

        raw = self.chat(prompt)
        raw = raw.strip()
        if raw.startswith("⁠ "):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit(" ⁠", 1)[0]

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
            /app/shared/<name_of_video>evolution/segment<N>.json
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
            "people": {},
            "martins_decisions": [],
            "martins_action_items": [],
            "calendar_events": [],
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