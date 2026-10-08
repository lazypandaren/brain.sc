"""brain CLI entrypoint."""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import date
from pathlib import Path

from brain import __version__
from brain.cards import Card, add_link, read_card, remove_link, write_card
from brain.config import load_user_config, resolve_root, set_root
from brain.doctor import run_doctor
from brain.errors import BrainError
from brain.index import rebuild_index, search
from brain.session import is_unlocked, lock, unlock
from brain.vault import init_vault
from brain.agents_install import install_claude, install_codex, install_cursor
from brain.recipes import get_recipe, list_recipes, remember, run_recipe, write_catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="brain", description="Knowledge Brain CLI")
    parser.add_argument("--version", action="version", version=f"brain {__version__}")
    parser.add_argument("--root", help="Override vault root for this command")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Create vault and set as root")
    p_init.add_argument("path", help="Absolute path for vault (e.g. Google Drive folder)")
    p_init.add_argument("--password", help="Optional master password (or prompt)")

    p_set = sub.add_parser("set-root", help="Point config at existing vault")
    p_set.add_argument("path")

    sub.add_parser("path", help="Show configured root")
    sub.add_parser("status", help="Status summary")
    sub.add_parser("doctor", help="Validate vault health")

    p_search = sub.add_parser("search", help="Search cards")
    p_search.add_argument("query")
    p_search.add_argument("-n", "--limit", type=int, default=None)

    p_get = sub.add_parser("get", help="Get card TL;DR (or --full)")
    p_get.add_argument("slug")
    p_get.add_argument("--full", action="store_true")

    p_add = sub.add_parser("add", help="Add a card")
    p_add.add_argument("slug")
    p_add.add_argument("--title", default="")
    p_add.add_argument("--tag", action="append", default=[])
    p_add.add_argument("--tldr", default="")
    p_add.add_argument("--secure", action="store_true")
    p_add.add_argument(
        "--hub",
        default=None,
        help="Link to hub slug after write (or 'auto' to suggest from title/tldr)",
    )

    p_hub = sub.add_parser("hub", help="Project hubs (tag hub) — list / init / suggest")
    hub_sub = p_hub.add_subparsers(dest="hub_cmd", required=True)
    hub_sub.add_parser("list", help="List cards with tag hub + aliases")
    p_hub_init = hub_sub.add_parser("init", help="Create/refresh a project hub card")
    p_hub_init.add_argument("slug")
    p_hub_init.add_argument("--title", default="")
    p_hub_init.add_argument(
        "--aliases",
        default="",
        help="Comma-separated aliases for AI search (repo, product, ticket prefix)",
    )
    p_hub_init.add_argument("--project", default="")
    p_hub_init.add_argument("--blurb", default="")
    p_hub_suggest = hub_sub.add_parser(
        "suggest", help="Suggest hub(s) for free text (write-back helper)"
    )
    p_hub_suggest.add_argument("text")
    p_hub_suggest.add_argument("-n", "--limit", type=int, default=3)

    p_link = sub.add_parser("link", help="Link two cards")
    p_link.add_argument("a")
    p_link.add_argument("b")
    p_unlink = sub.add_parser("unlink", help="Remove link between two cards")
    p_unlink.add_argument("a")
    p_unlink.add_argument("b")

    p_active = sub.add_parser("active", help="Show or set active note line")
    p_active.add_argument("--set", dest="set_line", default=None)

    sub.add_parser("reindex", help="Rebuild search.json")
    p_unlock = sub.add_parser("unlock", help="Unlock secure cards")
    p_unlock.add_argument("--password", default=None)
    sub.add_parser("lock", help="Lock secure session")

    p_passwd = sub.add_parser("passwd", help="Change master password (re-encrypt secure/)")
    p_passwd.add_argument("--old", default=None)
    p_passwd.add_argument("--new", default=None)

    p_ui = sub.add_parser("ui", help="Start localhost neural UI (HTTP only)")
    p_ui.add_argument("--port", type=int, default=None)

    p_desktop = sub.add_parser("desktop", help="Native app window (pywebview)")
    p_desktop.add_argument("--port", type=int, default=None)

    p_auto = sub.add_parser("autostart", help="Login LaunchAgent for Brain UI (macOS)")
    p_auto.add_argument("action", choices=["on", "off", "status"])

    p_up = sub.add_parser(
        "upgrade",
        help="In-place upgrade from BrainTools-*.pkg (no uninstall / vault untouched)",
    )
    p_up.add_argument("--pkg", default=None, help="Path to .pkg (else auto-find)")
    p_up.add_argument("--dry-run", action="store_true")

    p_agents = sub.add_parser(
        "agents",
        help="Install model-native instructions (Codex AGENTS.md, Claude CLAUDE.md)",
    )
    ag = p_agents.add_subparsers(dest="agents_cmd", required=True)
    p_ag_install = ag.add_parser("install", help="Merge snippets into global agent configs")
    p_ag_install.add_argument("--codex", action="store_true", help="~/.codex/AGENTS.md")
    p_ag_install.add_argument("--claude", action="store_true", help="~/.claude/CLAUDE.md")
    p_ag_install.add_argument("--cursor", action="store_true", help="~/.cursor/skills/brain/SKILL.md")
    p_ag_install.add_argument("--all", action="store_true", help="Codex + Claude + Cursor")

    sub.add_parser("catalog", help="Print lean index/catalog.md (token-cheap)")

    p_remember = sub.add_parser("remember", help="Append short learning to core/memory.md")
    p_remember.add_argument("note")
    p_remember.add_argument("--source", default="session")

    p_recipe = sub.add_parser("recipe", help="List/show/run automation recipes")
    rs = p_recipe.add_subparsers(dest="recipe_cmd", required=True)
    rs.add_parser("list", help="List recipes")
    p_rshow = rs.add_parser("show", help="Show recipe instructions")
    p_rshow.add_argument("id")
    p_rrun = rs.add_parser("run", help="Run built-in steps + print manual steps")
    p_rrun.add_argument("id")

    p_import = sub.add_parser("import", help="Import a folder of .md files as cards")
    p_import.add_argument("folder", help="Absolute path to folder with .md files")
    p_import.add_argument("--tag", default="imported")

    p_topics = sub.add_parser(
        "import-topics",
        help="Import topic notes as summary cards (e.g. elseveir docs/topics)",
    )
    p_topics.add_argument(
        "folder",
        help="Absolute path to a topics folder of .md files",
    )
    p_topics.add_argument("--tag", default="elseveir-topic")

    p_daily = sub.add_parser("daily", help="Open or create today's daily note card")
    p_daily.add_argument(
        "--date",
        dest="day",
        default=None,
        help="ISO date YYYY-MM-DD (default: today)",
    )

    sub.add_parser("stats", help="Token-economy and vault health stats")
    args = parser.parse_args(argv)
    try:
        return dispatch(args)
    except BrainError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def _root(args: argparse.Namespace) -> Path:
    return resolve_root(getattr(args, "root", None))


