# Frozen digest and JSON inventory

Baseline: `f332255139b613af0ffa1d227585db47fb8a8fb4`.

306 explicit constructor/serialization call sites. This is a static inventory,
not a count of independent formats or an assertion of runtime reachability.
Aliases of stdlib imports are resolved; dynamic calls and external schedules are not.
Caller-owned CSV options, file encodings, newline modes and publication order remain unchanged.

| File | Line | Operation | Input expression | Explicit options |
| --- | ---: | --- | --- | --- |
| research/campaign50_equity_breadth.py | 85 | hashlib.sha256 |  |  |
| research/campaign50_equity_breadth.py | 93 | json.dumps | payload | sort_keys=True, indent=2, allow_nan=False |
| research/campaign51_conditional_directional.py | 91 | hashlib.sha256 | payload |  |
| research/campaign51_conditional_directional.py | 288 | json.dumps | payload | sort_keys=True, separators=(',', ':'), allow_nan=False |
| research/harness/artifacts.py | 100 | json.dump | summary, f | indent=2, default=str |
| research/harness/campaign52_development.py | 117 | hashlib.sha256 | text.encode('utf-8') |  |
| research/jump_risk_engine/lab.py | 649 | json.dumps | report | indent=2, default=str |
| research/live_benchmarks.py | 119 | hashlib.sha256 |  |  |
| research/live_benchmarks.py | 127 | json.dumps | payload | sort_keys=True, indent=2, allow_nan=False |
| research/ml/calibration/model_store.py | 116 | json.dump | data, f | indent=2 |
| research/ml/calibration/model_store.py | 121 | json.dump | data, f | indent=2 |
| research/ml/validation/drift_detector.py | 428 | hashlib.sha256 | json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8') |  |
| research/ml/validation/drift_detector.py | 429 | json.dumps | payload | sort_keys=True, separators=(',', ':'), allow_nan=False |
| research/ml/validation/drift_diagnosis.py | 314 | hashlib.sha256 | json.dumps(payload, sort_keys=True, separators=(',', ':')).encode() |  |
| research/ml/validation/drift_diagnosis.py | 314 | json.dumps | payload | sort_keys=True, separators=(',', ':') |
| research/ml/validation/drift_diagnosis_v2.py | 213 | hashlib.sha256 | json.dumps(payload, sort_keys=True, separators=(',', ':')).encode() |  |
| research/ml/validation/drift_diagnosis_v2.py | 213 | json.dumps | payload | sort_keys=True, separators=(',', ':') |
| research/ml/validation/event_robustness.py | 30 | json.dumps | payload | sort_keys=True, separators=(',', ':'), allow_nan=False, ensure_ascii=False |
| research/ml/validation/event_robustness.py | 34 | hashlib.sha256 | canonical.encode('utf-8') |  |
| research/ml/validation/full_historical_regime_state_sequence.py | 56 | hashlib.sha256 | data |  |
| research/ml/validation/full_historical_regime_state_sequence.py | 60 | hashlib.sha256 |  |  |
| research/ml/validation/full_historical_regime_state_sequence.py | 290 | json.dumps | payload | sort_keys=True, indent=2, allow_nan=False |
| research/ml/validation/historical_event_families.py | 189 | json.dumps | payload | sort_keys=True, separators=(',', ':'), allow_nan=False, ensure_ascii=False |
| research/ml/validation/historical_event_families.py | 193 | hashlib.sha256 | canonical.encode('utf-8') |  |
| research/ml/validation/historical_regime_structure_discovery.py | 117 | hashlib.sha256 | data |  |
| research/ml/validation/historical_regime_structure_discovery.py | 121 | hashlib.sha256 |  |  |
| research/ml/validation/historical_regime_structure_discovery.py | 150 | json.dumps | _normalise(payload) | sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False |
| research/ml/validation/historical_regime_structure_discovery.py | 164 | json.dumps | value | sort_keys=True, separators=(',', ':'), allow_nan=False |
| research/ml/validation/historical_regime_structure_discovery.py | 736 | json.dumps | file_hashes | sort_keys=True, separators=(',', ':') |
| research/ml/validation/historical_regime_taxonomy.py | 248 | json.dumps | summary | sort_keys=True, separators=(',', ':'), allow_nan=False |
| research/ml/validation/historical_regime_taxonomy.py | 249 | hashlib.sha256 | canonical.encode('utf-8') |  |
| research/ml/validation/historical_regime_taxonomy_report.py | 68 | json.dumps | payload | sort_keys=True, separators=(',', ':'), allow_nan=False |
| research/ml/validation/historical_regime_taxonomy_report.py | 69 | hashlib.sha256 | canonical.encode('utf-8') |  |
| research/ml/validation/historical_regime_transition_discovery.py | 116 | hashlib.sha256 | data |  |
| research/ml/validation/historical_regime_transition_discovery.py | 120 | hashlib.sha256 |  |  |
| research/ml/validation/historical_regime_transition_discovery.py | 173 | json.dumps | normalised | sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False |
| research/ml/validation/historical_regime_transition_discovery.py | 191 | json.dumps | _normalise_scalar(value) | sort_keys=True, separators=(',', ':'), allow_nan=False |
| research/ml/validation/historical_regime_transition_discovery.py | 1157 | json.dumps | manifest | sort_keys=True, separators=(',', ':'), allow_nan=False |
| research/ml/validation/report.py | 497 | json.dump | payload, f | indent=2, default=str |
| research/ml/validation/report.py | 505 | json.dump | agg, f | indent=2, default=str |
| research/ml/validation/simple_btc_price_state_predictive_baselines.py | 147 | hashlib.sha256 | data |  |
| research/ml/validation/simple_btc_price_state_predictive_baselines.py | 151 | hashlib.sha256 |  |  |
| research/ml/validation/simple_btc_price_state_predictive_baselines.py | 173 | json.dumps | _normalise(payload) | sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False |
| research/ml/validation/simple_btc_price_state_predictive_baselines.py | 195 | json.dumps | value | sort_keys=True, separators=(',', ':'), allow_nan=False |
| research/ml_lab/evidence.py | 14 | hashlib.sha256 |  |  |
| research/ml_lab/experiments/experiment_005.py | 227 | json.dumps | report | indent=2, sort_keys=True |
| research/ml_lab/experiments/experiment_005.py | 228 | json.dumps | report | indent=2, sort_keys=True |
| research/ml_lab/experiments/experiment_006.py | 407 | json.dumps | report | indent=2, sort_keys=True |
| research/ml_lab/experiments/experiment_006.py | 408 | json.dumps | report | indent=2, sort_keys=True |
| research/ml_lab/experiments/experiment_007.py | 327 | json.dumps | report | indent=2, sort_keys=True |
| research/ml_lab/experiments/experiment_007.py | 329 | json.dumps | report | indent=2, sort_keys=True |
| research/ml_lab/experiments/experiment_008.py | 406 | json.dumps | report | indent=2, sort_keys=True, default=str |
| research/ml_lab/experiments/experiment_008.py | 408 | json.dumps | report | indent=2, sort_keys=True, default=str |
| research/ml_lab/experiments/experiment_009.py | 282 | json.dumps | report | indent=2, sort_keys=True |
| research/ml_lab/experiments/experiment_009.py | 283 | json.dumps | report | indent=2, sort_keys=True |
| research/ml_lab/experiments/experiment_010.py | 426 | json.dumps | report | indent=2, sort_keys=True |
| research/ml_lab/experiments/experiment_010.py | 428 | json.dumps | report | indent=2, sort_keys=True |
| research/ml_lab/experiments/experiment_011.py | 539 | json.dumps | report | indent=2, sort_keys=True, default=_json_default |
| research/research_engine/cache.py | 27 | json.dumps | self.canonical_payload() | sort_keys=True, separators=(',', ':'), default=str |
| research/research_engine/cache.py | 28 | hashlib.sha256 | raw.encode('utf-8') |  |
| research/research_engine/cache.py | 104 | hashlib.sha256 |  |  |
| research/research_engine/cache.py | 113 | json.dumps | payload | indent=2, sort_keys=True, default=str |
| research/research_engine/registry.py | 46 | json.dumps | payload | sort_keys=True, separators=(',', ':'), default=str |
| research/research_engine/registry.py | 47 | hashlib.sha256 | raw.encode('utf-8') |  |
| research/research_engine/registry.py | 110 | json.dumps | payload | indent=2, sort_keys=True, default=str |
| runtime/argus/state/runtime_state.py | 70 | json.dump | data, f | indent=2, default=str |
| runtime/core_v1/jump_risk_overlay.py | 89 | json.dumps | config_payload(max_input_age_seconds) | sort_keys=True, separators=(',', ':') |
| runtime/core_v1/jump_risk_overlay.py | 92 | hashlib.sha256 | payload.encode('utf-8') |  |
| runtime/core_v1/jump_risk_replay_provider.py | 34 | json.dumps | payload | sort_keys=True, separators=(',', ':'), default=str |
| runtime/core_v1/jump_risk_replay_provider.py | 38 | hashlib.sha256 | _canonical_json(payload) |  |
| runtime/core_v1/state_io.py | 19 | json.dumps | record | default=str, sort_keys=True |
| runtime/core_v1/state_io.py | 25 | json.dumps | payload | indent=2, default=str, sort_keys=True |
| scripts/analyze_core_v1_jump_risk_historical_regimes.py | 231 | json.dumps | payload | indent=2, sort_keys=True |
| scripts/analyze_core_v1_jump_risk_recovery_subtypes.py | 263 | json.dumps | payload | indent=2, sort_keys=True |
| scripts/analyze_overnight_intraday_anomaly.py | 170 | json.dumps | result | indent=2, default=str |
| scripts/analyze_overnight_intraday_anomaly.py | 211 | json.dumps | all_results | indent=2, default=str |
| scripts/analyze_pead_forward_drift.py | 269 | json.dumps | results | indent=2, default=str |
| scripts/analyze_sp500_reconstitution_effect.py | 209 | json.dumps | results | indent=2, default=str |
| scripts/analyze_sp500_reconstitution_effect.py | 211 | json.dumps | sorted(missing_tickers) | indent=2 |
| scripts/archive_reset_core_v1_paper_runtime.py | 64 | hashlib.sha256 |  |  |
| scripts/archive_reset_core_v1_paper_runtime.py | 75 | hashlib.sha256 |  |  |
| scripts/archive_reset_core_v1_paper_runtime.py | 260 | json.dumps | manifest | indent=2, sort_keys=True, default=str |
| scripts/archive_reset_core_v1_paper_runtime.py | 266 | json.dumps | manifest | indent=2, sort_keys=True, default=str |
| scripts/audit_core_v1_prices.py | 492 | json.dumps | report | indent=2, sort_keys=True, default=str |
| scripts/audit_core_v1_prices.py | 516 | json.dumps | report | indent=2, sort_keys=True |
| scripts/audit_jump_daily_generalization.py | 45 | json.dumps | payload | indent=2, default=str |
| scripts/backtest_low_volatility_factor.py | 258 | json.dumps | summary | indent=2, default=str |
| scripts/backtest_pairs_distance_method.py | 464 | json.dumps | summary | indent=2, default=str |
| scripts/check_dealer_gamma_sign_convention.py | 92 | json.dumps | report | indent=2, sort_keys=True |
| scripts/check_dealer_gamma_sign_convention.py | 93 | json.dumps | report | indent=2, sort_keys=True |
| scripts/core_v1_dashboard.py | 506 | json.dumps | value | default=str, sort_keys=True |
| scripts/diagnose_jump_risk_train_test_boundary_leakage.py | 158 | json.dumps | summary | indent=2, sort_keys=True |
| scripts/download_equity_data.py | 212 | json.dumps | payload | indent=2, default=str |
| scripts/estimate_pead_dollar_materiality.py | 266 | json.dumps | table | indent=2, default=str |
| scripts/export_core_v1_jump_risk_evidence.py | 64 | hashlib.sha256 |  |  |
| scripts/export_core_v1_jump_risk_evidence.py | 73 | json.dumps | payload | indent=2, sort_keys=True, default=str |
| scripts/export_core_v1_paper_data.py | 81 | json.dumps | value | default=str, sort_keys=True |
| scripts/export_core_v1_paper_data.py | 255 | json.dumps | manifest | indent=2, sort_keys=True, default=str |
| scripts/fetch_cot_legacy_futures_history.py | 142 | hashlib.sha256 | out_path.read_bytes() |  |
| scripts/fetch_cot_legacy_futures_history.py | 155 | json.dumps | manifest | indent=2, sort_keys=True |
| scripts/fetch_deribit_funding_history.py | 161 | json.dumps | manifest | indent=2, sort_keys=True |
| scripts/fetch_deribit_funding_history.py | 193 | hashlib.sha256 | content |  |
| scripts/inventory_campaign50_equity_sources.py | 25 | hashlib.sha256 |  |  |
| scripts/inventory_campaign50_equity_sources.py | 151 | json.dumps | inventory | indent=2, sort_keys=True, allow_nan=False |
| scripts/inventory_campaign50_equity_sources.py | 155 | json.dumps | {'file_count': inventory['file_count'], 'total_bytes': inventory['total_bytes'], 'output': output.as_posix(), 'outcomes_generated': False, 'predictors_generated': False} | sort_keys=True |
| scripts/preflight_campaign50_equity_breadth.py | 88 | json.dumps | {'candidate_count': result['candidate_count'], 'confirmation_enabled': False, 'outcomes_generated': False, 'output': output.as_posix(), 'predictors_generated': False, 'status': result['status']} | sort_keys=True |
| scripts/preflight_campaign50_execution_feasibility.py | 112 | json.dumps | result | sort_keys=True, indent=2, allow_nan=False |
| scripts/preflight_campaign50_execution_feasibility.py | 117 | json.dumps | {'status': result['status'], 'records': result['records'], 'structurally_impossible_gates': result['structurally_impossible_gates'], 'predictors_generated': False, 'outcomes_generated': False, 'prices_loaded': False, 'holdout_loaded': False, 'output': output.as_posix()} | sort_keys=True |
| scripts/preflight_campaign51_implementation.py | 96 | json.dumps | result | sort_keys=True, indent=2 |
| scripts/preflight_campaign51_implementation.py | 109 | json.dumps | execute(Path(args.source), Path(args.output)) | sort_keys=True |
| scripts/preflight_campaign51_source_variable_feasibility.py | 45 | hashlib.sha256 |  |  |
| scripts/preflight_campaign51_source_variable_feasibility.py | 224 | json.dumps | result | sort_keys=True, indent=2, allow_nan=False |
| scripts/preflight_campaign51_source_variable_feasibility.py | 228 | json.dumps | result | sort_keys=True |
| scripts/preflight_campaign52_sources_calendar.py | 56 | hashlib.sha256 | payload |  |
| scripts/preflight_campaign52_sources_calendar.py | 236 | json.dumps | failures |  |
| scripts/preflight_campaign52_sources_calendar.py | 244 | json.dumps | failures | sort_keys=True |
| scripts/preflight_campaign52_sources_calendar.py | 253 | json.dumps | coverage_failures | sort_keys=True |
| scripts/preflight_campaign52_sources_calendar.py | 296 | json.dumps | payload | sort_keys=True, indent=2 |
| scripts/preflight_campaign52_sources_calendar.py | 315 | json.dumps | execute(paths, Path(args.output)) | sort_keys=True |
| scripts/preflight_campaign57_long_history_confirmation.py | 190 | json.dumps | report | indent=2, sort_keys=True |
| scripts/preflight_campaign57_long_history_confirmation.py | 192 | json.dumps | report | indent=2, sort_keys=True |
| scripts/preflight_campaign57_long_history_confirmation.py | 246 | json.dumps | report | indent=2, sort_keys=True |
| scripts/preflight_campaign57_long_history_confirmation.py | 248 | json.dumps | report | indent=2, sort_keys=True |
| scripts/preflight_campaign57_vti_bnd_partitions.py | 302 | json.dumps | report | indent=2, sort_keys=True |
| scripts/preflight_campaign57_vti_bnd_partitions.py | 303 | json.dumps | report | indent=2, sort_keys=True |
| scripts/preflight_campaign57_vti_bnd_partitions.py | 351 | json.dumps | report | indent=2, sort_keys=True |
| scripts/preflight_campaign57_vti_bnd_partitions.py | 352 | json.dumps | report | indent=2, sort_keys=True |
| scripts/prepare_ml_lab_experiment_009_sources.py | 22 | hashlib.sha256 |  |  |
| scripts/prepare_ml_lab_experiment_011_sources.py | 31 | hashlib.sha256 |  |  |
| scripts/prepare_ml_lab_experiment_011_sources.py | 127 | json.dumps | payload | indent=2, sort_keys=True |
| scripts/prepare_ml_lab_experiment_011_sources.py | 128 | json.dumps | payload | indent=2, sort_keys=True |
| scripts/probe_cde_basis_snapshot.py | 144 | json.dumps | p | indent=2, sort_keys=True |
| scripts/probe_cde_basis_snapshot.py | 182 | json.dumps | perp_detail | indent=2, sort_keys=True |
| scripts/probe_cde_basis_snapshot.py | 185 | json.dumps | dated_detail | indent=2, sort_keys=True |
| scripts/probe_cde_basis_snapshot.py | 217 | json.dumps | {'probe': 'cde_basis_snapshot_v1', 'created_at_utc': datetime.now(timezone.utc).isoformat(), 'read_only': True, 'caveat': 'basis_best_effort uses a reasoned field-name priority order, not a confirmed schema -- verify against the printed full payload dumps before trusting it.', 'results': results} | indent=2, sort_keys=True |
| scripts/probe_cde_funding_coverage.py | 117 | json.dumps | {'probe': 'cde_funding_coverage_v1', 'created_at_utc': datetime.now(timezone.utc).isoformat(), 'read_only': True, 'liquid_perpetual_style_count': len(rows), 'funding_rate_covered_count': covered, 'products': rows} | indent=2, sort_keys=True |
| scripts/probe_cde_funding_history_endpoint.py | 166 | json.dumps | findings | indent=2, sort_keys=True, default=str |
| scripts/probe_cde_funding_rate_endpoint.py | 104 | json.dumps | payload[0] |  |
| scripts/probe_cde_funding_rate_endpoint.py | 116 | json.dumps | payload[0] |  |
| scripts/probe_cde_funding_rate_endpoint.py | 121 | json.dumps | findings | indent=2, sort_keys=True, default=str |
| scripts/probe_cde_funding_rate_endpoint_authenticated.py | 153 | json.dumps | payload[0] |  |
| scripts/probe_cde_funding_rate_endpoint_authenticated.py | 163 | json.dumps | findings | indent=2, sort_keys=True, default=str |
| scripts/probe_cde_history_depth.py | 121 | json.dumps | findings | indent=2, sort_keys=True, default=str |
| scripts/probe_cde_matched_pairs.py | 139 | json.dumps | {'probe': 'cde_matched_pairs_v1', 'created_at_utc': datetime.now(timezone.utc).isoformat(), 'read_only': True, 'liquid_perp_count': len(liquid_perp), 'matched_count': matched, 'rows': rows} | indent=2, sort_keys=True |
| scripts/probe_cde_product_detail.py | 94 | json.dumps | findings | indent=2, sort_keys=True |
| scripts/probe_coinbase_derivatives_universe.py | 154 | json.dumps | findings | indent=2, sort_keys=True |
| scripts/probe_coinbase_spot_momentum_universe.py | 203 | json.dumps | payload | indent=2, sort_keys=True |
| scripts/probe_cot_cross_sectional_universe.py | 260 | json.dumps | payload | indent=2, sort_keys=True, default=str |
| scripts/probe_deribit_open_interest_history.py | 80 | json.dumps | payload |  |
| scripts/probe_deribit_open_interest_history.py | 85 | json.dumps | findings | indent=2, sort_keys=True, default=str |
| scripts/probe_deribit_universe_coverage.py | 110 | json.dumps | findings | indent=2, sort_keys=True, default=str |
| scripts/probe_free_options_history.py | 61 | hashlib.sha256 |  |  |
| scripts/probe_free_options_history.py | 137 | json.dumps | report | indent=2, sort_keys=True |
| scripts/probe_free_options_history.py | 138 | json.dumps | report | indent=2, sort_keys=True |
| scripts/probe_free_options_history.py | 148 | json.dumps | manifest | indent=2, sort_keys=True |
| scripts/probe_free_options_history.py | 158 | json.dumps | report | indent=2, sort_keys=True |
| scripts/probe_free_options_history.py | 159 | json.dumps | report | indent=2, sort_keys=True |
| scripts/probe_free_options_history.py | 172 | json.dumps | report | indent=2, sort_keys=True |
| scripts/probe_free_options_history.py | 173 | json.dumps | report | indent=2, sort_keys=True |
| scripts/probe_free_options_history.py | 184 | json.dumps | report | indent=2, sort_keys=True |
| scripts/probe_free_options_history.py | 185 | json.dumps | report | indent=2, sort_keys=True |
| scripts/probe_funding_data_sources.py | 39 | json.dumps | payload |  |
| scripts/probe_funding_data_sources.py | 295 | json.dumps | findings | indent=2, sort_keys=True |
| scripts/prove_campaign58_residualization_leakage_canary.py | 150 | json.dumps | report | indent=2, sort_keys=True |
| scripts/reconcile_campaign50_equity_sessions.py | 57 | hashlib.sha256 |  |  |
| scripts/reconcile_campaign50_equity_sessions.py | 229 | json.dumps | result | indent=2, sort_keys=True, allow_nan=False |
| scripts/reconcile_campaign50_equity_sessions.py | 234 | json.dumps | {'all_source_common_session_count': result['all_source_common_session_count'], 'outcomes_generated': False, 'output': output.as_posix(), 'predictors_generated': False, 'target_calendar_session_count': result['target_calendar_session_count']} | sort_keys=True |
| scripts/reconcile_free_options_oi_with_occ.py | 52 | hashlib.sha256 | payload |  |
| scripts/reconcile_free_options_oi_with_occ.py | 85 | json.dumps | report | indent=2, sort_keys=True |
| scripts/reconcile_free_options_oi_with_occ.py | 124 | json.dumps | report | indent=2, sort_keys=True |
| scripts/reconcile_free_options_oi_with_occ.py | 125 | json.dumps | report | indent=2, sort_keys=True |
| scripts/redteam_month_end_rebalance_placebos.py | 154 | json.dumps | report | indent=2, sort_keys=True |
| scripts/redteam_month_end_rebalance_placebos.py | 155 | json.dumps | report | indent=2, sort_keys=True |
| scripts/register_jump_daily_champions.py | 157 | json.dumps | record.canonical_payload() | indent=2, default=str |
| scripts/replay_core_v1_export.py | 852 | json.dumps | report | indent=2, sort_keys=True, default=str |
| scripts/replay_core_v1_export.py | 981 | json.dumps | report | indent=2, sort_keys=True, default=str |
| scripts/review_campaign50_development_validation.py | 23 | hashlib.sha256 |  |  |
| scripts/review_campaign50_development_validation.py | 124 | json.dumps | review | sort_keys=True, indent=2, allow_nan=False |
| scripts/run_alpha_surface_discovery.py | 90 | hashlib.sha256 |  |  |
| scripts/run_alpha_surface_discovery.py | 125 | json.dumps | value | sort_keys=True, separators=(',', ':'), ensure_ascii=True |
| scripts/run_alpha_surface_discovery.py | 129 | json.dumps | value | indent=2, sort_keys=True, ensure_ascii=True |
| scripts/run_alpha_surface_discovery.py | 225 | hashlib.sha256 | payload |  |
| scripts/run_alpha_surface_discovery.py | 278 | hashlib.sha256 |  |  |
| scripts/run_alpha_surface_discovery.py | 309 | json.dumps | {'preflight': 'passed', 'inventory_surfaces': len(inventory), 'cited_sources': len(source_hashes), 'new_predictive_returns_generated': False} | sort_keys=True |
| scripts/run_alpha_surface_discovery.py | 328 | json.dumps | {'generation': 'passed', 'output_dir': str(output_dir), 'replay_digest': replay_digest(outputs), 'new_predictive_returns_generated': False} | sort_keys=True |
| scripts/run_alpha_surface_discovery.py | 340 | json.dumps | {'replay': 'passed', 'replay_digest': digest} | sort_keys=True |
| scripts/run_campaign50_development_validation.py | 119 | hashlib.sha256 | payload |  |
| scripts/run_campaign50_development_validation.py | 645 | json.dumps | result | sort_keys=True |
| scripts/run_campaign50_development_validation_amended.py | 86 | json.dumps | execute(Path(args.data_root), Path(args.output_dir)) | sort_keys=True |
| scripts/run_campaign51_development_validation.py | 443 | json.dumps | result | sort_keys=True |
| scripts/run_campaign52_development.py | 660 | json.dumps | summary | sort_keys=True |
| scripts/run_campaign52_governed_equivalence.py | 71 | hashlib.sha256 |  |  |
| scripts/run_campaign52_governed_equivalence.py | 81 | json.dumps | payload | sort_keys=True, separators=(',', ':') |
| scripts/run_campaign52_governed_equivalence.py | 408 | json.dumps | manifest | sort_keys=True |
| scripts/run_campaign53_discovery.py | 217 | json.dumps | report | indent=2, sort_keys=True |
| scripts/run_campaign53_power_analysis.py | 379 | json.dumps | report | indent=2, sort_keys=True |
| scripts/run_campaign57_long_history_confirmation.py | 66 | hashlib.sha256 |  |  |
| scripts/run_campaign57_long_history_confirmation.py | 248 | json.dumps | report | indent=2, sort_keys=True |
| scripts/run_campaign57_long_history_confirmation.py | 249 | json.dumps | report | indent=2, sort_keys=True |
| scripts/run_campaign57_long_history_confirmation.py | 328 | json.dumps | report | indent=2, sort_keys=True, default=str |
| scripts/run_campaign57_long_history_confirmation.py | 329 | json.dumps | report | indent=2, sort_keys=True, default=str |
| scripts/run_campaign58_grid_power_analysis.py | 345 | json.dumps | report | indent=2, sort_keys=True |
| scripts/run_campaign58_phase1_power_analysis.py | 439 | json.dumps | report | indent=2, sort_keys=True |
| scripts/run_campaign_54_sizing_sweep.py | 120 | json.dumps | rows | indent=2 |
| scripts/run_core_v1_event_robustness.py | 45 | hashlib.sha256 |  |  |
| scripts/run_core_v1_event_robustness.py | 63 | json.dumps | value | indent=2, sort_keys=True, allow_nan=False, ensure_ascii=False, separators=(',', ': ') |
| scripts/run_core_v1_experiment_grid.py | 103 | json.dumps | manifest | indent=2 |
| scripts/run_core_v1_historical_alpha_discovery.py | 107 | hashlib.sha256 |  |  |
| scripts/run_core_v1_historical_alpha_discovery.py | 753 | json.dumps | payload | sort_keys=True, indent=2, allow_nan=False, ensure_ascii=False |
| scripts/run_core_v1_historical_alpha_discovery.py | 856 | hashlib.sha256 |  |  |
| scripts/run_core_v1_historical_alpha_discovery.py | 868 | hashlib.sha256 | content |  |
| scripts/run_core_v1_historical_event_families.py | 61 | hashlib.sha256 |  |  |
| scripts/run_core_v1_historical_event_families.py | 85 | json.dumps | value | indent=2, sort_keys=True, allow_nan=False, ensure_ascii=False, separators=(',', ': ') |
| scripts/run_core_v1_historical_event_families.py | 166 | json.dumps | summary | sort_keys=True, separators=(',', ':'), allow_nan=False |
| scripts/run_core_v1_historical_event_families.py | 167 | hashlib.sha256 | canonical.encode('utf-8') |  |
| scripts/run_core_v1_historical_regime_taxonomy.py | 111 | json.dumps | _strict_json_records(classified) | indent=2, sort_keys=True, allow_nan=False |
| scripts/run_core_v1_historical_regime_taxonomy.py | 117 | json.dumps | summary | indent=2, sort_keys=True, allow_nan=False |
| scripts/run_core_v1_historical_regime_taxonomy.py | 132 | json.dumps | values | separators=(',', ':') |
| scripts/run_core_v1_historical_regime_taxonomy_report.py | 113 | json.dumps | report | indent=2, sort_keys=True, allow_nan=False |
| scripts/run_core_v1_jump_risk_diagnosis.py | 43 | json.dumps | payload | indent=2, sort_keys=True, default=str |
| scripts/run_core_v1_jump_risk_diagnosis_v2.py | 50 | json.dumps | payload | indent=2, sort_keys=True, default=str |
| scripts/run_core_v1_jump_risk_drift.py | 50 | json.dumps | payload | indent=2, sort_keys=True, default=str |
| scripts/run_core_v1_jump_risk_drift.py | 110 | json.dumps | report.score_components | sort_keys=True, separators=(',', ':') |
| scripts/run_core_v1_jump_risk_paper.py | 163 | json.dumps | record | default=str, sort_keys=True |
| scripts/run_core_v1_jump_risk_parity.py | 135 | json.dumps | result | sort_keys=True |
| scripts/run_core_v1_jump_risk_parity.py | 142 | json.dumps | result | indent=2, sort_keys=True |
| scripts/run_core_v1_jump_risk_replay.py | 53 | hashlib.sha256 | payload |  |
| scripts/run_core_v1_jump_risk_replay.py | 57 | json.dumps | payload | sort_keys=True, separators=(',', ':'), default=str |
| scripts/run_core_v1_jump_risk_replay.py | 213 | json.dumps | report | indent=2, sort_keys=True |
| scripts/run_core_v1_jump_risk_replay.py | 214 | json.dumps | {'status': 'PASS', 'out': str(out), 'replay_digest': report['replay_digest'], 'summary': report['summary']} | indent=2, sort_keys=True |
| scripts/run_core_v1_live_benchmarks.py | 167 | hashlib.sha256 | payload |  |
| scripts/run_core_v1_live_comparison.py | 225 | hashlib.sha256 | payload |  |
| scripts/run_core_v1_parameter_sensitivity.py | 315 | json.dumps | summary | indent=2, sort_keys=True |
| scripts/run_core_v1_policy_selector.py | 269 | json.dumps | summary | indent=2 |
| scripts/run_core_v1_regime_attribution.py | 553 | json.dumps | metadata | indent=2 |
| scripts/run_core_v1_sleeve_attribution_report.py | 376 | json.dumps | summary | indent=2, default=str |
| scripts/run_core_v1_sleeve_contribution_audit.py | 385 | json.dumps | summary | indent=2 |
| scripts/run_core_v1_sleeve_contribution_audit_parallel.py | 243 | json.dumps | summary | indent=2 |
| scripts/run_cot_cross_sectional_discovery.py | 336 | json.dumps | payload | indent=2, sort_keys=True, default=str |
| scripts/run_full_historical_regime_state_sequence.py | 45 | hashlib.sha256 | path.read_bytes() |  |
| scripts/run_full_historical_regime_state_sequence.py | 99 | json.dumps | {'status': 'PASS', 'source': evidence} | sort_keys=True |
| scripts/run_full_historical_regime_state_sequence.py | 146 | hashlib.sha256 | json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode() |  |
| scripts/run_full_historical_regime_state_sequence.py | 146 | json.dumps | manifest | sort_keys=True, separators=(',', ':') |
| scripts/run_full_historical_regime_state_sequence.py | 154 | json.dumps | {'status': 'PASS', 'feasibility': summary['status'], 'output': str(OUTPUT)} | sort_keys=True |
| scripts/run_fund_portfolio.py | 485 | json.dumps | summary | indent=2, default=str |
| scripts/run_fund_portfolio.py | 492 | json.dumps | port_summary | indent=2, default=str |
| scripts/run_fund_walk_forward.py | 276 | json.dumps | payload | indent=2, default=str |
| scripts/run_fund_walk_forward.py | 278 | json.dumps | agg | indent=2, default=str |
| scripts/run_historical_regime_structure_discovery.py | 52 | json.dumps | payload | sort_keys=True, separators=(',', ':'), allow_nan=False |
| scripts/run_historical_regime_transition_discovery.py | 59 | json.dumps | payload | sort_keys=True, allow_nan=False |
| scripts/run_historical_regime_transition_discovery.py | 68 | json.dumps | result | sort_keys=True, allow_nan=False |
| scripts/run_jump_ablation_research.py | 362 | json.dumps | report | indent=2, default=str |
| scripts/run_jump_ablation_research.py | 406 | json.dumps | manifest | indent=2, default=str |
| scripts/run_jump_candidate_robustness.py | 96 | json.dumps | payload | indent=2, default=str |
| scripts/run_jump_cross_asset_validation.py | 126 | json.dumps | payload | indent=2, default=str |
| scripts/run_jump_daily_asset_generalization.py | 147 | json.dumps | payload | indent=2, default=str |
| scripts/run_jump_energy_research.py | 134 | json.dumps | report | indent=2, default=str |
| scripts/run_jump_horizon_research.py | 210 | json.dumps | manifest | indent=2, default=str |
| scripts/run_jump_risk_lag_realistic_sensitivity.py | 344 | json.dumps | report | indent=2, sort_keys=True |
| scripts/run_jump_risk_lag_sensitivity.py | 206 | json.dumps | report | indent=2, sort_keys=True |
| scripts/run_jump_risk_portfolio_candidate_audit.py | 47 | json.dumps | payload | indent=2, default=str |
| scripts/run_jump_risk_portfolio_integration.py | 93 | json.dumps | payload | indent=2, default=str |
| scripts/run_jump_risk_portfolio_integration.py | 98 | hashlib.sha256 |  |  |
| scripts/run_jump_risk_runtime_cadence_probe.py | 292 | json.dumps | payload | indent=2, default=str |
| scripts/run_jump_risk_runtime_cadence_probe.py | 298 | json.dumps | payload | default=str, separators=(',', ':') |
| scripts/run_jump_risk_timing_audit.py | 51 | json.dumps | payload | indent=2, default=str |
| scripts/run_jump_targeted_horizon_research.py | 137 | json.dumps | payload | indent=2, default=str |
| scripts/run_ml_lab_experiment_001.py | 450 | json.dumps | report | indent=2, sort_keys=True |
| scripts/run_ml_lab_experiment_001.py | 452 | json.dumps | report | indent=2, sort_keys=True |
| scripts/run_ml_lab_experiment_002.py | 283 | json.dumps | report | indent=2, sort_keys=True |
| scripts/run_ml_lab_experiment_002.py | 284 | json.dumps | report | indent=2, sort_keys=True |
| scripts/run_ml_lab_experiment_003.py | 454 | json.dumps | report | indent=2, sort_keys=True |
| scripts/run_ml_lab_experiment_003.py | 455 | json.dumps | report | indent=2, sort_keys=True |
| scripts/run_ml_lab_experiment_004.py | 274 | json.dumps | report | indent=2, sort_keys=True |
| scripts/run_ml_lab_experiment_004.py | 275 | json.dumps | report | indent=2, sort_keys=True |
| scripts/run_multi_strategy_fund.py | 662 | json.dumps | summary | indent=2 |
| scripts/run_multi_strategy_walkforward.py | 549 | json.dumps | summary | indent=2 |
| scripts/run_multiasset_portfolio.py | 575 | json.dump | summary, f | indent=2 |
| scripts/run_paper.py | 148 | json.dump | cycle_log[-50:], f | indent=2, default=str |
| scripts/run_paper_runtime_cadence_audit.py | 316 | json.dumps | report | indent=2, sort_keys=True |
| scripts/run_simple_btc_price_state_predictive_baselines.py | 42 | json.dumps | payload | sort_keys=True, separators=(',', ':'), allow_nan=False |
| scripts/run_trend_persistence_ablation.py | 93 | json.dumps | payload | indent=2, default=str |
| scripts/run_trend_persistence_horizon_refinement.py | 115 | json.dumps | payload | indent=2, default=str |
| scripts/run_trend_persistence_portfolio_integration.py | 117 | json.dumps | payload | indent=2, default=str |
| scripts/run_trend_persistence_research.py | 321 | json.dumps | payload | indent=2, default=str |
| scripts/run_trend_persistence_robustness.py | 103 | json.dumps | payload | indent=2, default=str |
| scripts/screen_dealer_gamma_pressure.py | 302 | json.dumps | report | indent=2, sort_keys=True |
| scripts/screen_dealer_gamma_pressure.py | 308 | json.dumps | report | indent=2, sort_keys=True |
| scripts/screen_month_end_rebalance_pressure.py | 291 | json.dumps | report | indent=2, sort_keys=True |
| scripts/screen_month_end_rebalance_pressure.py | 293 | json.dumps | report | indent=2, sort_keys=True |
| scripts/screen_month_end_rebalance_pressure.py | 376 | json.dumps | report | indent=2, sort_keys=True, default=str |
| scripts/screen_month_end_rebalance_pressure.py | 378 | json.dumps | report | indent=2, sort_keys=True, default=str |
| scripts/summarize_core_v1_jump_risk_diagnosis_v2.py | 154 | json.dumps | payload | indent=2, sort_keys=True, default=str |
| scripts/test_pead_beta_confound.py | 190 | json.dumps | results | indent=2, default=str |
| scripts/train_calibrator.py | 373 | json.dump | regime_cal.to_dict(), f | indent=2 |
| scripts/train_calibrator.py | 384 | json.dump | all_reports, f | indent=2 |
| scripts/update_campaign49_coinbase_source.py | 211 | hashlib.sha256 | prior.raw |  |
| scripts/update_campaign49_coinbase_source.py | 216 | hashlib.sha256 | candidate.raw |  |
| scripts/update_campaign49_coinbase_source.py | 234 | json.dumps | manifest | indent=2, sort_keys=True, allow_nan=False |
| scripts/update_campaign49_coinbase_source.py | 260 | hashlib.sha256 | prior.raw |  |
| scripts/update_campaign49_coinbase_source.py | 325 | json.dumps | manifest | separators=(',', ':'), sort_keys=True |
| scripts/validate_pead_oos_bootstrap.py | 188 | json.dumps | combined | indent=2, default=str |
| scripts/verify_refactor_ml_parity.py | 113 | hashlib.sha256 | b''.join((before[k] for k in sorted(before))) |  |
| scripts/verify_refactor_ml_parity.py | 113 | json.dumps | {'status': 'PASS', 'baseline': sha, 'experiments': list(range(5, 12)), 'artifacts_byte_identical': len(before), 'digest': hashlib.sha256(b''.join((before[k] for k in sorted(before)))).hexdigest(), 'scope': 'Synthetic migration parity only; no historical market inputs'} | indent=2 |
| scripts/verify_refactor_runtime_parity.py | 56 | json.dumps | state | sort_keys=True |
| scripts/verify_refactor_runtime_parity.py | 169 | json.dumps | {'status': 'PASS', 'accounting_cases': accounting_cases, 'successful_cycles': 3, 'induced_failure_cycles': 1, 'error_logs_nonempty_and_byte_identical': True, 'cycle_state_and_logs_byte_identical': True, 'chart_specifications_identical': True, 'baseline': BASELINE_SHA} | indent=2 |
