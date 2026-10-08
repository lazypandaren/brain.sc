"""Localhost-only HTTP UI for neural graph + settings + unlock."""

from __future__ import annotations

import json
import mimetypes
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from brain.cards import add_link, read_card, remove_link
from brain.config import load_user_config, resolve_root, set_root
from brain.errors import BrainError, LockedError
from brain.index import load_index, rebuild_index, search
from brain.paths import is_vault, validate_root_path
from brain.resources import ui_dir
from brain.session import is_unlocked, lock, unlock
from brain import __version__

_REINDEX_LOCK = threading.Lock()


def graph_payload(root: Path) -> dict[str, Any]:
    cards = load_index(root)
    # Undirected degree (outbound + inbound) for hub highlighting
    degree_map: dict[str, int] = {}
    inbound: dict[str, int] = {}
    for c in cards:
        cid = c["id"]
        degree_map.setdefault(cid, 0)
        inbound.setdefault(cid, 0)
        for link in c.get("links") or []:
            degree_map[cid] = degree_map.get(cid, 0) + 1
            degree_map[link] = degree_map.get(link, 0) + 1
            inbound[link] = inbound.get(link, 0) + 1

    nodes = []
    edges = []
    seen = set()
    for c in cards:
        degree = degree_map.get(c["id"], 0)
        out_n = len(c.get("links") or [])
        in_n = inbound.get(c["id"], 0)
        tags = c.get("tags") or []
        nodes.append(
            {
                "id": c["id"],
                "title": c.get("title") or c["id"],
                "tags": tags,
                "tldr": c.get("tldr") or "",
                "secure": bool(c.get("secure")),
                "updated": c.get("updated") or "",
                "hub": "hub" in tags,
                "degree": degree,
                "orphan": out_n == 0 and in_n == 0,
            }
        )
        for link in c.get("links") or []:
            a, b = c["id"], link
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            edges.append({"source": a, "target": b})
    return {"nodes": nodes, "edges": edges, "unlocked": is_unlocked(), "version": __version__}


