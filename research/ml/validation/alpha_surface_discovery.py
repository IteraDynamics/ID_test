from __future__ import annotations

"""Deterministic, observation-only primitives for Campaign #44."""

from copy import deepcopy
from typing import Any, Mapping, Sequence


SCORE_DIMENSIONS: tuple[str, ...] = (
    "independent_support_potential",
    "data_readiness",
    "economic_plausibility",
    "uniqueness",
    "falsifiability",
    "portfolio_relevance",
    "implementation_efficiency",
    "governance_readiness",
)

REQUIRED_INVENTORY_FIELDS: tuple[str, ...] = (
    "surface_id",
    "surface_name",
    "surface_class",
    "repository_sources",
    "governance_state",
    "anchor_availability",
    "leakage_state",
    "observation_unit",
    "independence_unit",
    "available_observation_count",
    "available_independence_count",
    "historical_span_start",
    "historical_span_end",
    "asset_scope",
    "candidate_horizons",
    "existing_evidence_state",
    "known_overlap_or_redundancy",
    "data_readiness_state",
    "estimated_implementation_complexity",
    "falsification_path",
    "portfolio_relevance_hypothesis",
    "notes",
    "rankable",
    "non_rankable_reasons",
    "scores",
)


class AlphaSurfaceDiscoveryValidationError(ValueError):
    """Raised when Campaign #44 inventory or scoring fails closed."""