def dispatch(args: argparse.Namespace) -> int:
    cmd = args.cmd
    if cmd == "init":
        pw = args.password
        if pw is None:
            # optional
            use = input("Set master password now? [y/N]: ").strip().lower()
            if use == "y":
                pw = getpass.getpass("Master password: ")
                pw2 = getpass.getpass("Confirm: ")
                if pw != pw2:
                    raise BrainError("Passwords do not match")
        root = init_vault(args.path, master_password=pw or None)
        print(f"Initialized vault: {root}")
        return 0

    if cmd == "set-root":
        root = set_root(args.path)
        print(f"root={root}")
        return 0

    if cmd == "path":
        cfg = load_user_config()
        print(cfg.get("root") or "(not set)")
        if cfg.get("root"):
            try:
                print(f"resolved={resolve_root()}")
            except BrainError as e:
                print(f"warning: {e}")
        return 0

    if cmd == "status":
        from brain import __version__
        from brain.index import load_index
        from brain.service import ui_is_running, ui_port

        root = _root(args)
        port = ui_port()
        print(f"version={__version__}")
        print(f"root={root}")
        print(f"unlocked={is_unlocked()}")
        print(f"cards={len(load_index(root))}")
        print(f"ui_port={port}")
        print(f"ui_running={ui_is_running(port)}")
        return 0

    if cmd == "doctor":
        report = run_doctor(_root(args) if getattr(args, "root", None) else None)
        for line in report.info:
            print(f"info: {line}")
        for line in report.warnings:
            print(f"warn: {line}")
        for line in report.issues:
            print(f"fail: {line}")
        print("OK" if report.ok else "FAILED")
        return 0 if report.ok else 2

    if cmd == "search":
        root = _root(args)
        cfg = load_user_config()
        limit = args.limit or int(cfg.get("max_cards_per_query", 3))
        for c in search(root, args.query, limit=limit):
            sec = " [secure]" if c.get("secure") else ""
            print(f"{c['id']}{sec}\t{c.get('title')}\t{c.get('tldr', '')[:80]}")
        return 0

    if cmd == "get":
        root = _root(args)
        card = read_card(root, args.slug)
        print(f"# {card.title} ({card.id})")
        print(card.tldr if not args.full else card.body)
        if card.links:
            print("links: " + ", ".join(card.links))
        from brain.daily import backlinks

        bl = backlinks(root, card.id)
        if bl:
            print("backlinks: " + ", ".join(b["id"] for b in bl))
        return 0

    if cmd == "add":
        root = _root(args)
        if args.secure and not is_unlocked():
            raise BrainError("Unlock first: brain unlock")
        from brain.hubs import ensure_hub_link, suggest_hubs

        title = args.title or args.slug.replace("-", " ").title()
        tldr = args.tldr or title
        card = Card(
            id=args.slug,
            title=title,
            tags=args.tag,
            secure=bool(args.secure),
            body=f"# TL;DR\n{tldr}\n\n## Details\n\n",
            updated=date.today().isoformat(),
        )
        path = write_card(root, card)
        hub_arg = (getattr(args, "hub", None) or "").strip()
        if hub_arg:
            hub_id = hub_arg
            if hub_arg.lower() == "auto":
                hits = suggest_hubs(root, f"{title}\n{tldr}", limit=1)
                if not hits:
                    rebuild_index(root)
                    print(f"wrote {path}")
                    print("hub_suggest=(none)")
                    return 0
                hub_id = hits[0]["id"]
                print(f"hub_suggest={hub_id} score={hits[0]['score']}")
            ensure_hub_link(root, args.slug, hub_id)
            print(f"linked → hub {hub_id}")
        else:
            hits = suggest_hubs(root, f"{title}\n{tldr}", limit=2)
            if hits:
                print(
                    "hub_suggest: "
                    + ", ".join(f"{h['id']}({h['score']})" for h in hits)
                    + "  # use --hub auto|<slug>"
                )
        rebuild_index(root)
        print(f"wrote {path}")
        return 0

    if cmd == "hub":
        from brain.hubs import create_hub, list_hubs, suggest_hubs

        root = _root(args)
        if args.hub_cmd == "list":
            hubs = list_hubs(root)
            if not hubs:
                print("(no hub-tagged cards)")
                return 0
            for h in hubs:
                aliases = ", ".join(h.aliases[:8])
                print(f"{h.id}\t{h.title}\t{aliases}")
            return 0
        if args.hub_cmd == "init":
            aliases = [a.strip() for a in (args.aliases or "").split(",") if a.strip()]
            card = create_hub(
                root,
                args.slug,
                title=args.title or None,
                aliases=aliases,
                project=args.project or None,
                blurb=args.blurb or None,
            )
            rebuild_index(root)
            print(f"hub={card.id}")
            print(card.tldr)
            return 0
        if args.hub_cmd == "suggest":
            hits = suggest_hubs(root, args.text, limit=int(args.limit or 3))
            if not hits:
                print("(no match)")
                return 0
            for h in hits:
                print(f"{h['id']}\t{h['score']}\t{h['title']}")
            return 0
        raise BrainError(f"Unknown hub subcommand: {args.hub_cmd}")

    if cmd == "link":
        root = _root(args)
        add_link(root, args.a, args.b)
        rebuild_index(root)
        print(f"linked {args.a} ↔ {args.b}")
        return 0

    if cmd == "unlink":
        root = _root(args)
        remove_link(root, args.a, args.b)
        rebuild_index(root)
        print(f"unlinked {args.a} ↔ {args.b}")
        return 0

    if cmd == "active":
        root = _root(args)
        path = root / "core" / "active.md"
        if args.set_line:
            text = path.read_text(encoding="utf-8") if path.is_file() else "# Active\n"
            text += f"\n- {date.today().isoformat()}: {args.set_line}\n"
            path.write_text(text, encoding="utf-8")
            try:
                from brain.stats import log_activity

                log_activity(root, "active", detail=args.set_line[:100])
            except Exception:
                pass
            print("updated active.md")
            return 0
        print(path.read_text(encoding="utf-8") if path.is_file() else "(missing)")
        return 0

    if cmd == "reindex":
        root = _root(args)
        n = len(rebuild_index(root))
        print(f"indexed {n} cards")
        return 0

    if cmd == "unlock":
        root = _root(args)
        pw = args.password or getpass.getpass("Master password: ")
        from brain.config import load_vault_config

        allow_init = not bool(load_vault_config(root).get("crypto", {}).get("verifier"))
        unlock(root, pw, allow_init=allow_init)
        rebuild_index(root)
        print("unlocked" + (" (password initialized)" if allow_init else ""))
        return 0

    if cmd == "lock":
        lock()
        try:
            rebuild_index(_root(args))
        except BrainError:
            pass
        print("locked")
        return 0

    if cmd == "passwd":
        return _passwd(args)

    if cmd == "ui":
        from brain.ui_server import run_ui

        root = None
        try:
            root = _root(args)
        except BrainError:
            root = None
        run_ui(root=root, port=args.port)
        return 0

    if cmd == "desktop":
        from brain.desktop import run_desktop

        root = None
        try:
            root = _root(args)
        except BrainError:
            root = None
        run_desktop(root=root, port=args.port)
        return 0

    if cmd == "autostart":
        from brain import autostart as auto

        if args.action == "on":
            path = auto.enable()
            print(f"autostart=on plist={path}")
            print("UI стартує при логіні (KeepAlive). Перевір: brain status")
            return 0
        if args.action == "off":
            auto.disable()
            print("autostart=off")
            return 0
        st = auto.status()
        for k, v in st.items():
            print(f"{k}={v}")
        return 0

    if cmd == "upgrade":
        from brain.upgrade import find_pkg, run_upgrade, upgrade_hint

        pkg = find_pkg(args.pkg)
        for line in run_upgrade(pkg, dry_run=bool(args.dry_run)):
            print(line)
        if not args.dry_run:
            try:
                print(f"cursor={install_cursor()}")
                print(f"codex={install_codex()}")
                print(f"claude={install_claude()}")
            except Exception as e:
                print(f"agents_install_warn={e}")
        print(upgrade_hint())
        return 0

    if cmd == "agents":
        if args.agents_cmd == "install":
            do_codex = args.codex or args.all
            do_claude = args.claude or args.all
            do_cursor = args.cursor or args.all
            if not do_codex and not do_claude and not do_cursor:
                do_codex = do_claude = do_cursor = True  # default: all
            if do_codex:
                print(f"codex={install_codex()}")
            if do_claude:
                print(f"claude={install_claude()}")
            if do_cursor:
                print(f"cursor={install_cursor()}")
            return 0
        raise BrainError(f"Unknown agents subcommand: {args.agents_cmd}")

    if cmd == "catalog":
        root = _root(args)
        path = write_catalog(root)
        print(path.read_text(encoding="utf-8"), end="")
        return 0

    if cmd == "remember":
        root = _root(args)
        remember(root, args.note, source=args.source)
        print("remembered")
        return 0

    if cmd == "import":
        from brain.importer import import_folder

        root = _root(args)
        result = import_folder(root, args.folder, tag=args.tag)
        print(f"imported {result['count']} cards")
        if result.get("skipped"):
            print(f"skipped {len(result['skipped'])}")
        return 0

    if cmd == "import-topics":
        from brain.importer import import_topics

        root = _root(args)
        result = import_topics(root, args.folder, tag=args.tag)
        print(f"imported {result['count']} topic cards")
        if result.get("skipped"):
            print(f"skipped {len(result['skipped'])}")
            for s in result["skipped"]:
                print(f"skipped: {s}")
        return 0

    if cmd == "daily":
        from datetime import date as date_cls

        from brain.daily import ensure_daily
        from brain.recipes import seed_automations

        root = _root(args)
        seed_automations(root)
        day = date_cls.fromisoformat(args.day) if getattr(args, "day", None) else None
        card = ensure_daily(root, day)
        print(f"daily={card.id}")
        print(card.tldr)
        return 0

    if cmd == "stats":
        from brain.stats import vault_stats

        root = _root(args)
        s = vault_stats(root)
        print(f"cards={s['cards']} secure={s['secure']} inbox={s['inbox']}")
        print(
            f"tokens: full_vault={s['full_tokens']} plaintext={s['plaintext_tokens']} "
            f"secure≈{s['secure_tokens']} catalog={s['catalog_tokens']} "
            f"per_query≈{s['query_tokens']} savings≈{s['savings_pct']}%"
        )
        print(
            f"health: broken_links={s['broken_links']} orphans={s['orphans']} "
            f"stale={s['stale_cards']}"
        )
        print(
            f"activity: writes_today={s.get('writes_today', 0)} writes_14d={s.get('writes_14d', 0)} "
            f"fresh_24h={s.get('fresh_24h', 0)}"
        )
        print(
            f"usage_14d: queries={s['usage_queries_14d']} saved_tokens≈{s['usage_saved_14d']} "
            f"tz={s['usage_tz']}"
        )
        if s["top_tags"]:
            tags = ", ".join(f"{t}({n})" for t, n in s["top_tags"][:5])
            print(f"tags: {tags}")
        return 0

    if cmd == "recipe":
        root = _root(args)
        if args.recipe_cmd == "list":
            for r in list_recipes(root):
                print(f"{r.id}\t{r.trigger}\t{r.title}")
            return 0
        if args.recipe_cmd == "show":
            r = get_recipe(root, args.id)
            print(f"# {r.title} ({r.id})")
            print(f"trigger={r.trigger} scope={r.scope} max_cards={r.max_cards}")
            print(r.body)
            return 0
        if args.recipe_cmd == "run":
            result = run_recipe(root, args.id)
            for line in result["log"]:
                print(line)
            manuals = [x for x in result["log"] if x.startswith("manual:")]
            if manuals:
                print("--- manual steps for agent ---")
                for m in manuals:
                    print(m)
            return 0 if not any(x.startswith("fail:") for x in result["log"]) else 2
        raise BrainError(f"Unknown recipe subcommand: {args.recipe_cmd}")

    raise BrainError(f"Unknown command: {cmd}")


