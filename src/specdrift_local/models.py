from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class HarnessMode(StrEnum):
    RAW_OPENAPI = "raw_openapi"
    MCP_WRAPPED = "mcp_wrapped"
    ROUTED = "routed"


class ParameterSpec(BaseModel):
    name: str
    type: str
    required: bool = False
    enum: list[str] | None = None
    example: Any | None = None


class EndpointSpec(BaseModel):
    method: str
    path: str
    operation_id: str
    parameters: list[ParameterSpec]
    response_schema: dict[str, str]
    actual_accepts: dict[str, str]
    actual_response: dict[str, str]


class ApiSpec(BaseModel):
    id: str
    title: str
    category: str
    endpoints: list[EndpointSpec]
    human_trust_rating: float


class CallResult(BaseModel):
    api_id: str
    endpoint: str
    mode: HarnessMode
    success: bool
    hallucinated_parameter: bool
    response_schema_match: bool
    error_recovered: bool
    calls_to_success: int
    drift_type: str | None = None


class ApiScore(BaseModel):
    api_id: str
    title: str
    aci: float
    raw_aci: float
    mcp_aci: float
    routed_aci: float
    parameter_hallucination_rate: float
    response_schema_match_rate: float
    error_recovery_rate: float
    median_calls_to_success: float
    estimated_patch_gain: float
    human_trust_rating: float


class PatchSuggestion(BaseModel):
    api_id: str
    endpoint: str
    issue: str
    patch: dict[str, Any]
    estimated_aci_gain: float


class RunSummary(BaseModel):
    run_id: str
    api_count: int
    result_count: int
    avg_aci: float
    aci_human_correlation: float
    patch_success_rate: float
    generated_mcp_descriptors: int
    pass_gates: bool


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]
