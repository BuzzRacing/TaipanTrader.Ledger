#!/usr/bin/env python3
"""
Crimson Ledger (SeaTrader) - agent file locks.

Stops two Claude Code sessions working in D:\\SeaTrader at the same time from
overwriting each other. The first session to edit a file "checks it out"; any
other session that tries to edit that file is blocked and told who holds it.

Claude Code runs this as a hook (Install_Agent_Locks.bat puts tools/agent_locks/settings.json
into .claude/settings.json):
    file_lock.py pre      PreToolUse   - check out files before Edit/Write, guard Bash
    file_lock.py prompt   UserPromptSubmit - keep this session marked as alive
    file_lock.py end      SessionEnd   - check every file this session holds back in

You (or an agent) can also run it by hand:
    file_lock.py status               list who holds what
    file_lock.py claim FILE [FILE..]  agents: check files out before script edits
    file_lock.py done                 agents: check in everything this session holds
    file_lock.py clear                remove every lock (use if a session crashed)

A session's locks lapse on their own after STALE_MINUTES with no activity,
so a crashed or closed window never leaves a file stuck forever.

Standard library only, so it runs on Windows and on the Raspberry Pi as-is.
"""

import json
import os
import re
import sys
import time

STALE_MINUTES = 20
STALE_SECONDS = STALE_MINUTES * 60

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(os.path.dirname(HERE))          # tools/agent_locks -> project root
LOCK_DIR = os.path.join(PROJECT, ".agent-locks")
FILE_DIR = os.path.join(LOCK_DIR, "files")
SESSION_DIR = os.path.join(LOCK_DIR, "sessions")

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

# Folders the game itself writes to while running; agents touching them is not a clash.
UNLOCKED_PREFIXES = (
    ".agent-locks/", ".git/", "__pycache__/", ".pytest_cache/",
    "saves/", "journal/", "cache/", ".browser/", "config/backups/",
)

# Git commands that can throw away another session's unsaved work in this folder.
GIT_DESTRUCTIVE = re.compile(
    r"\bgit\s+(?:-\S+\s+)*(checkout|restore|reset|stash|clean|switch|pull|merge|rebase|cherry-pick|revert)\b"
)

# Signs that a shell command writes to a file it names.
WRITE_HINTS = re.compile(
    r"(?<![0-9&])>(?!&)|\btee\b|\bsed\s+-i|\bperl\s+-[a-z]*i|\bmv\b|\bcp\b|\brm\b|\bdel\b|\bcopy\b|\bmove\b"
    r"|Set-Content|Add-Content|Out-File|Copy-Item|Move-Item|Remove-Item"
    r"|write_text|write_bytes|\.write\(|open\([^)]*['\"][wa]"
)


# --------------------------------------------------------------------------- helpers

def now():
    return time.time()


def ensure_dirs():
    os.makedirs(FILE_DIR, exist_ok=True)
    os.makedirs(SESSION_DIR, exist_ok=True)


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def write_json(path, data):
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    os.replace(tmp, path)


def remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def short(sid):
    return (sid or "unknown")[:8]


