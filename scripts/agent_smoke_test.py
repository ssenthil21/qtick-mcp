#!/usr/bin/env python3
"""Run a quick agent smoke test against the local FastAPI service."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
import app.tools.agent as agent_module


def _ensure_api_key() -> None:
    settings = get_settings()
    if settings.google_api_key:
        # Settings already exposes the key through QTICK_GOOGLE_API_KEY.
        os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
    elif not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError(
            "GOOGLE_API_KEY environment variable is required for the smoke test."
        )


def _format_data_points(data_points: Any) -> str:
    if not data_points:
        return "[]"
    try:
        return json.dumps(data_points, indent=2, ensure_ascii=False)
    except TypeError:
        return str(data_points)


def run_smoke_test(prompt: str, request_timeout: float) -> Dict[str, Any]:
    """Execute the /agent/run endpoint with the provided prompt."""

    # Ensure configuration changes are respected between runs.
    get_settings.cache_clear()
    agent_module._get_agent_bundle.cache_clear()

    _ensure_api_key()

    settings = get_settings()
    print(
        f"Running smoke test with model '{settings.agent_google_model}' at "
        f"{settings.mcp_base_url}"
    )

    with TestClient(app) as client:
        response = client.post(
            "/agent/run",
            json={"prompt": prompt},
            timeout=request_timeout,
        )

    if response.status_code != 200:
        raise RuntimeError(
            f"Agent run failed ({response.status_code}): {response.text}"
        )

    payload: Dict[str, Any] = response.json()
    print("Model response:")
    print(payload.get("output", "<no output>"))

    print("\nTool triggered:")
    print(payload.get("tool"))

    print("\nData points:")
    print(_format_data_points(payload.get("dataPoints")))

    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a smoke test against the local agent service. The test sends a "
            "prompt through the /agent/run endpoint using the configured Gemini "
            "model."
        )
    )
    parser.add_argument(
        "--prompt",
        default="Summarize the purpose of the QTick MCP service in one sentence.",
        help="Prompt to send to the agent during the smoke test.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Timeout (in seconds) for the agent HTTP request.",
    )

    args = parser.parse_args(argv)

    try:
        run_smoke_test(args.prompt, args.timeout)
    except Exception as exc:  # pragma: no cover - manual diagnostic utility
        print(f"Smoke test failed: {exc}", file=sys.stderr)
        return 1

    print("\nSmoke test completed successfully.")
    return 0


if __name__ == "__main__":  # pragma: no cover - manual diagnostic utility
    raise SystemExit(main())
