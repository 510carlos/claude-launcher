from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from app.models import (
    DiscoveredEnvironment,
    DiscoveryCompatibility,
    RuntimeType,
    Workspot,
)

log = logging.getLogger(__name__)

COMMON_CLAUDE_PATHS = [
    "claude",
    "/usr/local/bin/claude",
    "/home/node/.npm-global/bin/claude",
    "/home/node/.local/bin/claude",
    "/usr/bin/claude",
    "/home/carlos/.local/bin/claude",
]

WORKSPACE_SEARCH_DIRS = ["/workspaces", "/home", "/app", "/opt", "/root"]


async def _exec(cmd: list[str], timeout: float = 10.0) -> tuple[int, str, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode or 0, stdout.decode().strip(), stderr.decode().strip()
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return -1, "", "timeout"
    except Exception as e:
        return -1, "", str(e)


async def _docker_exec(container: str, command: str, timeout: float = 10.0) -> tuple[int, str, str]:
    return await _exec(["docker", "exec", container, "bash", "-lc", command], timeout=timeout)


async def _find_claude_in_container(container: str) -> Optional[str]:
    for path in COMMON_CLAUDE_PATHS:
        rc, stdout, _ = await _docker_exec(container, f"command -v {path} 2>/dev/null")
        if rc == 0 and stdout:
            return stdout.split("\n")[0].strip()
    return None


async def _find_repos_in_container(container: str) -> list[str]:
    repos: list[str] = []
    seen: set[str] = set()

    for ws_dir in WORKSPACE_SEARCH_DIRS:
        rc, stdout, _ = await _docker_exec(
            container,
            f"find {ws_dir} -maxdepth 2 -name .git -type d 2>/dev/null | head -20",
            timeout=15.0,
        )
        if rc == 0 and stdout:
            for line in stdout.strip().split("\n"):
                repo_path = line.replace("/.git", "")
                if repo_path and repo_path not in seen:
                    seen.add(repo_path)
                    repos.append(repo_path)
    return repos


async def _check_auth_in_container(container: str) -> bool:
    rc, _, _ = await _docker_exec(
        container,
        "test -s ~/.claude/.credentials.json "
        "|| test -s /home/node/.claude/.credentials.json "
        "|| test -s /root/.claude/.credentials.json",
    )
    return rc == 0


async def _get_container_info() -> dict[str, dict]:
    """Get container name -> {image, status} mapping."""
    rc, stdout, _ = await _exec(
        ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.State}}"],
        timeout=10.0,
    )
    if rc != 0:
        return {}
    info = {}
    for line in stdout.strip().split("\n"):
        parts = line.split("\t")
        if len(parts) >= 4:
            info[parts[0]] = {"image": parts[1], "status": parts[2], "state": parts[3]}
    return info


async def scan_docker_containers(existing_names: set[str]) -> list[DiscoveredEnvironment]:
    container_info = await _get_container_info()
    if not container_info:
        return []

    all_containers = list(container_info.keys())
    results: list[DiscoveredEnvironment] = []
    sem = asyncio.Semaphore(5)

    async def scan_container(container: str):
        async with sem:
            cinfo = container_info.get(container, {})
            image = cinfo.get("image", "")
            cstatus = cinfo.get("status", "")
            is_running = cinfo.get("state") == "running"

            # Stopped containers: can't exec in, just report them
            if not is_running:
                already = container in existing_names
                results.append(DiscoveredEnvironment(
                    name=container,
                    runtime=RuntimeType.docker,
                    dir="/",
                    container=container,
                    claude_bin=None,
                    compatibility=DiscoveryCompatibility.incompatible,
                    checks={"runtime_ok": False, "git_ok": False, "claude_bin_ok": False, "auth_ok": False},
                    issues=["Container not running"],
                    already_configured=already,
                    image=image,
                    container_status=cstatus,
                ))
                return

            claude_bin = await _find_claude_in_container(container)
            has_claude = claude_bin is not None
            is_auth = await _check_auth_in_container(container) if has_claude else False
            git_rc, _, _ = await _docker_exec(container, "command -v git")
            has_git_cmd = git_rc == 0
            repos = await _find_repos_in_container(container) if has_git_cmd else []

            if not repos:
                issues = []
                checks = {"runtime_ok": True, "git_ok": False, "claude_bin_ok": has_claude, "auth_ok": is_auth}
                if not has_claude:
                    issues.append("Claude CLI not found")
                if not is_auth and has_claude:
                    issues.append("Not authenticated")
                if not has_git_cmd:
                    issues.append("Git not available")
                issues.append("No git repositories found")

                compat = DiscoveryCompatibility.incompatible
                if has_claude and has_git_cmd:
                    compat = DiscoveryCompatibility.partial

                already = container in existing_names
                results.append(DiscoveredEnvironment(
                    name=container,
                    runtime=RuntimeType.docker,
                    dir="/",
                    container=container,
                    claude_bin=claude_bin,
                    compatibility=compat,
                    checks=checks,
                    issues=issues,
                    already_configured=already,
                    image=image,
                    container_status=cstatus,
                ))
            else:
                for repo_path in repos:
                    git_check_rc, _, _ = await _docker_exec(
                        container, f"git -C {repo_path} rev-parse --is-inside-work-tree 2>/dev/null"
                    )
                    has_git = git_check_rc == 0

                    issues = []
                    if not has_claude:
                        issues.append("Claude CLI not found")
                    if not is_auth and has_claude:
                        issues.append("Not authenticated — run /login")
                    if not has_git:
                        issues.append("Git not initialized")

                    if has_claude and is_auth and has_git:
                        compat = DiscoveryCompatibility.compatible
                    elif has_claude or has_git:
                        compat = DiscoveryCompatibility.partial
                    else:
                        compat = DiscoveryCompatibility.incompatible

                    repo_name = Path(repo_path).name
                    suggested_name = repo_name if len(repos) == 1 else f"{repo_name}-{container}"
                    already = suggested_name in existing_names

                    results.append(DiscoveredEnvironment(
                        name=suggested_name,
                        runtime=RuntimeType.docker,
                        dir=repo_path,
                        container=container,
                        claude_bin=claude_bin,
                        compatibility=compat,
                        checks={
                            "runtime_ok": True,
                            "repo_exists": True,
                            "git_ok": has_git,
                            "claude_bin_ok": has_claude,
                            "auth_ok": is_auth,
                        },
                        issues=issues,
                        already_configured=already,
                        image=image,
                        container_status=cstatus,
                    ))

    await asyncio.gather(*(scan_container(c) for c in all_containers))
    return results


