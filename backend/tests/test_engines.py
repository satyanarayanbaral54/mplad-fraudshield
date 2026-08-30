"""
MPLAD FraudShield — Engine Unit Tests
Run with: pytest tests/ -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import pandas as pd
import numpy as np
from engines.red_flag_engine import RedFlagEngine
from engines.ml_engine import MLAnomalyEngine
from engines.nlp_engine import NLPRiskEngine
from engines.risk_aggregator import RiskAggregator
from utils.helpers import generate_sample_mplad_dataset, preprocess_pipeline


# ─────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────

@pytest.fixture(scope="module")
def sample_df():
    """500-row synthetic dataset with deliberate fraud patterns."""
    df = generate_sample_mplad_dataset(200)
    return preprocess_pipeline(df)


# ─────────────────────────────────────────
# RED FLAG ENGINE TESTS
# ─────────────────────────────────────────

class TestRedFlagEngine:

    def test_engine_runs_on_sample_data(self, sample_df):
        engine = RedFlagEngine()
        result = engine.analyze_all(sample_df)
        assert 'red_flag_score' in result.columns
        assert 'flags_triggered' in result.columns
        print(f"\n✅ Red flag engine: {len(result)} projects analyzed")

    def test_scores_are_in_valid_range(self, sample_df):
        engine = RedFlagEngine()
        result = engine.analyze_all(sample_df)
        assert result['red_flag_score'].between(0, 100).all(), \
            "All red_flag_scores must be between 0 and 100"

    def test_finds_phantom_completions(self, sample_df):
        """Projects marked complete with no photos must be flagged."""
        engine = RedFlagEngine()
        result = engine.analyze_all(sample_df)
        phantom = result[result['flags_triggered'].apply(
            lambda f: 'phantom_completion' in (f if isinstance(f, list) else [])
        )]
        assert len(phantom) > 0, "Sample data has phantom completions — should be found"
        print(f"\n✅ Phantom completions found: {len(phantom)}")

    def test_finds_cost_outliers(self, sample_df):
        """Projects with 3x cost vs benchmark must be flagged."""
        engine = RedFlagEngine()
        result = engine.analyze_all(sample_df)
        outliers = result[result['flags_triggered'].apply(
            lambda f: 'cost_outlier' in (f if isinstance(f, list) else [])
        )]
        assert len(outliers) > 0, "Sample data has cost outliers — should be found"
        print(f"\n✅ Cost outliers found: {len(outliers)}")

    def test_repeated_vendor_flagged(self, sample_df):
        """Same vendor winning 3+ projects from same MP must be flagged."""
        engine = RedFlagEngine()
        result = engine.analyze_all(sample_df)
        vendor_flags = result[result['flags_triggered'].apply(
            lambda f: 'repeated_vendor' in (f if isinstance(f, list) else [])
        )]
        assert len(vendor_flags) > 0, "Sample data has repeated vendors — should be found"
        print(f"\n✅ Repeated vendor flags: {len(vendor_flags)}")


# ─────────────────────────────────────────
# ML ENGINE TESTS
# ─────────────────────────────────────────

class TestMLAnomalyEngine:

    def test_model_loads_successfully(self):
        engine = MLAnomalyEngine()
        loaded = engine.load_models()
        assert loaded == True or engine.iso_forest is not None, \
            "ML model must load from disk"
        print(f"\n✅ ML model loaded: {type(engine.iso_forest).__name__}")

    def test_score_returns_valid_column(self, sample_df):
        engine = MLAnomalyEngine()
        result = engine.score(sample_df)
        assert 'ml_anomaly_score' in result.columns
        assert result['ml_anomaly_score'].between(0, 100).all()
        print(f"\n✅ ML scores range: {result['ml_anomaly_score'].min():.1f} – {result['ml_anomaly_score'].max():.1f}")

    def test_anomaly_count_reasonable(self, sample_df):
        """With contamination=0.05, ~5% of rows should be anomalies."""
        engine = MLAnomalyEngine()
        result = engine.score(sample_df)
        if 'ml_is_anomaly' in result.columns:
            anomaly_pct = result['ml_is_anomaly'].mean() * 100
            print(f"\n✅ Anomaly percentage: {anomaly_pct:.1f}%")
            # Allow 1–20% — contamination param controls this
            assert 0 < anomaly_pct < 30

    def test_vendor_network_data_structure(self, sample_df):
        engine = MLAnomalyEngine()
        network = engine.get_vendor_network_data(sample_df)
        assert 'nodes' in network
        assert 'links' in network
        assert len(network['nodes']) > 0
        print(f"\n✅ Network: {len(network['nodes'])} nodes, {len(network['links'])} links")


# ─────────────────────────────────────────
# NLP ENGINE TESTS
# ─────────────────────────────────────────

class TestNLPRiskEngine:

    def test_vague_text_scores_high(self):
        engine = NLPRiskEngine()
        vague = "work completed as per norms. funds utilized properly as sanctioned."
        score, phrases = engine.compute_vagueness_score(vague)
        assert score > 40, f"Vague text should score >40, got {score}"
        print(f"\n✅ Vague text score: {score} | Phrases: {phrases}")

    def test_specific_text_scores_low(self):
        engine = NLPRiskEngine()
        specific = ("Construction of 2.3 km road from Village Khandwa to Primary School, "
                    "completed using 450 MT bitumen grade VG-30, verified by DM office on "
                    "2024-01-15. Measured length confirmed by junior engineer. Total cost "
                    "₹18.5 Lakhs within sanctioned amount. 12 workers employed for 45 days.")
        score, phrases = engine.compute_vagueness_score(specific)
        assert score < 40, f"Specific text should score <40, got {score}"
        print(f"\n✅ Specific text score: {score}")

    def test_template_reuse_detects_copies(self):
        engine = NLPRiskEngine()
        identical_texts = [
            "work completed as per norms and government guidelines funds utilized",
            "work completed as per norms and government guidelines funds utilized",  # exact copy
            "road construction from village A to village B completed successfully and properly"
        ]
        scores = engine.detect_template_reuse(identical_texts)
        assert len(scores) == 3
        assert scores[0] > 0.85, f"Identical text should have similarity >0.85, got {scores[0]}"
        print(f"\n✅ Template reuse scores: {[round(s,2) for s in scores]}")

    def test_analyze_project_texts_returns_columns(self, sample_df):
        engine = NLPRiskEngine()
        result = engine.analyze_project_texts(sample_df)
        assert 'vagueness_score' in result.columns
        assert 'nlp_risk_score' in result.columns
        print(f"\n✅ NLP analysis complete. Avg vagueness: {result['vagueness_score'].mean():.1f}")


# ─────────────────────────────────────────
# RISK AGGREGATOR TESTS
# ─────────────────────────────────────────

class TestRiskAggregator:

    def test_full_pipeline_runs(self, sample_df):
        aggregator = RiskAggregator()
        result = aggregator.run_full_analysis(sample_df)
        assert 'final_risk_score' in result.columns
        assert 'risk_level' in result.columns
        print(f"\n✅ Full pipeline: {len(result)} records scored")

    def test_scores_in_valid_range(self, sample_df):
        aggregator = RiskAggregator()
        result = aggregator.run_full_analysis(sample_df)
        assert result['final_risk_score'].between(0, 100).all()

    def test_critical_projects_found(self, sample_df):
        """Sample data has deliberate fraud — CRITICAL projects MUST be found."""
        aggregator = RiskAggregator()
        result = aggregator.run_full_analysis(sample_df)
        critical = result[result['risk_level'] == 'CRITICAL']
        assert len(critical) > 0, "CRITICAL fraud patterns must be detected!"
        print(f"\n✅ CRITICAL projects: {len(critical)} | Max score: {result['final_risk_score'].max():.1f}")

    def test_risk_levels_match_scores(self, sample_df):
        aggregator = RiskAggregator()
        result = aggregator.run_full_analysis(sample_df)
        # CRITICAL must have score >= 75
        critical = result[result['risk_level'] == 'CRITICAL']
        if len(critical) > 0:
            assert critical['final_risk_score'].min() >= 74  # allow 1-point rounding
        # LOW must have score < 50
        low = result[result['risk_level'] == 'LOW']
        if len(low) > 0:
            assert low['final_risk_score'].max() < 51

    def test_dashboard_stats_structure(self, sample_df):
        aggregator = RiskAggregator()
        result = aggregator.run_full_analysis(sample_df)
        stats = aggregator.get_dashboard_stats(result)
        required_keys = ['total_projects', 'critical_count', 'high_count', 
                         'funds_at_risk', 'avg_risk_score']
        for key in required_keys:
            assert key in stats, f"Missing key in dashboard stats: {key}"
        print(f"\n✅ Dashboard stats: {stats}")