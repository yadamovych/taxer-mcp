"""Tests for scripts/create_gmail_draft_with_attachment.py (no live Gmail)."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "create_gmail_draft_with_attachment.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("gmail_draft_script", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_missing_env_prints_json_error(capsys):
    mod = _load_module()
    for name in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"):
        os.environ.pop(name, None)
    with pytest.raises(SystemExit) as exc:
        mod._require_env()
    assert exc.value.code == 1
    err = json.loads(capsys.readouterr().err)
    assert "error" in err
    assert "GMAIL" in err["error"]


def test_missing_pdf_prints_json_error(tmp_path, monkeypatch, capsys):
    mod = _load_module()
    monkeypatch.setenv("GMAIL_CLIENT_ID", "id")
    monkeypatch.setenv("GMAIL_CLIENT_SECRET", "secret")
    monkeypatch.setenv("GMAIL_REFRESH_TOKEN", "refresh")
    body = tmp_path / "body.txt"
    body.write_text("hi", encoding="utf-8")
    missing = tmp_path / "nope.pdf"
    argv = [
        "create_gmail_draft_with_attachment.py",
        "--to",
        "a@example.com",
        "--subject",
        "S",
        "--body-file",
        str(body),
        "--pdf",
        str(missing),
        "--filename",
        "x.pdf",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
    err = json.loads(capsys.readouterr().err)
    assert "PDF not found" in err["error"]
