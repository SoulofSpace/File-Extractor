"""
evaluation package — Offline IR evaluation harness and benchmark metrics for FILE XTRACTOR V2.
"""

from .benchmark import EvaluationHarness, EvaluationReport, GoldQuery

__all__ = ["EvaluationHarness", "EvaluationReport", "GoldQuery"]
