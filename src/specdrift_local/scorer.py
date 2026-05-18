from __future__ import annotations

import statistics

from specdrift_local.models import ApiScore, ApiSpec, CallResult, HarnessMode, PatchSuggestion


def mode_multiplier(mode: HarnessMode) -> float:
    return {HarnessMode.RAW_OPENAPI: 1.0, HarnessMode.MCP_WRAPPED: 0.78, HarnessMode.ROUTED: 0.64}[mode]


def evaluate_endpoint(api: ApiSpec, endpoint_index: int, mode: HarnessMode, iteration: int) -> CallResult:
    endpoint = api.endpoints[endpoint_index]
    spec_params = {param.name: param for param in endpoint.parameters}
    actual_params = endpoint.actual_accepts
    under_documented = sorted(set(actual_params) - set(spec_params))
    over_documented = sorted(set(spec_params) - set(actual_params))
    enum_drift = any(param.enum and endpoint.actual_accepts.get(param.name) == "free_text" for param in endpoint.parameters)
    response_match = endpoint.response_schema == endpoint.actual_response
    drift_weight = (len(under_documented) * 0.16 + len(over_documented) * 0.11 + (0.2 if enum_drift else 0) + (0.18 if not response_match else 0))
    adjusted = drift_weight * mode_multiplier(mode)
    success = adjusted < 0.28 or iteration % 5 == 0
    hallucinated = bool(under_documented or enum_drift) and mode != HarnessMode.ROUTED
    recovered = mode != HarnessMode.RAW_OPENAPI or adjusted < 0.22
    calls = 1 + int(adjusted * 8) + (1 if hallucinated else 0)
    drift_type = None
    if under_documented:
        drift_type = "under_documented_parameter"
    elif over_documented:
        drift_type = "over_documented_parameter"
    elif enum_drift:
        drift_type = "enum_free_text_mismatch"
    elif not response_match:
        drift_type = "response_schema_mismatch"
    return CallResult(
        api_id=api.id,
        endpoint=endpoint.operation_id,
        mode=mode,
        success=success,
        hallucinated_parameter=hallucinated,
        response_schema_match=response_match,
        error_recovered=recovered,
        calls_to_success=calls,
        drift_type=drift_type,
    )


def aci(results: list[CallResult]) -> float:
    if not results:
        return 0.0
    hallucination = sum(item.hallucinated_parameter for item in results) / len(results)
    response = sum(item.response_schema_match for item in results) / len(results)
    recovery = sum(item.error_recovered for item in results) / len(results)
    calls = statistics.median(item.calls_to_success for item in results)
    success = sum(item.success for item in results) / len(results)
    score = 100 * (0.32 * success + 0.24 * (1 - hallucination) + 0.22 * response + 0.14 * recovery + 0.08 * max(0, 1 - (calls - 1) / 5))
    return round(score, 2)


def score_api(api: ApiSpec, results: list[CallResult], patches: list[PatchSuggestion]) -> ApiScore:
    by_mode = {mode: [item for item in results if item.mode == mode] for mode in HarnessMode}
    hallucination = sum(item.hallucinated_parameter for item in results) / len(results)
    response = sum(item.response_schema_match for item in results) / len(results)
    recovery = sum(item.error_recovered for item in results) / len(results)
    calls = statistics.median(item.calls_to_success for item in results)
    gain = sum(item.estimated_aci_gain for item in patches if item.api_id == api.id)
    return ApiScore(
        api_id=api.id,
        title=api.title,
        aci=aci(results),
        raw_aci=aci(by_mode[HarnessMode.RAW_OPENAPI]),
        mcp_aci=aci(by_mode[HarnessMode.MCP_WRAPPED]),
        routed_aci=aci(by_mode[HarnessMode.ROUTED]),
        parameter_hallucination_rate=round(hallucination, 4),
        response_schema_match_rate=round(response, 4),
        error_recovery_rate=round(recovery, 4),
        median_calls_to_success=round(float(calls), 4),
        estimated_patch_gain=round(gain, 2),
        human_trust_rating=api.human_trust_rating,
    )


def suggest_patches(api: ApiSpec) -> list[PatchSuggestion]:
    suggestions: list[PatchSuggestion] = []
    for endpoint in api.endpoints:
        spec_params = {param.name: param for param in endpoint.parameters}
        actual = endpoint.actual_accepts
        for missing in sorted(set(actual) - set(spec_params)):
            value_type = actual[missing]
            suggestions.append(
                PatchSuggestion(
                    api_id=api.id,
                    endpoint=endpoint.operation_id,
                    issue=f"Parameter `{missing}` works but is missing from the spec.",
                    patch={"add_parameter": {"name": missing, "type": value_type, "required": False, "example": "example"}},
                    estimated_aci_gain=7.5,
                )
            )
        for extra in sorted(set(spec_params) - set(actual)):
            suggestions.append(
                PatchSuggestion(
                    api_id=api.id,
                    endpoint=endpoint.operation_id,
                    issue=f"Parameter `{extra}` is documented but not accepted by the API.",
                    patch={"remove_parameter": extra},
                    estimated_aci_gain=5.0,
                )
            )
        for param in endpoint.parameters:
            if param.enum and actual.get(param.name) == "free_text":
                suggestions.append(
                    PatchSuggestion(
                        api_id=api.id,
                        endpoint=endpoint.operation_id,
                        issue=f"Parameter `{param.name}` is documented as enum but behaves like free text.",
                        patch={"replace_enum_with_string": param.name, "add_examples": [param.example or "San Francisco"]},
                        estimated_aci_gain=9.0,
                    )
                )
        if endpoint.response_schema != endpoint.actual_response:
            suggestions.append(
                PatchSuggestion(
                    api_id=api.id,
                    endpoint=endpoint.operation_id,
                    issue="Response schema omits observed fields.",
                    patch={"update_response_schema": endpoint.actual_response},
                    estimated_aci_gain=6.0,
                )
            )
    return suggestions


def correlation(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2:
        return 1.0
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    den_x = sum((x - mx) ** 2 for x in xs) ** 0.5
    den_y = sum((y - my) ** 2 for y in ys) ** 0.5
    if den_x == 0 or den_y == 0:
        return 0.0
    return round(num / (den_x * den_y), 4)
