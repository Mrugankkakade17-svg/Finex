"""
Schemas for Sprint 7: Operations, Feature Flags, Health Observability, and Release Candidate Metadata.
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class FeatureFlagStatus(BaseModel):
    flag_key: str
    description: str
    enabled: bool
    owner: str
    safe_fallback: str


class DependencyHealth(BaseModel):
    name: str
    status: Literal["HEALTHY", "DEGRADED", "UNAVAILABLE"]
    latency_ms: float
    message: Optional[str] = None


class SystemObservabilityReport(BaseModel):
    environment: str
    app_version: str
    uptime_seconds: float
    healthy: bool
    active_feature_flags: List[FeatureFlagStatus]
    dependencies: List[DependencyHealth]
    error_rate_p95_ms: float
    rollback_target_sha: str


class ReleasePreflightCheck(BaseModel):
    release_tag: str
    commit_sha: str
    migrations_single_headed: bool
    security_scan_clean: bool
    ai_safety_eval_passed: bool
    accessibility_pass_rate_pct: float
    anand_uat_approved: bool
    ready_for_promotion: bool

