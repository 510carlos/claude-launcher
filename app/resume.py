"""PTY-based session resume: spawn claude --resume, send /remote-control, capture URL."""

from __future__ import annotations

import logging
import os
import pty
import re
import select
import signal
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"https://claude\.ai/code/session_[A-Za-z0-9]+")
PROMPT_CHAR = "\u276f"  # ❯


@dataclass
class PtySession:
    master_fd: int
    child_pid: int


def blocking_pty_resume(
    claude_bin: str,
    conversation_id: str,
    working_dir: str,
    env: dict[str, str],
    timeout: float = 30.0,
) -> tuple[PtySession | None, str | None, str]:
    """Spawn claude --resume via PTY, send /remote-control, capture URL.

    Runs synchronously (call from executor). Returns (pty_session, url, output).
    The child process survives via os.setsid() — caller does NOT need to keep
    the master fd open for the child to stay alive.
    """
    master_fd, slave_fd = pty.openpty()

    pid = os.fork()
    if pid == 0:
        # --- Child process ---
        os.close(master_fd)
        os.setsid()
        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        if slave_fd > 2:
            os.close(slave_fd)
        try:
            os.chdir(working_dir)
        except OSError:
            pass
        os.execvpe(claude_bin, [claude_bin, "--resume", conversation_id, "--fork-session"], env)
        os._exit(1)

    # --- Parent process ---
    os.close(slave_fd)

    output = ""
    url = None
    deadline = time.monotonic() + timeout
    sent = False

    while time.monotonic() < deadline:
        ready, _, _ = select.select([master_fd], [], [], 0.5)
        if ready:
            try:
                chunk = os.read(master_fd, 4096).decode("utf-8", errors="replace")
            except OSError:
                break
            output += chunk

            if not sent and PROMPT_CHAR in output:
                time.sleep(1)  # let UI settle
                try:
                    os.write(master_fd, b"/remote-control\r")
                except OSError:
                    break
                sent = True

            if sent:
                match = URL_PATTERN.search(output)
                if match:
                    url = match.group(0)
                    break

    # Close master fd — child survives because of setsid()
    try:
        os.close(master_fd)
    except OSError:
        pass

    if url:
        log.info("Resume captured URL for pid %d: %s", pid, url)
        return PtySession(master_fd=-1, child_pid=pid), url, output
    else:
        log.warning("Resume failed to capture URL for pid %d (sent=%s)", pid, sent)
        # Kill the child if we didn't get a URL
        _kill_pid(pid)
        return None, None, output


def cleanup_pty(pty_session: PtySession) -> None:
    """Terminate a resumed session's child process."""
    _kill_pid(pty_session.child_pid)


def _kill_pid(pid: int) -> None:
    """SIGTERM, wait 2s, SIGKILL."""
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    time.sleep(2)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