def frozen_surface_inventory() -> list[dict[str, Any]]:
    """Return the finite, pre-result Campaign #44 alpha-surface inventory."""
    return deepcopy(
        [
            {
                "surface_id": "S-001",
                "surface_name": "Registered Core v1 collapse structure candidate A-001",
                "surface_class": "registered_candidate",
                "repository_sources": [
                    "docs/ITERA_CAMPAIGN_BOARD.md",
                    "docs/research/CORE_V1_HISTORICAL_ALPHA_DISCOVERY.md",
                    "docs/research/CORE_V1_HISTORICAL_ALPHA_DISCOVERY_R1.md",
                    "artifacts/core_v1_historical_alpha_discovery/btc_core_v1_alpha_candidates.json",
                    "artifacts/core_v1_historical_alpha_discovery/btc_core_v1_alpha_discovery_folds.csv",
                ],
                "governance_state": "GOVERNED",
                "anchor_availability": "ESTABLISHED",
                "leakage_state": "LEAKAGE_CONTROLS_ESTABLISHED",
                "observation_unit": "historical collapse episode",
                "independence_unit": "deterministic event family",
                "available_observation_count": 122,
                "available_independence_count": 14,
                "historical_span_start": "UNKNOWN",
                "historical_span_end": "UNKNOWN",
                "asset_scope": ["BTC"],
                "candidate_horizons": [24, 72],
                "existing_evidence_state": "PRELIMINARY_SUPPORTED_ASSOCIATION",
                "known_overlap_or_redundancy": "The severe-collapse and intrinsic-subtype rows share the same five independent families and must remain one nested candidate, not separate evidence.",
                "data_readiness_state": "READY_FOR_FINITE_FALSIFICATION",
                "estimated_implementation_complexity": 2,
                "falsification_path": "Freeze the 24-hour primary pattern and secondary 72-hour nested pattern; compare against unconditional and date-matched BTC baselines, anchor-period BTC behavior, and leave-one-family-out sensitivity without mining new descriptors.",
                "portfolio_relevance_hypothesis": "A sparse event-conditioned research sleeve could diversify continuous price-only signals if incremental information survives falsification.",
                "notes": "Registered Candidate A-001 only; no deployable-alpha claim.",
                "rankable": True,
                "non_rankable_reasons": [],
                "scores": {
                    "independent_support_potential": 2,
                    "data_readiness": 4,
                    "economic_plausibility": 3,
                    "uniqueness": 3,
                    "falsifiability": 4,
                    "portfolio_relevance": 2,
                    "implementation_efficiency": 4,
                    "governance_readiness": 4,
                },
            },
            {
                "surface_id": "S-002",
                "surface_name": "Historical regime state and transition structure",
                "surface_class": "regime_classification",
                "repository_sources": [
                    "research/ml/validation/historical_regime_taxonomy.py",
                    "artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_regimes.json",
                    "artifacts/core_v1_jump_risk_historical_regimes/btc_extended_up_historical_episodes.csv",
                    "tests/test_historical_regime_taxonomy.py",
                ],
                "governance_state": "GOVERNABLE_FROM_EXISTING_CANONICAL_ARTIFACTS",
                "anchor_availability": "ESTABLISHED_FOR_EPISODE_WINDOWS",
                "leakage_state": "REQUIRES_ANCHOR_LOCAL_FIELD_FREEZE",
                "observation_unit": "historical regime episode or transition",
                "independence_unit": "non-overlapping event family or chronologically separated transition",
                "available_observation_count": 122,
                "available_independence_count": 14,
                "historical_span_start": "UNKNOWN",
                "historical_span_end": "UNKNOWN",
                "asset_scope": ["BTC"],
                "candidate_horizons": "TO_BE_FROZEN_IN_LATER_CAMPAIGN",
                "existing_evidence_state": "STRUCTURAL_ARTIFACT_AVAILABLE_NO_NEW_RETURN_TEST",
                "known_overlap_or_redundancy": "Overlaps Campaign #43 event families and must not count overlapping episode windows as independent observations.",
                "data_readiness_state": "READY_FOR_CANDIDATE_FREEZE",
                "estimated_implementation_complexity": 2,
                "falsification_path": "Pre-register a finite transition inventory, anchor-local fields, independent-family resolution, horizons, and chronological folds; reject if direction or incremental value is unstable out of sample.",
                "portfolio_relevance_hypothesis": "Regime-conditioned information may identify when other alpha families should be expected to work or fail, without itself becoming a production regime switch.",
                "notes": "Campaign #44 does not inspect predictive outcomes for this surface.",
                "rankable": True,
                "non_rankable_reasons": [],
                "scores": {
                    "independent_support_potential": 3,
                    "data_readiness": 4,
                    "economic_plausibility": 4,
                    "uniqueness": 3,
                    "falsifiability": 4,
                    "portfolio_relevance": 4,
                    "implementation_efficiency": 3,
                    "governance_readiness": 4,
                },
            },
            {
                "surface_id": "S-003",
                "surface_name": "Historical event persistence, clustering, duration, and spacing",
                "surface_class": "event_structure",
                "repository_sources": [
                    "research/ml/validation/historical_event_families.py",
                    "artifacts/core_v1_historical_event_families/btc_extended_up_event_families.json",
                    "artifacts/core_v1_historical_event_families/btc_extended_up_event_family_membership.csv",
                    "artifacts/core_v1_event_robustness/btc_extended_up_event_robustness.json",
                    "tests/test_historical_event_families.py",
                ],
                "governance_state": "GOVERNED",
                "anchor_availability": "ESTABLISHED_FOR_EVENT_WINDOWS",
                "leakage_state": "REQUIRES_PRE_ANCHOR_OR_AT_ANCHOR_FEATURE_FREEZE",
                "observation_unit": "event family",
                "independence_unit": "event family",
                "available_observation_count": 14,
                "available_independence_count": 14,
                "historical_span_start": "UNKNOWN",
                "historical_span_end": "UNKNOWN",
                "asset_scope": ["BTC"],
                "candidate_horizons": "TO_BE_FROZEN_IN_LATER_CAMPAIGN",
                "existing_evidence_state": "ROBUSTNESS_AND_FAMILY_STRUCTURE_AVAILABLE_NO_NEW_RETURN_TEST",
                "known_overlap_or_redundancy": "Uses the same 14 families as Campaign #43; structural descriptors must be evaluated as a separate hypothesis family without duplicating A-001 evidence.",
                "data_readiness_state": "READY_FOR_CANDIDATE_FREEZE",
                "estimated_implementation_complexity": 2,
                "falsification_path": "Freeze a small set of anchor-available structural descriptors and reject candidates that fail leave-one-family-out, chronological, or simple-price-baseline comparisons.",
                "portfolio_relevance_hypothesis": "Event recurrence and persistence may describe signal timing or conditional risk at horizons distinct from continuous predictors.",
                "notes": "Independent sample remains small and must be treated as a binding constraint.",
                "rankable": True,
                "non_rankable_reasons": [],
                "scores": {
                    "independent_support_potential": 2,
                    "data_readiness": 4,
                    "economic_plausibility": 3,
                    "uniqueness": 4,
                    "falsifiability": 4,
                    "portfolio_relevance": 3,
                    "implementation_efficiency": 3,
                    "governance_readiness": 4,
                },
            },
            {
                "surface_id": "S-004",
                "surface_name": "Model confidence and calibration state",
                "surface_class": "model_diagnostics",
                "repository_sources": [
                    "research/ml/calibration/model_store.py",
                    "research/ml/calibration/training_data.py",
                    "research/ml/calibration/platt_calibrator.py",
                    "research/ml/calibration/regime_calibrator.py",
                    "research/ml/validation/report.py",
                ],
                "governance_state": "PARTIALLY_GOVERNED_CODE_SURFACE",
                "anchor_availability": "NOT_YET_ESTABLISHED_FOR_HISTORICAL_RESEARCH_ROWS",
                "leakage_state": "UNRESOLVED",
                "observation_unit": "UNKNOWN",
                "independence_unit": "UNKNOWN",
                "available_observation_count": "UNKNOWN",
                "available_independence_count": "UNKNOWN",
                "historical_span_start": "UNKNOWN",
                "historical_span_end": "UNKNOWN",
                "asset_scope": "UNKNOWN",
                "candidate_horizons": "UNKNOWN",
                "existing_evidence_state": "CODE_SURFACE_EXISTS_DATASET_GOVERNANCE_UNESTABLISHED",
                "known_overlap_or_redundancy": "Potential overlap with raw model confidence and regime outputs is unresolved.",
                "data_readiness_state": "NOT_RANKABLE",
                "estimated_implementation_complexity": 3,
                "falsification_path": "First establish immutable historical rows, exact prediction timestamps, calibration provenance, anchor locality, and an independence unit; only then freeze a predictive test.",
                "portfolio_relevance_hypothesis": "Calibration state could identify conditional reliability or crowding of model-derived signals if a governed historical dataset exists.",
                "notes": "Unknowns remain explicit; repository code alone does not establish a governed historical alpha surface.",
                "rankable": False,
                "non_rankable_reasons": [
                    "anchor availability cannot be established",
                    "predictor leakage is unresolved",
                    "historical source identity and schema are not frozen",
                ],
                "scores": {},
            },
            {
                "surface_id": "S-005",
                "surface_name": "Model disagreement and consensus",
                "surface_class": "model_diagnostics",
                "repository_sources": [
                    "docs/research/ALPHA_SURFACE_DISCOVERY_AND_PRIORITIZATION.md",
                ],
                "governance_state": "INSUFFICIENT_REPOSITORY_EVIDENCE",
                "anchor_availability": "UNKNOWN",
                "leakage_state": "UNKNOWN",
                "observation_unit": "UNKNOWN",
                "independence_unit": "UNKNOWN",
                "available_observation_count": "UNKNOWN",
                "available_independence_count": "UNKNOWN",
                "historical_span_start": "UNKNOWN",
                "historical_span_end": "UNKNOWN",
                "asset_scope": "UNKNOWN",
                "candidate_horizons": "UNKNOWN",
                "existing_evidence_state": "CONCEPTUAL_ELIGIBLE_CLASS_ONLY",
                "known_overlap_or_redundancy": "UNKNOWN",
                "data_readiness_state": "NOT_RANKABLE",
                "estimated_implementation_complexity": 4,
                "falsification_path": "Identify a concrete repository-tracked historical disagreement dataset before proposing a finite test.",
                "portfolio_relevance_hypothesis": "Disagreement may identify uncertainty, information conflict, or transition risk, but this remains a conceptual hypothesis.",
                "notes": "Campaign #44 must not infer implementation or data availability from prior discussions.",
                "rankable": False,
                "non_rankable_reasons": [
                    "repository evidence is insufficient without speculation",
                    "anchor availability cannot be established",
                    "source identity and schema cannot be governed",
                ],
                "scores": {},
            },
            {
                "surface_id": "S-006",
                "surface_name": "Cross-origin signal agreement and divergence",
                "surface_class": "cross_origin",
                "repository_sources": [
                    "docs/research/ALPHA_SURFACE_DISCOVERY_AND_PRIORITIZATION.md",
                ],
                "governance_state": "INSUFFICIENT_REPOSITORY_EVIDENCE",
                "anchor_availability": "UNKNOWN",
                "leakage_state": "UNKNOWN",
                "observation_unit": "UNKNOWN",
                "independence_unit": "UNKNOWN",
                "available_observation_count": "UNKNOWN",
                "available_independence_count": "UNKNOWN",
                "historical_span_start": "UNKNOWN",
                "historical_span_end": "UNKNOWN",
                "asset_scope": "UNKNOWN",
                "candidate_horizons": "UNKNOWN",
                "existing_evidence_state": "CONCEPTUAL_ELIGIBLE_CLASS_ONLY",
                "known_overlap_or_redundancy": "Potential overlap with confidence, consensus, and market-regime surfaces is unknown.",
                "data_readiness_state": "NOT_RANKABLE",
                "estimated_implementation_complexity": 4,
                "falsification_path": "Establish governed origin-specific histories, timestamp alignment, missingness rules, and an anchor-local agreement definition before any outcome test.",
                "portfolio_relevance_hypothesis": "Independent information origins could diversify price-derived signals if their histories and timing are governable.",
                "notes": "No source availability, count, or span is inferred.",
                "rankable": False,
                "non_rankable_reasons": [
                    "repository evidence is insufficient without speculation",
                    "anchor availability cannot be established",
                    "source identity and schema cannot be governed",
                ],
                "scores": {},
            },
            {
                "surface_id": "S-007",
                "surface_name": "Post-anchor recovery outcomes",
                "surface_class": "recovery_characteristics",
                "repository_sources": [
                    "docs/research/CORE_V1_HISTORICAL_ALPHA_DISCOVERY.md",
                    "research/ml/validation/historical_alpha_discovery.py",
                    "artifacts/core_v1_jump_risk_recovery_subtypes/btc_extended_up_episode_signatures.csv",
                ],
                "governance_state": "GOVERNED_BUT_EXCLUDED_AS_PREDICTOR",
                "anchor_availability": "POST_ANCHOR_INFORMATION",
                "leakage_state": "KNOWN_LOOK_AHEAD",
                "observation_unit": "historical collapse episode",
                "independence_unit": "deterministic event family",
                "available_observation_count": 122,
                "available_independence_count": 14,
                "historical_span_start": "UNKNOWN",
                "historical_span_end": "UNKNOWN",
                "asset_scope": ["BTC"],
                "candidate_horizons": [],
                "existing_evidence_state": "EXCLUDED_BY_CAMPAIGN_43_LEAKAGE_CONTROLS",
                "known_overlap_or_redundancy": "Recovery outcomes describe information observed after the predictive anchor.",
                "data_readiness_state": "NOT_RANKABLE",
                "estimated_implementation_complexity": 1,
                "falsification_path": "No predictive test is authorized unless a future campaign defines a distinct earlier anchor at which every predictor is actually available.",
                "portfolio_relevance_hypothesis": "None in the currently governed predictor framing.",
                "notes": "Visible negative inventory result; must remain excluded rather than transformed around the leakage rule.",
                "rankable": False,
                "non_rankable_reasons": ["predictor leakage is known"],
                "scores": {},
            },
            {
                "surface_id": "S-008",
                "surface_name": "Simple BTC price-state baselines",
                "surface_class": "market_price",
                "repository_sources": [
                    "data/btcusd_3600s_2018-01-01_to_2025-12-31.csv",
                    "docs/research/CORE_V1_HISTORICAL_ALPHA_DISCOVERY_R1.md",
                    "scripts/run_core_v1_historical_alpha_discovery.py",
                ],
                "governance_state": "GOVERNED_LOCAL_RESEARCH_INPUT",
                "anchor_availability": "ESTABLISHED",
                "leakage_state": "CAN_BE_FROZEN_ANCHOR_LOCAL",
                "observation_unit": "exact hourly BTC observation",
                "independence_unit": "chronologically separated observation or event-matched control",
                "available_observation_count": 70069,
                "available_independence_count": "TO_BE_DEFINED_BY_TEST_DESIGN",
                "historical_span_start": "2018-01-01 00:00:00",
                "historical_span_end": "2025-12-31 00:00:00",
                "asset_scope": ["BTC"],
                "candidate_horizons": "TO_BE_FROZEN_IN_LATER_CAMPAIGN",
                "existing_evidence_state": "GOVERNED_PRICE_SOURCE_AVAILABLE_NO_NEW_RETURN_TEST",
                "known_overlap_or_redundancy": "This is the required simple baseline against which more complex Itera surfaces should demonstrate incremental information.",
                "data_readiness_state": "READY_FOR_BASELINE_DESIGN",
                "estimated_implementation_complexity": 1,
                "falsification_path": "Freeze a minimal non-overlapping set of anchor-local price states and use them as null and incremental-information controls rather than mining a large technical-indicator library.",
                "portfolio_relevance_hypothesis": "Simple price states establish whether proprietary surfaces add information beyond low-complexity market behavior.",
                "notes": "Baseline research surface, not a license for arbitrary technical-indicator search.",
                "rankable": True,
                "non_rankable_reasons": [],
                "scores": {
                    "independent_support_potential": 4,
                    "data_readiness": 4,
                    "economic_plausibility": 3,
                    "uniqueness": 0,
                    "falsifiability": 4,
                    "portfolio_relevance": 3,
                    "implementation_efficiency": 4,
                    "governance_readiness": 4,
                },
            },
        ]
    )


