# Crimson Ledger (SeaTrader) — rules for agents

More than one agent may be working in this folder at the same time. A file-lock
hook (`tools/agent_locks/file_lock.py`, switched on in `.claude/settings.json` by `Install_Agent_Locks.bat`)
keeps them from overwriting each other.

## How the locks work
- The first session to Edit/Write a file checks it out automatically.
- If another session holds a file, your edit is blocked with a message saying who
  holds it and what they're working on.
- Locks are checked back in when a session ends, or lapse after 20 idle minutes.

## Rules
1. **A blocked file is off-limits.** Never work around a block by rewriting the
   file through Bash, a Python script, PowerShell, or by copying files over it.
   Work on something else, or stop and tell the user which file is in use.
2. **Claim before scripted edits.** If you'll change files with a script instead of
   Edit/Write, check them out first:
   `python tools/agent_locks/file_lock.py claim engine.py strings.py`
3. **Check in when a task is finished** so other agents aren't kept waiting:
   `python tools/agent_locks/file_lock.py done`
4. **No folder-wide git commands while others hold locks** (checkout, restore,
   reset, stash, clean, pull, merge, rebase). They can wipe another session's
   unsaved work. The hook blocks them; ask the user instead.
5. **See who holds what:** `python tools/agent_locks/file_lock.py status`
6. **Agents working from outside this PC** (cloud sessions using the device
   bridge) don't go through the hook. Read `.agent-locks/files/` before
   writing, skip any file another session holds, and always commit with the
   staged file's mtime as the expected mtime so a changed file is refused.

The big shared files (`engine.py`, `strings.py`, `config.py`, `server.py`) are
where clashes happen. Keep changes to them focused and check in promptly.

## Writing dialogue
Every line a character says aloud follows the house voice in `house_voice.py` (`HOUSE_STYLE`):
sexy, funny, full of innuendo, never explicit, each character in her own voice. Brand-new lines go in
`strings.py` as usual, written in that voice, with a clean version in `FAMILY`. To reword an existing
spoken line, put it in `house_voice.LINES` (and `SPOKEN` for a number-free voice version) so the old
wording becomes the family line. Run `tests/house_voice_test.py`.
