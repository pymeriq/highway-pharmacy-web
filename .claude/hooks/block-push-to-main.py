#!/usr/bin/env python3
"""PreToolUse(Bash) hook: block `git push` to main/master in THIS repo.

Wired via the repo's .claude/settings.json, so it loads for anyone running Claude
Code in this project. Portable: the guarded repo is derived from this script's own
location (repo/.claude/hooks/), not a hardcoded path.

For a `git push` command it:
  1. Resolves the effective dir the git command runs in (honors `cd <dir>` and
     `git -C <dir>`; falls back to the hook's cwd).
  2. If that dir's git top-level != this repo, allows it (a different repo).
  3. Otherwise blocks when the push targets main/master:
       - explicit target, e.g. `git push origin main`, `... HEAD:main`, `feat:master`
       - a bare push (no refspec) while HEAD is on main/master.

Emits a PreToolUse "deny" decision on block; otherwise stays silent (allow).
"""
import sys, os, json, re, subprocess

# repo root = two levels up from this file (repo/.claude/hooks/block-push-to-main.py)
GUARDED_REPO = os.path.realpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
REPO_NAME = os.path.basename(GUARDED_REPO)
PROTECTED = ("main", "master")


def emit_deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def _unquote(m):
    return m.group(2) or m.group(3) or m.group(4)


def effective_dir(cmd, default):
    """Best-effort: directory the git command executes in."""
    d = default
    for m in re.finditer(r'\bcd\s+("([^"]*)"|\'([^\']*)\'|([^\s;&|]+))', cmd):
        d = _unquote(m)  # last `cd <dir>` wins
    m = re.search(r'\bgit\b(?:\s+-\S+)*\s+-C\s+("([^"]*)"|\'([^\']*)\'|([^\s;&|]+))', cmd)
    if m:
        d = _unquote(m)  # `git -C <dir>` overrides
    return d


def _git(d, *args):
    try:
        r = subprocess.run(["git", "-C", d, *args], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cmd = ((data.get("tool_input") or {}).get("command") or "")
    if not cmd:
        sys.exit(0)

    # `git [global-opts] push <args>` — `push` must be the git SUBCOMMAND, not the
    # substring "push" inside a branch name / commit message. Skip global opts
    # (incl. value-taking -C/-c/--namespace forms) before the subcommand.
    push_re = (r'\bgit\b(?:\s+(?:-C\s+\S+|-c\s+\S+|--namespace\s+\S+|--work-tree\s+\S+'
               r'|--git-dir\s+\S+|--\S+|-\w+))*\s+push\b([^;&|]*)')
    segments = [m.group(1) for m in re.finditer(push_re, cmd)]
    if not segments:
        sys.exit(0)

    # Repo guard: only enforce inside this repo.
    workdir = effective_dir(cmd, os.getcwd())
    top = _git(workdir, "rev-parse", "--show-toplevel")
    if os.path.realpath(top) != GUARDED_REPO if top else True:
        sys.exit(0)

    # Case 1: explicit main/master token as a push target.
    for seg in segments:
        if re.search(r'(?:^|[\s:])(?:main|master)(?:[\s:]|$)', seg):
            emit_deny(
                f"Direct push to main/master in {REPO_NAME} is blocked. Create a feature branch "
                f"and open a PR (git checkout -b <type>/<slug>; git push -u origin <branch>; gh pr create)."
            )

    # Case 2: bare push (no explicit refspec) while HEAD is on a protected branch.
    branch = _git(workdir, "rev-parse", "--abbrev-ref", "HEAD")
    if branch in PROTECTED:
        for seg in segments:
            positional = [t for t in seg.split() if t and not t.startswith("-")]
            if len(positional) <= 1:  # just a remote, or nothing -> pushes current (protected) branch
                emit_deny(
                    f"You are on '{branch}' in {REPO_NAME} and pushing it directly. Blocked — "
                    f"branch off (git checkout -b <type>/<slug>) and open a PR."
                )

    sys.exit(0)


if __name__ == "__main__":
    main()
