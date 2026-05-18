from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

import duckdb

from specdrift_local.models import ApiScore, CallResult, HarnessMode, PatchSuggestion, RunSummary, project_root
from specdrift_local.scorer import correlation, evaluate_endpoint, score_api, suggest_patches
from specdrift_local.specs import load_specs


def init_demo(force: bool = False) -> dict[str, str]:
    root = project_root()
    for name in ("data", "runs", "outputs"):
        path = root / name
        if force and path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
    return {"specs": str(root / "specs" / "apis.json"), "outputs": str(root / "outputs")}


def connect_store(path: Path) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(path))
    conn.execute(
        """
        create table if not exists api_scores (
          run_id varchar,
          api_id varchar,
          title varchar,
          aci double,
          raw_aci double,
          mcp_aci double,
          routed_aci double,
          parameter_hallucination_rate double,
          response_schema_match_rate double,
          error_recovery_rate double,
          median_calls_to_success double,
          estimated_patch_gain double,
          human_trust_rating double
        )
        """
    )
    conn.execute(
        """
        create table if not exists call_results (
          run_id varchar,
          api_id varchar,
          endpoint varchar,
          mode varchar,
          success boolean,
          hallucinated_parameter boolean,
          response_schema_match boolean,
          error_recovered boolean,
          calls_to_success integer,
          drift_type varchar
        )
        """
    )
    conn.execute(
        """
        create table if not exists patches (
          run_id varchar,
          api_id varchar,
          endpoint varchar,
          issue varchar,
          estimated_aci_gain double
        )
        """
    )
    return conn


def persist(conn: duckdb.DuckDBPyConnection, run_id: str, scores: list[ApiScore], results: list[CallResult], patches: list[PatchSuggestion]) -> None:
    conn.executemany(
        "insert into api_scores values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                run_id,
                score.api_id,
                score.title,
                score.aci,
                score.raw_aci,
                score.mcp_aci,
                score.routed_aci,
                score.parameter_hallucination_rate,
                score.response_schema_match_rate,
                score.error_recovery_rate,
                score.median_calls_to_success,
                score.estimated_patch_gain,
                score.human_trust_rating,
            )
            for score in scores
        ],
    )
    conn.executemany(
        "insert into call_results values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                run_id,
                result.api_id,
                result.endpoint,
                result.mode.value,
                result.success,
                result.hallucinated_parameter,
                result.response_schema_match,
                result.error_recovered,
                result.calls_to_success,
                result.drift_type,
            )
            for result in results
        ],
    )
    if patches:
        conn.executemany(
            "insert into patches values (?, ?, ?, ?, ?)",
            [(run_id, patch.api_id, patch.endpoint, patch.issue, patch.estimated_aci_gain) for patch in patches],
        )


def write_outputs(patches: list[PatchSuggestion], scores: list[ApiScore]) -> tuple[int, int]:
    root = project_root()
    patch_dir = root / "outputs" / "patches"
    mcp_dir = root / "outputs" / "mcp"
    for directory in (patch_dir, mcp_dir):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)
    for index, patch in enumerate(patches, start=1):
        path = patch_dir / f"{index:03d}_{patch.api_id}_{patch.endpoint}.json"
        path.write_text(patch.model_dump_json(indent=2), encoding="utf-8")
    for score in scores:
        descriptor = {
            "server": f"{score.api_id}-mcp",
            "tools": [
                {
                    "name": f"{score.api_id}.call",
                    "description": f"Generated local MCP descriptor for {score.title}; ACI {score.aci}.",
                    "inputSchema": {"type": "object", "additionalProperties": True},
                }
            ],
        }
        (mcp_dir / f"{score.api_id}.json").write_text(json.dumps(descriptor, indent=2), encoding="utf-8")
    return len(list(patch_dir.glob("*.json"))), len(list(mcp_dir.glob("*.json")))