async def scan_local_directories(scan_dirs: list[str], existing_names: set[str]) -> list[DiscoveredEnvironment]:
    # Check host-level Claude availability once
    claude_rc, claude_path, _ = await _exec(["which", "claude"])
    has_claude = claude_rc == 0
    claude_bin = claude_path if has_claude else None

    home = os.path.expanduser("~")
    creds_path = os.path.join(home, ".claude", ".credentials.json")
    is_auth = os.path.isfile(creds_path) and os.path.getsize(creds_path) > 0

    results: list[DiscoveredEnvironment] = []

    for scan_dir in scan_dirs:
        expanded = os.path.expanduser(scan_dir)
        if not os.path.isdir(expanded):
            continue

        rc, stdout, _ = await _exec(
            ["find", expanded, "-maxdepth", "2", "-name", ".git", "-type", "d"],
            timeout=15.0,
        )
        if rc != 0 or not stdout:
            continue

        for line in stdout.strip().split("\n"):
            repo_path = line.replace("/.git", "")
            if not repo_path or not os.path.isdir(repo_path):
                continue

            issues = []
            if not has_claude:
                issues.append("Claude CLI not on PATH")
            if not is_auth:
                issues.append("Not authenticated — run claude login")

            if has_claude and is_auth:
                compat = DiscoveryCompatibility.compatible
            elif has_claude:
                compat = DiscoveryCompatibility.partial
            else:
                compat = DiscoveryCompatibility.incompatible

            repo_name = Path(repo_path).name
            already = repo_name in existing_names

            results.append(DiscoveredEnvironment(
                name=repo_name,
                runtime=RuntimeType.host,
                dir=repo_path,
                container=None,
                claude_bin=claude_bin,
                compatibility=compat,
                checks={
                    "runtime_ok": True,
                    "repo_exists": True,
                    "git_ok": True,
                    "claude_bin_ok": has_claude,
                    "auth_ok": is_auth,
                },
                issues=issues,
                already_configured=already,
            ))

    return results


async def discover_all(
    scan_dirs: list[str],
    existing_workspots: list[Workspot],
    docker_enabled: bool = True,
    local_enabled: bool = True,
) -> dict:
    existing_names = {ws.name for ws in existing_workspots}

    tasks = []
    if docker_enabled:
        tasks.append(scan_docker_containers(existing_names))
    if local_enabled:
        tasks.append(scan_local_directories(scan_dirs, existing_names))

    all_results: list[DiscoveredEnvironment] = []
    for result_list in await asyncio.gather(*tasks):
        all_results.extend(result_list)

    compatible = [r.model_dump() for r in all_results if r.compatibility == DiscoveryCompatibility.compatible]
    partial = [r.model_dump() for r in all_results if r.compatibility == DiscoveryCompatibility.partial]
    incompatible = [r.model_dump() for r in all_results if r.compatibility == DiscoveryCompatibility.incompatible]

    return {
        "compatible": compatible,
        "partial": partial,
        "incompatible": incompatible,
        "total": len(all_results),
    }
