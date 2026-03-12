from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


DB_PATH = Path(os.getenv("POSTLAYER_API_DB_PATH", "postlayer.db"))


def dict_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = dict_factory
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_cursor(commit: bool = False) -> Iterator[sqlite3.Cursor]:
    conn = connect()
    cur = conn.cursor()
    try:
        yield cur
        if commit:
            conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_cursor(commit=True) as cur:
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id TEXT PRIMARY KEY,
              email TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              full_name TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS organizations (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              slug TEXT NOT NULL UNIQUE,
              logo_url TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS organization_members (
              id TEXT PRIMARY KEY,
              organization_id TEXT NOT NULL,
              user_id TEXT NOT NULL,
              role TEXT NOT NULL DEFAULT 'member',
              created_at TEXT NOT NULL,
              UNIQUE(organization_id, user_id),
              FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS brand_settings (
              id TEXT PRIMARY KEY,
              organization_id TEXT NOT NULL UNIQUE,
              primary_color TEXT NOT NULL DEFAULT '#3B82F6',
              secondary_color TEXT NOT NULL DEFAULT '#8B5CF6',
              accent_color TEXT NOT NULL DEFAULT '#F59E0B',
              font_heading TEXT NOT NULL DEFAULT 'Inter',
              font_body TEXT NOT NULL DEFAULT 'Inter',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS posts (
              id TEXT PRIMARY KEY,
              organization_id TEXT NOT NULL,
              title TEXT NOT NULL,
              format TEXT NOT NULL,
              width INTEGER NOT NULL,
              height INTEGER NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
              FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS post_layers (
              id TEXT PRIMARY KEY,
              post_id TEXT NOT NULL,
              type TEXT NOT NULL,
              z_index INTEGER NOT NULL DEFAULT 0,
              properties TEXT NOT NULL DEFAULT '{}',
              visible INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS templates (
              id TEXT PRIMARY KEY,
              organization_id TEXT,
              name TEXT NOT NULL,
              category TEXT NOT NULL DEFAULT 'geral',
              format TEXT NOT NULL DEFAULT '1:1',
              thumbnail_url TEXT,
              layers TEXT NOT NULL DEFAULT '[]',
              is_public INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE
            );
            """
        )
    seed_templates()


def seed_templates() -> None:
    with get_cursor(commit=True) as cur:
        row = cur.execute("SELECT COUNT(*) AS total FROM templates").fetchone()
        if row and row["total"] > 0:
            return

        now = utcnow()
        templates = [
            {
                "id": str(uuid.uuid4()),
                "name": "Promo Clean",
                "category": "promocional",
                "format": "1:1",
                "layers": json.dumps(
                    [
                        {"type": "background", "visible": True, "properties": {"color": "#0F172A", "imageUrl": ""}},
                        {"type": "text", "visible": True, "properties": {"content": "Oferta da semana", "fontFamily": "Space Grotesk", "fontSize": 64, "fontWeight": "bold", "color": "#FFFFFF", "x": 50, "y": 45, "textAlign": "center", "shadow": True}},
                    ]
                ),
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Story Bold",
                "category": "stories",
                "format": "9:16",
                "layers": json.dumps(
                    [
                        {"type": "background", "visible": True, "properties": {"color": "#1D4ED8", "imageUrl": ""}},
                        {"type": "overlay", "visible": True, "properties": {"color": "#000000", "opacity": 0.25}},
                        {"type": "text", "visible": True, "properties": {"content": "Lance hoje", "fontFamily": "Montserrat", "fontSize": 72, "fontWeight": "800", "color": "#FFFFFF", "x": 50, "y": 50, "textAlign": "center", "shadow": True}},
                    ]
                ),
            },
        ]
        for template in templates:
            cur.execute(
                """
                INSERT INTO templates (
                  id, organization_id, name, category, format, thumbnail_url, layers, is_public, created_at, updated_at
                ) VALUES (?, NULL, ?, ?, ?, NULL, ?, 1, ?, ?)
                """,
                (template["id"], template["name"], template["category"], template["format"], template["layers"], now, now),
            )


def json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    return json.loads(value)