def score_suite(iterations: int = 20) -> RunSummary:
    init_demo()
    started = time.perf_counter()
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    root = project_root()
    run_dir = root / "runs" / "latest"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    specs = load_specs()
    all_results: list[CallResult] = []
    all_patches: list[PatchSuggestion] = []
    scores: list[ApiScore] = []
    for api in specs:
        api_results: list[CallResult] = []
        patches = suggest_patches(api)
        for iteration in range(iterations):
            for index, _endpoint in enumerate(api.endpoints):
                for mode in HarnessMode:
                    result = evaluate_endpoint(api, index, mode, iteration)
                    api_results.append(result)
                    all_results.append(result)
        all_patches.extend(patches)
        scores.append(score_api(api, api_results, patches))
    patch_count, mcp_count = write_outputs(all_patches, scores)
    conn = connect_store(run_dir / "specdrift.duckdb")
    persist(conn, run_id, scores, all_results, all_patches)
    conn.close()
    aci_corr = correlation([score.aci for score in scores], [score.human_trust_rating for score in scores])
    successful_patches = sum(1 for score in scores if score.estimated_patch_gain >= 5)
    summary = RunSummary(
        run_id=run_id,
        api_count=len(specs),
        result_count=len(all_results),
        avg_aci=round(sum(score.aci for score in scores) / len(scores), 4),
        aci_human_correlation=aci_corr,
        patch_success_rate=round(successful_patches / len(scores), 4),
        generated_mcp_descriptors=mcp_count,
        pass_gates=aci_corr >= 0.85 and successful_patches / len(scores) >= 0.7 and mcp_count == len(specs) and patch_count >= 5,
    )
    (root / "outputs" / "summary.json").write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    (root / "outputs" / "run_meta.json").write_text(json.dumps({"elapsed_seconds": round(time.perf_counter() - started, 4)}, indent=2), encoding="utf-8")
    return summary


def verify_outputs() -> dict[str, Any]:
    root = project_root()
    summary_path = root / "outputs" / "summary.json"
    db_path = root / "runs" / "latest" / "specdrift.duckdb"
    patch_dir = root / "outputs" / "patches"
    mcp_dir = root / "outputs" / "mcp"
    if not summary_path.exists() or not db_path.exists() or not patch_dir.exists() or not mcp_dir.exists():
        raise FileNotFoundError("Run `uv run specdrift-local score` before verification.")
    summary = RunSummary.model_validate_json(summary_path.read_text(encoding="utf-8"))
    conn = duckdb.connect(str(db_path), read_only=True)
    api_rows = conn.execute("select count(*) from api_scores").fetchone()[0]
    result_rows = conn.execute("select count(*) from call_results").fetchone()[0]
    drift_rows = conn.execute("select count(*) from call_results where drift_type is not null").fetchone()[0]
    conn.close()
    patches = len(list(patch_dir.glob("*.json")))
    mcps = len(list(mcp_dir.glob("*.json")))
    checks = {
        "required_outputs_present": summary_path.exists() and db_path.exists() and patch_dir.exists() and mcp_dir.exists(),
        "five_api_scorecards": api_rows == 5,
        "result_count_at_least_300": result_rows >= 300,
        "drift_rows_present": drift_rows >= 50,
        "human_correlation_at_least_0_85": summary.aci_human_correlation >= 0.85,
        "patch_success_rate_at_least_0_70": summary.patch_success_rate >= 0.7,
        "patch_files_generated": patches >= 5,
        "mcp_descriptors_for_all_apis": mcps == 5,
    }
    return {"run_id": summary.run_id, "summary": summary.model_dump(), "checks": checks, "passed": all(checks.values())}


def export_demo_pack() -> Path:
    root = project_root()
    pack = root / "outputs" / "demo_pack"
    if pack.exists():
        shutil.rmtree(pack)
    pack.mkdir(parents=True, exist_ok=True)
    for name in ("summary.json", "dashboard.html", "run_meta.json"):
        source = root / "outputs" / name
        if source.exists():
            shutil.copy2(source, pack / name)
    shutil.copytree(root / "outputs" / "patches", pack / "patches")
    shutil.copytree(root / "outputs" / "mcp", pack / "mcp")
    shutil.copy2(root / "specs" / "apis.json", pack / "apis.json")
    return pack
