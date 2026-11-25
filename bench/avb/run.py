"""Run AgenticVBench tasks with and without UberSeek: `uv run python -m bench.avb.run --tasks <id> ...`.

Each run happens in a container that repeats the task's environment: the same base image, FFmpeg, CPU and
memory limits, and clock. The agent is OpenCode. The score comes from the task's own verifier, which fetches
the answer only after the agent has finished, as the benchmark does.

This is not a Harbor run, so its scores are not leaderboard results. It compares two conditions under the
same conditions as each other.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
import tomllib
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent.parent
RESULTS = HERE / "results"
CACHE = REPO / "data" / "avb"
MODEL = "openrouter/anthropic/claude-haiku-5.5"
CONDITIONS = ("native", "uberseek")
# Nobody is there to answer a permission question, and a refused one ends the run: allow work outside /workspace.
OPENCODE = json.dumps({"permission": {"external_directory": "allow"}})
ORACLE = "oracle"  # the task's own solution instead of an agent: checks the runner, costs nothing


def sh(*args: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, text=True, capture_output=True, **kwargs)


def proxy_env() -> dict[str, str]:
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or ""
    return {"HTTPS_PROXY": proxy, "https_proxy": proxy} if proxy else {}


def build(target: str) -> str:
    """Build the image for one condition. The certificate bundle and proxy are those of this machine."""
    context = CACHE / "context"
    shutil.rmtree(context, ignore_errors=True)
    (context / "src").mkdir(parents=True)
    bundle = Path(os.environ.get("SSL_CERT_FILE", "/etc/ssl/certs/ca-certificates.crt"))
    shutil.copy(bundle, context / "ca.crt")
    shutil.copy(HERE / "Dockerfile", context / "Dockerfile")
    for name in ("pyproject.toml", "README.md", "LICENSE", "uberseek"):
        source = REPO / name
        (shutil.copytree if source.is_dir() else shutil.copy)(source, context / "src" / name)
    tag = f"avb-{target}"
    proxy = proxy_env().get("HTTPS_PROXY", "")
    done = sh("docker", "build", "--network", "host", "--target", target, "--build-arg", f"PROXY={proxy}", "-t", tag, str(context))
    if done.returncode != 0:
        raise SystemExit(f"building {tag} failed:\n{done.stdout[-1500:]}\n{done.stderr[-1500:]}")
    return tag


def find_task(benchmark: Path, name: str) -> Path:
    """A task's folder, in whichever family holds it."""
    found = sorted((benchmark / "tasks").glob(f"agentic_vbench_*/{name}/task.toml"))
    found += sorted((HERE / "tasks").glob(f"*/{name}/task.toml"))  # our own tasks, in the same layout
    if not found:
        raise SystemExit(f"no task named {name} in {benchmark / 'tasks'} or {HERE / 'tasks'}")
    return found[0].parent


def materials_url(folder: Path, task: dict) -> str:
    """Where the task's zip is: the verifier's setting where there is one, else the image's build argument."""
    url = task["steps"][0].get("verifier", {}).get("env", {}).get("MATERIALS_URL")
    if url:
        return url
    found = re.search(r"^ARG MATERIALS_URL=(\S+)", (folder / "environment" / "Dockerfile").read_text(), re.M)
    if not found:
        raise SystemExit(f"{folder.name}: no MATERIALS_URL")
    return found.group(1)