def _passwd(args: argparse.Namespace) -> int:
    from brain.crypto import decrypt, derive_key, encrypt, generate_salt
    from brain.config import load_vault_config, save_vault_config
    from brain.session import get_session_key, lock as sess_lock, unlock as sess_unlock

    root = _root(args)
    old = args.old or getpass.getpass("Current password: ")
    new = args.new or getpass.getpass("New password: ")
    # Always confirm interactively (never skip when --new is set)
    new2 = getpass.getpass("Confirm new: ")
    if new != new2:
        raise BrainError("New passwords do not match")
    sess_unlock(root, old)
    old_key = get_session_key()
    new_salt = generate_salt()
    new_key = derive_key(new, new_salt)
    secure_dir = root / "secure"
    secure_dir.mkdir(parents=True, exist_ok=True)
    files = list(secure_dir.glob("*.md.enc"))
    # Stage re-encrypted blobs, then atomic swap — avoids half-rekeyed vault on crash
    staged: list[tuple[Path, Path]] = []
    tmp_dir = secure_dir / ".rekey-tmp"
    if tmp_dir.exists():
        import shutil

        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        for p in files:
            plain = decrypt(p.read_bytes(), old_key)
            dest = tmp_dir / p.name
            dest.write_bytes(encrypt(plain, new_key))
            staged.append((dest, p))
        for dest, p in staged:
            dest.replace(p)
        vcfg = load_vault_config(root)
        vcfg["crypto"] = {
            "salt": new_salt.hex(),
            "kdf": "argon2id",
            "cipher": "aes-256-gcm",
            "verifier": encrypt(b"brain-ok", new_key).hex(),
        }
        save_vault_config(root, vcfg)
    finally:
        import shutil

        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
    sess_lock()
    sess_unlock(root, new)
    print("password updated; session re-unlocked with new password")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
