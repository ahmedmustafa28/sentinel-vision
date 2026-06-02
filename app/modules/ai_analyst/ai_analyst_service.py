from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from sqlalchemy.orm import Session

from app.core.config import BASE_DIR, get_settings
from app.db import crud_event


class AIAnalystService:
    """Analyzes surveillance events and produces a structured risk assessment using Ollama.

    Output format (JSON):
    {
      "risk_level": "Low|Medium|High",
      "risk_score": 0-100,
      "summary": "...",
      "reasoning": "...",
      "recommended_action": "..."
    }
    """

    def __init__(
        self,
        *,
        ollama_base_url: str | None = None,
        model_name: str | None = None,
        output_dir: str | Path | None = None,
        temperature: float | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        settings = get_settings()

        self._logger = logging.getLogger(self.__class__.__name__)
        self._ollama_base_url = (ollama_base_url or settings.ollama_base_url).rstrip("/")
        self._model_name = model_name or settings.ollama_model
        self._temperature = (
            max(0.0, min(1.0, temperature))
            if temperature is not None
            else max(0.0, min(1.0, settings.report_llm_temperature))
        )
        self._timeout_seconds = max(5.0, timeout_seconds)

        resolved_output_dir = (
            Path(output_dir) if output_dir is not None else (BASE_DIR / settings.report_output_dir)
        )
        self._output_dir = resolved_output_dir.resolve()
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def analyze_events(
        self,
        events: list[str] | None = None,
        *,
        db: Session | None = None,
        hours: int | None = 24,
    ) -> dict[str, Any]:
        """Analyze a list of event descriptions or load from DB for the last `hours`.

        Returns a dict with keys: `risk_level`, `risk_score`, `summary`, `reasoning`, `recommended_action`.
        """
        sanitized: list[str] = []
        if events:
            sanitized = [e.strip() for e in events if e and e.strip()]
        elif db is not None:
            since = None
            if hours is not None:
                since = datetime.now(timezone.utc) - timedelta(hours=hours)
            raw = self._load_events_from_db(db, since=since)
            sanitized = [self._format_event_short(e) for e in raw]

        prompt = self._build_prompt(events=sanitized, hours=hours)
        result = self._generate_structured_analysis(prompt)

        # Persist a JSON-backed snapshot for auditing
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            out_path = self._output_dir / f"ai_analyst_{timestamp}.json"
            out_path.write_text(json.dumps({"input_events": sanitized, "analysis": result}, indent=2), encoding="utf-8")
        except Exception:
            self._logger.exception("Failed to save analyst output file")

        return result

    def _load_events_from_db(self, db: Session, since: datetime | None = None) -> list[dict]:
        # Use crud_event.list_events to fetch recent events; translate to dicts
        events = crud_event.list_events(db, skip=0, limit=500)
        results = []
        for e in events:
            if since is not None and e.timestamp is not None and e.timestamp < since:
                continue
            results.append({
                "id": int(e.id),
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "event_type": e.event_type,
                "description": e.description,
                "camera_id": e.camera_id,
                "image_path": e.image_path,
            })
        return results

    def _format_event_short(self, event: dict) -> str:
        ts = event.get("timestamp") or "unknown time"
        et = event.get("event_type") or "event"
        desc = event.get("description") or ""
        cam = event.get("camera_id")
        return f"[{ts}] (camera {cam}) {et}: {desc}".strip()

    def _build_prompt(self, *, events: list[str], hours: int | None) -> str:
        timeframe = f"last {hours} hours" if hours else "all available events"
        header = (
            "You are a senior security analyst. Evaluate the provided surveillance event log "
            f"({timeframe}) and produce a single JSON object with the following fields:\n"
            "- risk_level: one of Low, Medium, High\n"
            "- risk_score: integer 0-100 (higher = more risky)\n"
            "- summary: concise executive summary (1-3 sentences)\n"
            "- reasoning: detailed bullet-style reasoning that maps events to risks\n"
            "- recommended_action: concrete next steps for security/ops\n\n"
            "Output MUST be valid JSON only, nothing else.\n\n"
        )

        events_block = "\n".join(f"- {e}" for e in events) if events else "- No events provided"

        prompt = header + "Event Log:\n" + events_block + "\n"
        return prompt

    def _generate_structured_analysis(self, prompt: str) -> dict[str, Any]:
        endpoint = f"{self._ollama_base_url}/api/generate"
        payload = {
            "model": self._model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self._temperature},
        }

        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                resp = client.post(endpoint, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            self._logger.exception("Ollama call failed: %s", exc)
            return self._fallback_analysis(prompt)

        text = str(data.get("response", "")).strip()
        if not text:
            return self._fallback_analysis(prompt)

        # Try to parse JSON from model response. Be tolerant of leading/trailing text.
        try:
            parsed = json.loads(text)
            return self._normalize_output(parsed)
        except Exception:
            # Attempt to extract JSON substring
            try:
                start = text.index("{")
                end = text.rindex("}") + 1
                snippet = text[start:end]
                parsed = json.loads(snippet)
                return self._normalize_output(parsed)
            except Exception:
                self._logger.exception("Failed to parse JSON from model response. Raw: %s", text[:1000])
                return self._fallback_analysis(prompt)

    def _normalize_output(self, parsed: dict[str, Any]) -> dict[str, Any]:
        # Ensure keys and types
        risk_level = str(parsed.get("risk_level", "Low")).title()
        if risk_level not in {"Low", "Medium", "High"}:
            # map common variants
            low = {"low", "low risk"}
            med = {"medium", "moderate", "medium risk"}
            high = {"high", "high risk", "severe"}
            r = str(parsed.get("risk_level", "")).lower()
            if r in high:
                risk_level = "High"
            elif r in med:
                risk_level = "Medium"
            else:
                risk_level = "Low"

        try:
            score_raw = parsed.get("risk_score", 0)
            score = int(float(score_raw))
            score = max(0, min(100, score))
        except Exception:
            score = 0

        return {
            "risk_level": risk_level,
            "risk_score": score,
            "summary": str(parsed.get("summary", "")) or "No summary provided.",
            "reasoning": str(parsed.get("reasoning", "")) or "No reasoning provided.",
            "recommended_action": str(parsed.get("recommended_action", "")) or "No recommended action provided.",
        }

    def _fallback_analysis(self, prompt: str) -> dict[str, Any]:
        return {
            "risk_level": "Low",
            "risk_score": 0,
            "summary": "Analysis service unavailable. Ensure Ollama is running and reachable.",
            "reasoning": "Unable to contact LLM endpoint.",
            "recommended_action": "Start Ollama with the configured model and retry.",
        }