def ago(ts):
    secs = max(0, int(now() - (ts or 0)))
    if secs < 90:
        return "%ds ago" % secs
    return "%d min ago" % (secs // 60)


def rel_path(path):
    """Project-relative path with forward slashes, or None if outside the project."""
    if not path:
        return None
    full = path if os.path.isabs(path) else os.path.join(PROJECT, path)
    full = os.path.normcase(os.path.normpath(os.path.abspath(full)))
    root = os.path.normcase(os.path.normpath(PROJECT))
    if full != root and not full.startswith(root + os.sep):
        return None
    rel = os.path.relpath(full, root).replace(os.sep, "/")
    return None if rel == "." else rel


def lockable(rel):
    return rel is not None and not rel.startswith(UNLOCKED_PREFIXES)


def lock_path(rel):
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", rel.replace("/", "__"))
    return os.path.join(FILE_DIR, safe + ".json")


def session_path(sid):
    return os.path.join(SESSION_DIR, re.sub(r"[^A-Za-z0-9_-]", "_", sid) + ".json")


# --------------------------------------------------------------------------- sessions

def heartbeat(sid, task=None):
    if not sid:
        return
    ensure_dirs()
    path = session_path(sid)
    data = read_json(path) or {"session_id": sid, "started": now()}
    data["last_seen"] = now()
    if task:
        data["task"] = task
    write_json(path, data)


def session_info(sid):
    return read_json(session_path(sid)) or {}


def owner_alive(lock):
    """A lock counts while its session has been active within STALE_MINUTES."""
    info = session_info(lock.get("session_id", ""))
    last = max(info.get("last_seen", 0), lock.get("last_seen", 0))
    return now() - last < STALE_SECONDS, last, info.get("task", "")


def all_locks():
    ensure_dirs()
    out = []
    for name in sorted(os.listdir(FILE_DIR)):
        if name.endswith(".json"):
            path = os.path.join(FILE_DIR, name)
            data = read_json(path)
            if data:
                out.append((path, data))
    return out


# --------------------------------------------------------------------------- locking

def acquire(rel, sid, tool):
    """Check rel out to sid. Returns None if OK, or a message explaining the block."""
    ensure_dirs()
    path = lock_path(rel)
    record = {"path": rel, "session_id": sid, "acquired": now(), "last_seen": now(), "tool": tool}
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=1)
        return None
    except FileExistsError:
        pass

    current = read_json(path) or {}
    if current.get("session_id") == sid:
        current["last_seen"] = now()
        write_json(path, current)
        return None

    alive, last, task = owner_alive(current)
    if not alive:
        write_json(path, record)              # previous holder went quiet: take it over
        return None

    msg = (
        "BLOCKED: %s is checked out by another agent session (%s), active %s."
        % (rel, short(current.get("session_id")), ago(last))
    )
    if task:
        msg += " That session is working on: \"%s\"." % task
    msg += (
        " Do not edit this file by any other route (Bash, Python, copying files). "
        "Work on something else, or stop and tell the user this file is in use. "
        "The lock frees up when that session ends or after %d idle minutes. "
        "Check with: python tools/agent_locks/file_lock.py status" % STALE_MINUTES
    )
    return msg


def release_session(sid):
    count = 0
    for path, data in all_locks():
        if data.get("session_id") == sid:
            remove(path)
            count += 1
    return count


def foreign_live_locks(sid):
    out = []
    for _path, data in all_locks():
        if data.get("session_id") != sid:
            alive, last, task = owner_alive(data)
            if alive:
                out.append((data, last, task))
    return out


# --------------------------------------------------------------------------- hook handlers

def read_event():
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    try:
        return json.loads(raw) if raw.strip() else {}
    except ValueError:
        return {}


def block(msg):
    sys.stderr.write(msg + "\n")
    sys.exit(2)                               # exit 2 = Claude Code blocks the tool call


def claim_args(command):
    """Files listed after 'file_lock.py claim' in a shell command."""
    m = re.search(r"file_lock\.py[\"']?\s+claim\s+(.+)", command)
    if not m:
        return []
    tail = re.split(r"[;&|]", m.group(1))[0]
    return [t.strip("\"'") for t in tail.split() if t.strip("\"'")]


