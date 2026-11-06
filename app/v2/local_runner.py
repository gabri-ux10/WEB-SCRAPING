"""Load the ignored .env, gate the Stage 2 pilot on diagnostics, then run it."""

from __future__ import annotations

import os
import json
import subprocess
import sys
import time
from pathlib import Path

from app.v2.envfile import load_selected_env

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        raise SystemExit("Missing project .env; create it by merging keys, never by overwriting an existing env file.")
    safe_keys = {"DATABASE_URL", "CSJOBS_CONTACT_EMAIL", "CSJOBS_TEAMTAILOR_FEED_URL", "CSJOBS_TEAMTAILOR_COMPANY_NAME", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"}
    values = load_selected_env(env_path, safe_keys)
    proxy_keys = sorted(safe_keys - {"DATABASE_URL", "CSJOBS_CONTACT_EMAIL"})
    runtime_keys = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA", *proxy_keys)
    child_env = {key: os.environ[key] for key in runtime_keys if key in os.environ}
    child_env.update(values)
    required = ("DATABASE_URL", "CSJOBS_CONTACT_EMAIL")
    missing = [
        key for key in required
        if not child_env.get(key)
        or "change-me" in child_env.get(key, "").lower()
        or (key == "DATABASE_URL" and ("<" in child_env[key] or ">" in child_env[key]))
        or (key == "CSJOBS_CONTACT_EMAIL" and ("example.org" in child_env[key].lower() or "your-project-contact" in child_env[key].lower()))
    ]
    if missing:
        raise SystemExit("Missing or placeholder required .env key(s): " + ", ".join(missing))

    commands = [
        ("preflight", [sys.executable, "-m", "app.v2.preflight"]),
        ("database migration", [sys.executable, "-m", "app.v2.migrate"]),
        ("regional pilots", None),
    ]
    for index, (name, command) in enumerate(commands):
        print(f"[stage2] Starting {name}.", flush=True)
        if name == "preflight":
            completed = subprocess.run(command, cwd=ROOT, env=child_env, check=False, capture_output=True, text=True)
            if completed.stdout:
                print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n", flush=True)
            if completed.stderr:
                print(completed.stderr, end="" if completed.stderr.endswith("\n") else "\n", file=sys.stderr, flush=True)
            if completed.returncode == 0:
                values.update(load_selected_env(env_path, safe_keys))
                child_env.update(values)
                discovery = next((line.strip() for line in completed.stdout.splitlines() if line.startswith("teamtailor: ")), "teamtailor: no verified feed found in the Arbeitnow sample")
                child_env["STAGE2_TEAMTAILOR_STATUS"] = discovery
                child_env["STAGE2_TEAMTAILOR_VERIFIED"] = "1" if discovery.startswith("teamtailor: verified ") else "0"
                arbeitnow_gate = next((line.rsplit(" ", 1)[-1].strip("[]") for line in completed.stdout.splitlines() if line.startswith("[ARBEITNOW_GATE] ")), "PASS")
                child_env["STAGE2_ARBEITNOW_ENABLED"] = "0" if arbeitnow_gate == "SKIP" else "1"
            else:
                failed_stage = next((line.partition(":")[2].split(".", 1)[0].strip() for line in completed.stdout.splitlines() if line.startswith("Preflight failed at stage:")), "preflight")
                print("[STAGE2_SUMMARY] " + json.dumps({"status": "stopped_at_preflight", "failed_stage": failed_stage}, ensure_ascii=False), flush=True)
        elif name == "regional pilots":
            # Preflight already passed once. Run each newly requested geography separately
            # so each gets its own 500-per-source cap, run record, and report.
            time.sleep(1.05)
            completed = None
            for region in ("002", "USA", "142"):
                label = {"002": "Africa", "USA": "USA", "142": "Asia"}[region]
                print(f"[stage3] Starting {label} pilot.", flush=True)
                region_env = dict(child_env)
                region_env["STAGE2_TARGET_REGION"] = region
                completed = subprocess.run(
                    [sys.executable, "-u", "scripts/run_stage2_europe_pilot.py"],
                    cwd=ROOT, env=region_env, check=False,
                )
                if completed.returncode:
                    print(f"[stage3] Stopped at {label} pilot (exit {completed.returncode}).", flush=True)
                    print("[STAGE3_SUMMARY] " + json.dumps({"status": "stopped_at_region", "region": label}, ensure_ascii=False), flush=True)
                    raise SystemExit(completed.returncode)
            print("[STAGE3_SUMMARY] completed_regions=Africa,USA,Asia", flush=True)
            if completed is None:
                raise RuntimeError("No regional pilot targets were configured")
        else:
            completed = subprocess.run(command, cwd=ROOT, env=child_env, check=False)
        if completed.returncode:
            print(f"[stage2] Stopped at {name} (exit {completed.returncode}).", flush=True)
            if name != "preflight":
                print("[STAGE2_SUMMARY] " + json.dumps({"status": "stopped_at_stage", "stage": name}, ensure_ascii=False), flush=True)
            raise SystemExit(completed.returncode)
    reports = ", ".join(f"docs/STAGE_3_{label}_PILOT_REPORT.md" for label in ("AFRICA", "USA", "ASIA"))
    print(f"[stage3] Complete. Reports: {reports}", flush=True)


if __name__ == "__main__":
    main()
