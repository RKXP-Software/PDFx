"""Preferências persistentes: arquivos recentes e estado de cada documento (página, zoom...)."""

from __future__ import annotations

import hashlib
import json
import os

from PySide6.QtCore import QSettings

MAX_RECENT = 30


def normalize(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


class Settings:
    def __init__(self) -> None:
        self._q = QSettings("PDFx", "PDFx")

    # ---- valores genéricos ------------------------------------------------
    def value(self, key: str, default=None, type_=None):
        if type_ is None:
            return self._q.value(key, default)
        return self._q.value(key, default, type=type_)

    def set_value(self, key: str, value) -> None:
        self._q.setValue(key, value)

    # ---- arquivos recentes --------------------------------------------------
    def recent_files(self) -> list[str]:
        raw = self._q.value("recent_files", [])
        if raw is None:
            return []
        if isinstance(raw, str):
            raw = [raw] if raw else []
        return [p for p in raw if isinstance(p, str) and p]

    def add_recent(self, path: str) -> None:
        path = os.path.abspath(path)
        items = [p for p in self.recent_files() if normalize(p) != normalize(path)]
        items.insert(0, path)
        self._q.setValue("recent_files", items[:MAX_RECENT])

    def remove_recent(self, path: str) -> None:
        items = [p for p in self.recent_files() if normalize(p) != normalize(path)]
        self._q.setValue("recent_files", items)

    # ---- estado por documento ----------------------------------------------
    @staticmethod
    def _doc_key(path: str) -> str:
        return "documents/" + hashlib.sha1(normalize(path).encode("utf-8")).hexdigest()

    def document_state(self, path: str) -> dict:
        raw = self._q.value(self._doc_key(path))
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def save_document_state(self, path: str, state: dict) -> None:
        data = self.document_state(path)
        data.update(state)
        self._q.setValue(self._doc_key(path), json.dumps(data))

    def bookmarks(self, path: str) -> list[dict]:
        items = self.document_state(path).get("bookmarks", [])
        return [b for b in items if isinstance(b, dict) and isinstance(b.get("page"), int)]

    def set_bookmarks(self, path: str, items: list[dict]) -> None:
        self.save_document_state(path, {"bookmarks": items})