def validate_inventory(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate exact Campaign #44 inventory fields and fail-closed states."""
    if not rows:
        raise AlphaSurfaceDiscoveryValidationError("inventory must not be empty")
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for source in rows:
        missing = set(REQUIRED_INVENTORY_FIELDS) - set(source)
        extra = set(source) - set(REQUIRED_INVENTORY_FIELDS)
        if missing or extra:
            raise AlphaSurfaceDiscoveryValidationError(
                f"inventory fields mismatch; missing={sorted(missing)} extra={sorted(extra)}"
            )
        row = deepcopy(dict(source))
        surface_id = str(row["surface_id"])
        if not surface_id or surface_id in seen_ids:
            raise AlphaSurfaceDiscoveryValidationError("surface_id values must be unique and non-empty")
        seen_ids.add(surface_id)
        sources = row["repository_sources"]
        if not isinstance(sources, list) or not sources or any(not str(path) for path in sources):
            raise AlphaSurfaceDiscoveryValidationError(
                f"{surface_id} must cite at least one concrete repository source"
            )
        rankable = row["rankable"]
        if not isinstance(rankable, bool):
            raise AlphaSurfaceDiscoveryValidationError(f"{surface_id} rankable must be boolean")
        reasons = row["non_rankable_reasons"]
        scores = row["scores"]
        if rankable:
            if reasons:
                raise AlphaSurfaceDiscoveryValidationError(
                    f"{surface_id} rankable surface cannot have non-rankable reasons"
                )
            if set(scores) != set(SCORE_DIMENSIONS):
                raise AlphaSurfaceDiscoveryValidationError(
                    f"{surface_id} scores must match frozen dimensions exactly"
                )
            for dimension in SCORE_DIMENSIONS:
                value = scores[dimension]
                if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 4:
                    raise AlphaSurfaceDiscoveryValidationError(
                        f"{surface_id} {dimension} score must be an integer from 0 through 4"
                    )
        else:
            if not isinstance(reasons, list) or not reasons:
                raise AlphaSurfaceDiscoveryValidationError(
                    f"{surface_id} non-rankable surface requires explicit reasons"
                )
            if scores:
                raise AlphaSurfaceDiscoveryValidationError(
                    f"{surface_id} non-rankable surface must not receive scores"
                )
        complexity = row["estimated_implementation_complexity"]
        if isinstance(complexity, bool) or not isinstance(complexity, int) or not 0 <= complexity <= 4:
            raise AlphaSurfaceDiscoveryValidationError(
                f"{surface_id} implementation complexity must be an integer from 0 through 4"
            )
        normalized.append(row)
    if "S-001" not in seen_ids:
        raise AlphaSurfaceDiscoveryValidationError("registered Candidate A-001 must remain visible")
    return sorted(normalized, key=lambda row: str(row["surface_id"]))


def priority_record(row: Mapping[str, Any]) -> dict[str, Any]:
    """Create one deterministic research-priority record for a rankable surface."""
    if not row.get("rankable"):
        raise AlphaSurfaceDiscoveryValidationError("non-rankable surfaces cannot receive priority records")
    scores = row["scores"]
    total = sum(int(scores[dimension]) for dimension in SCORE_DIMENSIONS)
    return {
        "surface_id": str(row["surface_id"]),
        "surface_name": str(row["surface_name"]),
        "total_score": total,
        **{dimension: int(scores[dimension]) for dimension in SCORE_DIMENSIONS},
        "estimated_implementation_complexity": int(row["estimated_implementation_complexity"]),
        "falsification_path": str(row["falsification_path"]),
        "portfolio_relevance_hypothesis": str(row["portfolio_relevance_hypothesis"]),
    }


def priority_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    """Return the frozen Campaign #44 deterministic ranking tuple."""
    return (
        -int(row["total_score"]),
        -int(row["independent_support_potential"]),
        -int(row["uniqueness"]),
        -int(row["falsifiability"]),
        -int(row["portfolio_relevance"]),
        int(row["estimated_implementation_complexity"]),
        str(row["surface_id"]),
    )


def rank_surfaces(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate inventory and rank only eligible research programs."""
    inventory = validate_inventory(rows)
    priorities = [priority_record(row) for row in inventory if row["rankable"]]
    ordered = sorted(priorities, key=priority_key)
    for rank, row in enumerate(ordered, start=1):
        row["rank"] = rank
    return ordered
