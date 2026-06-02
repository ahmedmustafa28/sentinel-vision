from __future__ import annotations

import json
import logging
from datetime import timezone, datetime
from pathlib import Path
from typing import Any

import httpx

from app.core.config import BASE_DIR, get_settings


class ReportService:
    """Generates surveillance reports using Ollama with Llama 3."""

    def __init__(
        self,
        *,
        ollama_base_url: str | None = None,
        model_name: str | None = None,
        output_dir: str | Path | None = None,
        temperature: float | None = None,
        timeout_seconds: float = 120.0,
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
        self._timeout_seconds = max(10.0, timeout_seconds)

        resolved_output_dir = (
            Path(output_dir)
            if output_dir is not None
            else (BASE_DIR / settings.report_output_dir)
        )
        self._output_dir = resolved_output_dir.resolve()
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def generate_reports(self, events: list[str]) -> dict[str, str]:
        """Generates daily, suspicious activity, and weekly reports."""
        sanitized_events = [event.strip() for event in events if event and event.strip()]

        daily_report = self.generate_daily_report(sanitized_events)
        suspicious_activity_report = self.generate_suspicious_activity_report(sanitized_events)
        weekly_report = self.generate_weekly_report(sanitized_events)

        reports = {
            "daily_report": daily_report,
            "suspicious_activity_report": suspicious_activity_report,
            "weekly_report": weekly_report,
        }

        self._save_reports(reports)
        return reports

    def generate_daily_report(self, events: list[str]) -> str:
        prompt = self._build_report_prompt(
            report_type="Daily Surveillance Report",
            instructions=(
                "Summarize the day chronologically. Highlight entry/exit patterns, "
                "notable incidents, and operational recommendations."
            ),
            events=events,
        )
        return self._generate_text(prompt)

    def generate_suspicious_activity_report(self, events: list[str]) -> str:
        suspicious_events = self._filter_suspicious_events(events)
        prompt = self._build_report_prompt(
            report_type="Suspicious Activity Report",
            instructions=(
                "Focus strictly on risk indicators, unknown individuals, removals, and "
                "anomalies. Include severity assessment (Low/Medium/High) and immediate "
                "recommended actions."
            ),
            events=suspicious_events if suspicious_events else events,
        )
        return self._generate_text(prompt)

    def generate_weekly_report(self, events: list[str]) -> str:
        prompt = self._build_report_prompt(
            report_type="Weekly Surveillance Report",
            instructions=(
                "Provide trend analysis, repeated incidents, operational risk patterns, "
                "and a concise action plan for next week."
            ),
            events=events,
        )
        return self._generate_text(prompt)

    def _generate_text(self, prompt: str) -> str:
        endpoint = f"{self._ollama_base_url}/api/generate"
        payload = {
            "model": self._model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self._temperature,
            },
        }

        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.post(endpoint, json=payload)
                response.raise_for_status()
                data: dict[str, Any] = response.json()
        except Exception as exc:
            self._logger.exception("Failed to generate report via Ollama: %s", exc)
            return self._fallback_report(prompt)

        text = str(data.get("response", "")).strip()
        if not text:
            return self._fallback_report(prompt)

        return text

    def _build_report_prompt(self, *, report_type: str, instructions: str, events: list[str]) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        if events:
            events_block = "\n".join(f"- {item}" for item in events)
        else:
            events_block = "- No events provided"

        return (
            "You are a surveillance analyst writing concise and professional security reports.\n"
            f"Report Type: {report_type}\n"
            f"Generated At: {timestamp}\n"
            "Output Format:\n"
            "1) Executive Summary\n"
            "2) Key Events\n"
            "3) Risk Analysis\n"
            "4) Recommended Actions\n\n"
            f"Instructions: {instructions}\n\n"
            "Event Log:\n"
            f"{events_block}\n"
        )

    def _filter_suspicious_events(self, events: list[str]) -> list[str]:
        suspicious_keywords = {
            "unknown",
            "removed",
            "removal",
            "disappeared",
            "suspicious",
            "intrusion",
            "alert",
            "motion",
            "unauthorized",
        }

        filtered: list[str] = []
        for event in events:
            text = event.lower()
            if any(keyword in text for keyword in suspicious_keywords):
                filtered.append(event)
        return filtered

    def _fallback_report(self, prompt: str) -> str:
        return (
            "Report generation service is temporarily unavailable. "
            "Please verify Ollama is running with model 'llama3' and retry.\n\n"
            "Prompt Snapshot:\n"
            f"{prompt[:1200]}"
        )

    def _save_reports(self, reports: dict[str, str]) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        text_path = self._output_dir / f"ai_reports_{timestamp}.txt"
        json_path = self._output_dir / f"ai_reports_{timestamp}.json"

        text_content = (
            "DAILY REPORT\n"
            f"{reports['daily_report']}\n\n"
            "SUSPICIOUS ACTIVITY REPORT\n"
            f"{reports['suspicious_activity_report']}\n\n"
            "WEEKLY REPORT\n"
            f"{reports['weekly_report']}\n"
        )

        try:
            text_path.write_text(text_content, encoding="utf-8")
            json_path.write_text(json.dumps(reports, indent=2), encoding="utf-8")
        except Exception as exc:
            self._logger.exception("Failed to save report files: %s", exc)