def materials(folder: Path, task: dict) -> Path:
    """The task's zip, fetched once. A Repair zip holds input/ for the agent and golden/ for the verifier."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{folder.parent.name}.{folder.name}.zip"
    if not path.exists():
        url = materials_url(folder, task)
        request = urllib.request.Request(url, headers={"User-Agent": "uberseek-bench/0.1"})
        with urllib.request.urlopen(request, timeout=120) as reply, path.open("wb") as out:
            shutil.copyfileobj(reply, out)
    return path


def unpack(folder: Path, task: dict, work: Path) -> None:
    """A benchmark task's zip into the agent's materials. Only input/ is given when the zip has one."""
    with zipfile.ZipFile(materials(folder, task)) as archive:
        names = [member for member in archive.namelist() if not member.endswith("/")]
        split = any(member.startswith("input/") for member in names)  # then only input/ is given to the agent
        for member in names:
            if not split or member.startswith("input/"):
                target = (work / "workspace" / "materials" / member.removeprefix("input/")).resolve()
                if not target.is_relative_to(work):
                    raise SystemExit(f"{folder.name}: the zip has a path outside the folder: {member}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member))


def run_one(benchmark: Path, name: str, condition: str, model: str, stamp: str) -> dict:
    folder = find_task(benchmark, name)
    task = tomllib.loads((folder / "task.toml").read_text())
    limits, step = task["environment"], task["steps"][0]
    timeout = int(step["agent"]["timeout_sec"])
    work = (CACHE / "runs" / stamp / name / condition).resolve()
    for sub in ("workspace/materials", "workspace/output", "workspace/work", "logs", "tests"):
        (work / sub).mkdir(parents=True)

    if "materials" in task:  # our own tasks name their files instead of a zip
        for given, source in task["materials"].items():
            if not (REPO / source).exists() and (make := task.get("metadata", {}).get("make")):
                subprocess.run(make.split(), cwd=REPO, check=True)  # a generated file is made, not committed
            if not (REPO / source).exists():
                raise SystemExit(f"{folder.name}: {source} is missing. See the task's metadata for how to get it.")
            shutil.copy(REPO / source, work / "workspace" / "materials" / given)
    else:
        unpack(folder, task, work)
    (work / "instruction.md").write_text((folder / "steps" / "solve" / "instruction.md").read_text())

    common = ["--network", "host", "--cpus", str(limits["cpus"]), "--memory", f"{limits['memory_mb']}m"]
    env = [arg for key, value in proxy_env().items() for arg in ("-e", f"{key}={value}")]
    mounts = ["-v", f"{work / 'workspace'}:/workspace", "-v", f"{work / 'logs'}:/logs"]
    agent = (
        f"cd /workspace && timeout {timeout} opencode run -m {model} --format json "
        '"$(cat /task/instruction.md)" > /logs/agent.jsonl 2> /logs/agent.err; echo $? > /logs/agent.exit'
    )
    image = f"avb-{condition}"
    if condition == ORACLE:
        image, script = "avb-native", folder / "steps" / "solve" / "solution" / "solve.sh"
        mounts += ["-v", f"{script}:/task/solve.sh:ro"]
        agent = "bash /task/solve.sh > /logs/agent.err 2>&1; echo $? > /logs/agent.exit; : > /logs/agent.jsonl"
    began = time.time()
    sh(
        "docker", "run", "--rm", *common, *env, *mounts, "-v", f"{work / 'instruction.md'}:/task/instruction.md:ro",
        "-e", "OPENROUTER_API_KEY=proxy-injected", "-e", f"OPENCODE_CONFIG_CONTENT={OPENCODE}", image, "bash", "-c", agent,
        timeout=timeout + 120,
    )  # fmt: skip
    seconds = round(time.time() - began)

    # The verifier: the task's own test.sh, which fetches the answer itself, after the agent is gone.
    shutil.copytree(folder / "steps" / "solve" / "tests", work / "tests", dirs_exist_ok=True)
    secret = [arg for key, value in step["verifier"].get("env", {}).items() for arg in ("-e", f"{key}={value}")]
    sh(
        "docker", "run", "--rm", *common, *env, *mounts, "-v", f"{work / 'tests'}:/tests", *secret,
        "avb-native", "bash", "/tests/test.sh",
        timeout=int(step["verifier"]["timeout_sec"]),
    )  # fmt: skip
    reward = work / "logs" / "verifier" / "reward.json"
    events = [json.loads(line) for line in (work / "logs" / "agent.jsonl").read_text().splitlines() if line.startswith("{")]
    tokens = [e["part"]["tokens"] for e in events if e.get("type") == "step_finish" and "tokens" in e.get("part", {})]
    tools = [e["part"]["tool"] for e in events if e.get("type") == "tool_use"]
    commands = [
        e["part"]["state"]["input"].get("command", "") for e in events if e.get("type") == "tool_use" and e["part"]["tool"] == "bash"
    ]
    return {
        "task": name,
        "condition": condition,
        "model": model,
        "reward": json.loads(reward.read_text()) if reward.exists() else None,
        "seconds": seconds,
        "timed_out": (work / "logs" / "agent.exit").read_text().strip() == "124",
        "steps": len(tokens),
        "tokens": {"input": sum(t.get("input", 0) for t in tokens), "output": sum(t.get("output", 0) for t in tokens),
                   "cache_read": sum(t.get("cache", {}).get("read", 0) for t in tokens)},
        "cost_usd": round(sum(e["part"].get("cost", 0) for e in events if e.get("type") == "step_finish"), 4),
        "tool_calls": len(tools),
        "uberseek_commands": sum("uberseek" in command for command in commands),
        "folder": str(work),
    }  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", default="/home/user/philolabs/agentic-vbench", help="a checkout of PhiloLabs/agentic-vbench")
    parser.add_argument("--tasks", nargs="+", required=True, help="task ids of any family, like exp-content-cut-wsj-task01")
    parser.add_argument("--conditions", nargs="+", default=list(CONDITIONS), choices=(*CONDITIONS, ORACLE))
    parser.add_argument("--model", default=MODEL, help="an OpenCode model id")
    parser.add_argument("--no-build", action="store_true", help="use the images already built")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    if not args.no_build:
        for target in dict.fromkeys(["native", *(c for c in args.conditions if c != ORACLE)]):
            print(f"building avb-{target} ...", flush=True)
            build(target)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%S")
    rows = []
    for name in args.tasks:
        for condition in args.conditions:
            row = run_one(Path(args.benchmark), name, condition, args.model, stamp)
            rows.append(row)
            score = row["reward"]["reward"] if row["reward"] else "no score"
            used = f"{row['seconds']} s · {row['steps']} steps · ${row['cost_usd']}"
            print(f"{name} · {condition} · reward {score} · {used} · {row['uberseek_commands']} uberseek commands", flush=True)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{stamp}.json").write_text(json.dumps({"at": stamp, "note": args.note, "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