def on_pre(event):
    sid = event.get("session_id", "")
    tool = event.get("tool_name", "")
    tin = event.get("tool_input") or {}
    heartbeat(sid)

    if tool in EDIT_TOOLS:
        rel = rel_path(tin.get("file_path") or tin.get("notebook_path"))
        if lockable(rel):
            msg = acquire(rel, sid, tool)
            if msg:
                block(msg)
        return

    if tool != "Bash":
        return
    command = tin.get("command", "") or ""

    # Agent asked to check files out before a scripted edit.
    if "file_lock.py" in command and re.search(r"file_lock\.py[\"']?\s+claim\b", command):
        problems = []
        for name in claim_args(command):
            rel = rel_path(name)
            if lockable(rel):
                msg = acquire(rel, sid, "claim")
                if msg:
                    problems.append(msg)
        if problems:
            block("\n".join(problems))
        return

    if "file_lock.py" in command and re.search(r"file_lock\.py[\"']?\s+done\b", command):
        release_session(sid)
        return

    others = foreign_live_locks(sid)
    if not others:
        return

    if GIT_DESTRUCTIVE.search(command):
        held = ", ".join(sorted({d.get("path", "?") for d, _l, _t in others}))
        block(
            "BLOCKED: another agent session has files checked out (%s). This git command "
            "can throw away its unsaved work in this folder, so it is not allowed until "
            "those locks are released. Ask the user first." % held
        )

    if WRITE_HINTS.search(command):
        lowered = command.replace("\\", "/").lower()
        for data, last, task in others:
            rel = data.get("path", "")
            base = rel.rsplit("/", 1)[-1].lower()
            if rel.lower() in lowered or re.search(r"(?<![A-Za-z0-9_.-])" + re.escape(base) + r"(?![A-Za-z0-9_-])", lowered):
                note = (" It is working on: \"%s\"." % task) if task else ""
                block(
                    "BLOCKED: this command looks like it writes to %s, which is checked out by "
                    "another agent session (%s, active %s).%s Do not change it by any route; "
                    "work on something else or tell the user." % (rel, short(data.get("session_id")), ago(last), note)
                )


def on_prompt(event):
    prompt = (event.get("prompt") or "").strip().replace("\n", " ")
    task = prompt[:90] + ("..." if len(prompt) > 90 else "")
    heartbeat(event.get("session_id", ""), task or None)


def on_end(event):
    sid = event.get("session_id", "")
    if sid:
        release_session(sid)
        remove(session_path(sid))


# --------------------------------------------------------------------------- manual commands

def cmd_status():
    locks = all_locks()
    if not locks:
        print("No files are checked out. Every agent is free to edit.")
        return
    print("Files checked out by agent sessions (locks lapse after %d idle minutes):" % STALE_MINUTES)
    print()
    by_session = {}
    for _path, data in locks:
        by_session.setdefault(data.get("session_id", "?"), []).append(data)
    for sid, items in by_session.items():
        alive, last, task = owner_alive(items[0])
        state = "ACTIVE" if alive else "lapsed"
        print("  Session %s  [%s, last active %s]" % (short(sid), state, ago(last)))
        if task:
            print("    working on: %s" % task)
        for d in sorted(items, key=lambda x: x.get("path", "")):
            print("    - %s" % d.get("path"))
        print()


def cmd_clear():
    n = 0
    for path, _data in all_locks():
        remove(path)
        n += 1
    for name in os.listdir(SESSION_DIR):
        remove(os.path.join(SESSION_DIR, name))
    print("Cleared %d lock(s)." % n)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "status"
    try:
        if mode == "pre":
            on_pre(read_event())
        elif mode == "prompt":
            on_prompt(read_event())
        elif mode == "end":
            on_end(read_event())
        elif mode == "status":
            cmd_status()
        elif mode == "clear":
            cmd_clear()
        elif mode == "claim":
            # The real check-out happens in the PreToolUse hook (it knows the session id).
            print("Checked out: " + ", ".join(sys.argv[2:]) if sys.argv[2:] else "Nothing to claim.")
        elif mode == "done":
            print("This session's files are checked back in.")
        else:
            print(__doc__)
    except SystemExit:
        raise
    except Exception as exc:                  # never break an agent because the lock system hiccuped
        sys.stderr.write("file_lock: %s\n" % exc)
        sys.exit(0)


if __name__ == "__main__":
    main()