class BrainHandler(BaseHTTPRequestHandler):
    root: Path
    server_version = "BrainUI/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Avoid logging unlock / set-password paths (sensitive)
        if self.path.startswith("/api/unlock") or self.path.startswith("/api/set-password"):
            return
        super().log_message(fmt, *args)

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").strip().lower()
        if not host:
            return False
        name = host.rsplit(":", 1)[0]
        if name.startswith("[") and name.endswith("]"):
            name = name[1:-1]
        return name in {"127.0.0.1", "localhost", "::1"}

    def _reject_bad_host(self) -> bool:
        if self._host_ok():
            return False
        self._json(403, {"error": "forbidden host"})
        return True

    def _json(self, code: int, obj: Any) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length > 1_000_000:
            raise BrainError("Body too large")
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise BrainError("JSON object required")
        return data

    def do_GET(self) -> None:
        if self._reject_bad_host():
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/status":
                cfg = load_user_config()
                try:
                    cards = len(load_index(self.root)) if is_vault(self.root) else 0
                    root_s = str(self.root) if is_vault(self.root) else None
                except Exception:
                    cards = 0
                    root_s = None
                has_password = False
                if root_s:
                    from brain.config import load_vault_config

                    vcfg = load_vault_config(self.root)
                    has_password = bool(vcfg.get("crypto", {}).get("verifier"))
                self._json(
                    200,
                    {
                        "root": root_s or cfg.get("root"),
                        "unlocked": is_unlocked(),
                        "cards": cards,
                        "config_root": cfg.get("root"),
                        "has_password": has_password,
                        "ready": bool(root_s or (cfg.get("root") and is_vault(Path(str(cfg.get("root")))))),
                        "version": __version__,
                        "ui_running": True,
                    },
                )
                return
            if path == "/api/graph":
                if not is_vault(self.root):
                    self._json(400, {"error": "Vault root not set. Use Settings."})
                    return
                self._json(200, graph_payload(self.root))
                return
            if path == "/api/search":
                qs = urllib.parse.parse_qs(parsed.query)
                q = (qs.get("q") or [""])[0]
                limit = int((qs.get("limit") or ["20"])[0])
                limit = max(1, min(limit, 50))
                results = search(self.root, q, limit=limit)
                if q.strip():
                    from brain.stats import cheap_full_tokens, log_usage, served_tokens_for_results

                    catalog = self.root / "index" / "catalog.md"
                    catalog_tokens = 0
                    if catalog.is_file():
                        from brain.stats import estimate_tokens

                        catalog_tokens = estimate_tokens(catalog.stat().st_size)
                    log_usage(
                        self.root,
                        "search",
                        catalog_tokens + served_tokens_for_results(results),
                        cheap_full_tokens(self.root),
                    )
                self._json(200, {"results": results})
                return
            if path == "/api/stats":
                if not is_vault(self.root):
                    self._json(400, {"error": "Vault root not set. Use Settings."})
                    return
                from brain.stats import vault_stats

                self._json(200, vault_stats(self.root))
                return
            if path == "/api/config":
                cfg = load_user_config()
                self._json(
                    200,
                    {
                        "max_cards_per_query": int(cfg.get("max_cards_per_query", 3)),
                        "default_detail": str(cfg.get("default_detail", "tldr")),
                        "session_ttl_minutes": int(cfg.get("session_ttl_minutes", 60)),
                        "ui_port": int(cfg.get("ui_port", 8765)),
                    },
                )
                return
            if path == "/api/doctor":
                from brain.doctor import run_doctor

                report = run_doctor(self.root if is_vault(self.root) else None)
                self._json(
                    200,
                    {
                        "ok": report.ok,
                        "info": report.info,
                        "warnings": report.warnings,
                        "issues": report.issues,
                    },
                )
                return
            if path.startswith("/api/card/"):
                slug = urllib.parse.unquote(path[len("/api/card/") :])
                card = read_card(self.root, slug)
                from brain.daily import backlinks
                from brain.stats import cheap_full_tokens, estimate_tokens, log_usage

                log_usage(
                    self.root,
                    "get",
                    estimate_tokens(card.body),
                    cheap_full_tokens(self.root),
                )
                self._json(
                    200,
                    {
                        "id": card.id,
                        "title": card.title,
                        "tags": card.tags,
                        "links": card.links,
                        "backlinks": backlinks(self.root, card.id),
                        "tldr": card.tldr,
                        "body": card.body,
                        "secure": card.secure,
                        "updated": card.updated,
                    },
                )
                return
            self._serve_static(path)
        except LockedError as e:
            self._json(403, {"error": str(e)})
        except BrainError as e:
            self._json(400, {"error": str(e)})
        except Exception:
            self._json(500, {"error": "internal error"})

    def do_POST(self) -> None:
        if self._reject_bad_host():
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            body = self._read_json()
            if path == "/api/desktop/show":
                from brain.desktop_ipc import request_show

                request_show()
                self._json(200, {"ok": True, "show": True})
                return
            if path == "/api/unlock":
                password = str(body.get("password") or "")
                unlock(self.root, password)
                rebuild_index(self.root)
                self._json(200, {"ok": True, "unlocked": True})
                return
            if path == "/api/set-password":
                from brain.config import load_vault_config
                from brain.session import unlock as unlock_sess

                if not is_vault(self.root):
                    self._json(400, {"error": "Vault root not set. Use Settings."})
                    return
                vcfg = load_vault_config(self.root)
                if vcfg.get("crypto", {}).get("verifier"):
                    self._json(400, {"error": "Master password already set. Use Unlock."})
                    return
                password = str(body.get("password") or "")
                confirm = str(body.get("confirm") or "")
                if len(password) < 6:
                    self._json(400, {"error": "Пароль закороткий (мінімум 6 символів)"})
                    return
                if password != confirm:
                    self._json(400, {"error": "Паролі не збігаються"})
                    return
                # First-time only — allow_init writes verifier
                unlock_sess(self.root, password, allow_init=True)
                rebuild_index(self.root)
                self._json(200, {"ok": True, "unlocked": True, "created": True})
                return
            if path == "/api/lock":
                lock()
                rebuild_index(self.root)
                self._json(200, {"ok": True, "unlocked": False})
                return
            if path == "/api/set-root":
                raw = str(body.get("path") or "")
                # create=True (default): init vault in Google Drive folder if missing
                create = body.get("create", True)
                if create is None:
                    create = True
                create = bool(create)
                root = validate_root_path(raw, must_exist=False)
                created = False
                if not root.exists():
                    if not create:
                        self._json(400, {"error": f"Path does not exist: {root}"})
                        return
                    root.mkdir(parents=True, exist_ok=True)
                if not root.is_dir():
                    self._json(400, {"error": f"Path is not a directory: {root}"})
                    return
                if not is_vault(root):
                    if not create:
                        self._json(
                            400,
                            {
                                "error": f"Not a vault: {root}",
                                "hint": "Send create=true to initialize vault in this folder",
                            },
                        )
                        return
                    from brain.errors import VaultError
                    from brain.vault import init_vault

                    try:
                        root = init_vault(root)
                        created = True
                    except VaultError:
                        if is_vault(root):
                            set_root(root, require_vault=True)
                            created = False
                        else:
                            raise
                    except Exception as e:
                        if is_vault(root):
                            set_root(root, require_vault=True)
                            created = False
                        else:
                            raise BrainError(
                                f"Cannot create vault in {root}: {e}. "
                                "Choose a writable Google Drive folder."
                            ) from e
                else:
                    set_root(root, require_vault=True)
                self.root = root
                BrainHandler.root = root
                self._json(200, {"ok": True, "root": str(root), "created": created})
                return
            if path == "/api/config":
                from brain.config import save_user_config

                cfg = load_user_config()
                if "max_cards_per_query" in body:
                    cfg["max_cards_per_query"] = max(1, min(10, int(body["max_cards_per_query"])))
                if "default_detail" in body:
                    detail = str(body["default_detail"])
                    if detail not in ("tldr", "full"):
                        self._json(400, {"error": "default_detail must be tldr|full"})
                        return
                    cfg["default_detail"] = detail
                if "session_ttl_minutes" in body:
                    cfg["session_ttl_minutes"] = max(5, min(480, int(body["session_ttl_minutes"])))
                if "ui_port" in body:
                    port = int(body["ui_port"])
                    if not (1024 <= port <= 65535):
                        self._json(400, {"error": "ui_port must be 1024–65535"})
                        return
                    cfg["ui_port"] = port
                save_user_config(cfg)
                self._json(200, {"ok": True})
                return
            if path == "/api/usage-reset":
                if not is_vault(self.root):
                    self._json(400, {"error": "Vault root not set. Use Settings."})
                    return
                from brain.stats import activity_path, usage_path

                usage_path(self.root).unlink(missing_ok=True)
                activity_path(self.root).unlink(missing_ok=True)
                self._json(200, {"ok": True})
                return
            if path == "/api/reindex":
                if not is_vault(self.root):
                    self._json(400, {"error": "Vault root not set. Use Settings."})
                    return
                with _REINDEX_LOCK:
                    n = len(rebuild_index(self.root))
                self._json(200, {"ok": True, "indexed": n})
                return
            if path == "/api/reveal-root":
                if not is_vault(self.root):
                    self._json(400, {"error": "Vault root not set. Use Settings."})
                    return
                from brain.feedback import reveal_in_finder

                reveal_in_finder(self.root)
                self._json(200, {"ok": True})
                return
            if path == "/api/agents-install":
                from brain.agents_install import install_claude, install_codex, install_cursor

                targets = body.get("targets") or ["cursor", "codex", "claude"]
                installed: dict[str, str] = {}
                if "cursor" in targets:
                    installed["cursor"] = str(install_cursor())
                if "codex" in targets:
                    installed["codex"] = str(install_codex())
                if "claude" in targets:
                    installed["claude"] = str(install_claude())
                self._json(200, {"ok": True, "installed": installed})
                return
            if path == "/api/feedback":
                if not is_vault(self.root):
                    self._json(400, {"error": "Vault root not set. Use Settings."})
                    return
                from brain.feedback import reveal_in_finder, save_feedback

                answers = body.get("answers") or {}
                comments = str(body.get("comments") or "")
                saved = save_feedback(self.root, answers, comments)
                reveal_in_finder(saved)
                self._json(200, {"ok": True, "path": str(saved)})
                return
            if path == "/api/import-folder":
                if not is_vault(self.root):
                    self._json(400, {"error": "Vault root not set. Use Settings."})
                    return
                from brain.importer import import_folder

                folder = str(body.get("path") or "")
                result = import_folder(self.root, folder)
                self._json(200, {"ok": True, **result})
                return
            if path == "/api/import-topics":
                if not is_vault(self.root):
                    self._json(400, {"error": "Vault root not set. Use Settings."})
                    return
                from brain.importer import import_topics

                folder = str(body.get("path") or "")
                if not folder:
                    self._json(400, {"error": "path required (absolute path to docs/topics)"})
                    return
                tag = str(body.get("tag") or "elseveir-topic")
                result = import_topics(self.root, folder, tag=tag)
                self._json(200, {"ok": True, **result})
                return
            if path == "/api/remember":
                if not is_vault(self.root):
                    self._json(400, {"error": "Vault root not set. Use Settings."})
                    return
                from brain.recipes import remember

                note = str(body.get("note") or "")
                source = str(body.get("source") or "ui")
                remember(self.root, note, source=source)
                self._json(200, {"ok": True})
                return
            if path == "/api/add":
                if not is_vault(self.root):
                    self._json(400, {"error": "Vault root not set. Use Settings."})
                    return
                from brain.cards import Card, write_card
                from brain.importer import slugify

                slug = str(body.get("id") or body.get("slug") or "").strip()
                title = str(body.get("title") or "").strip()
                tldr = str(body.get("tldr") or "").strip()
                tags_raw = body.get("tags") or []
                if isinstance(tags_raw, str):
                    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                else:
                    tags = [str(t).strip() for t in tags_raw if str(t).strip()]
                if not slug:
                    slug = slugify(title or tldr or "note")
                if not title:
                    title = slug
                if not tldr:
                    tldr = title
                body_md = f"# TL;DR\n{tldr}\n\n## Details\n\n{str(body.get('body') or tldr)}\n"
                write_card(
                    self.root,
                    Card(id=slug, title=title, tags=tags or ["inbox"], body=body_md),
                )
                rebuild_index(self.root)
                self._json(200, {"ok": True, "id": slug})
                return
            if path == "/api/daily":
                if not is_vault(self.root):
                    self._json(400, {"error": "Vault root not set. Use Settings."})
                    return
                from datetime import date as date_cls

                from brain.daily import ensure_daily

                raw = str(body.get("date") or "").strip()
                day = date_cls.fromisoformat(raw) if raw else None
                card = ensure_daily(self.root, day)
                self._json(
                    200,
                    {
                        "ok": True,
                        "id": card.id,
                        "title": card.title,
                        "tldr": card.tldr,
                    },
                )
                return
            if path == "/api/link":
                if not is_vault(self.root):
                    self._json(400, {"error": "Vault root not set. Use Settings."})
                    return
                a = str(body.get("a") or "")
                b = str(body.get("b") or "")
                add_link(self.root, a, b)
                rebuild_index(self.root)
                self._json(200, {"ok": True, "a": a, "b": b})
                return
            if path == "/api/unlink":
                if not is_vault(self.root):
                    self._json(400, {"error": "Vault root not set. Use Settings."})
                    return
                a = str(body.get("a") or "")
                b = str(body.get("b") or "")
                remove_link(self.root, a, b)
                rebuild_index(self.root)
                self._json(200, {"ok": True, "a": a, "b": b})
                return
            self._json(404, {"error": "not found"})
        except LockedError as e:
            self._json(403, {"error": str(e)})
        except BrainError as e:
            self._json(400, {"error": str(e)})
        except Exception:
            self._json(500, {"error": "internal error"})

    def _serve_static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"
        # Only files under UI_DIR
        rel = path.lstrip("/")
        if ".." in rel or rel.startswith("/"):
            self._json(400, {"error": "bad path"})
            return
        base = ui_dir().resolve()
        file_path = (base / rel).resolve()
        try:
            file_path.relative_to(base)
        except ValueError:
            self._json(400, {"error": "bad path"})
            return
        if not file_path.is_file():
            self.send_error(404)
            return
        ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run_ui(root: Path | None = None, port: int | None = None) -> None:
    cfg = load_user_config()
    port = port or int(cfg.get("ui_port", 8765))
    if root is None:
        try:
            root = resolve_root()
        except BrainError:
            # Allow Settings/setup wizard; APIs that need vault will error clearly
            root = Path("/tmp/brain-unset")
    BrainHandler.root = root
    # CRITICAL: loopback only
    httpd = ThreadingHTTPServer(("127.0.0.1", port), BrainHandler)
    print(f"Brain UI: http://127.0.0.1:{port}/  (root={root})")
    print("Press Ctrl+C to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        httpd.server_close()
