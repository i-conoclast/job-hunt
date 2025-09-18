"""Job scoring and prioritization module."""

from typing import Dict, List, Any
from dataclasses import dataclass
import yaml
from pathlib import Path

from .job_normalizer import NormalizedJob


@dataclass
class ScoringConfig:
    """Scoring configuration."""
    weights: Dict[str, float]
    penalties: Dict[str, float]
    thresholds: Dict[str, int]
    user_profile: Dict[str, Any]


class JobScorer:
    """Scores and prioritizes jobs based on user profile and preferences."""

    def __init__(self, config_path: str = None):
        """Initialize scorer with configuration."""
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: str = None) -> ScoringConfig:
        """Load scoring configuration."""
        if config_path:
            config_file = Path(config_path)
        else:
            config_file = Path(__file__).parent.parent.parent / "config" / "scoring.yml"

        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
        else:
            config_data = self._get_default_config()

        return ScoringConfig(
            weights=config_data.get("weights", {}),
            penalties=config_data.get("penalties", {}),
            thresholds=config_data.get("thresholds", {}),
            user_profile=config_data.get("user_profile", {})
        )

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default scoring configuration."""
        return {
            "weights": {
                "must_match": 60,
                "seniority": 10,
                "domain": 10,
                "work_type": 8,
                "recency": 5,
                "language": 7
            },
            "penalties": {
                "red_flag": -10
            },
            "thresholds": {
                "shortlist": 75,
                "consider": 60
            },
            "user_profile": {
                "required_skills": ["python", "llm", "rag", "machine learning"],
                "preferred_skills": ["pytorch", "fastapi", "aws", "docker"],
                "seniority_level": "mid",
                "preferred_domains": ["fintech", "healthcare", "education"],
                "work_type_preference": "hybrid",
                "location_preference": ["Seoul", "Pangyo"],
                "language_skills": ["KR", "EN"]
            }
        }

    def score_job(self, job: NormalizedJob) -> float:
        """Calculate priority score for a job."""
        score = 0.0

        # Core skill matching (60 points)
        score += self._score_skill_match(job) * self.config.weights.get("must_match", 60)

        # Seniority fit (10 points)
        score += self._score_seniority_fit(job) * self.config.weights.get("seniority", 10)

        # Domain fit (10 points)
        score += self._score_domain_fit(job) * self.config.weights.get("domain", 10)

        # Work type preference (8 points)
        score += self._score_work_type_fit(job) * self.config.weights.get("work_type", 8)

        # Recency bonus (5 points)
        score += self._score_recency(job) * self.config.weights.get("recency", 5)

        # Language requirements (7 points)
        score += self._score_language_fit(job) * self.config.weights.get("language", 7)

        # Red flag penalties
        score += self._score_red_flags(job) * self.config.penalties.get("red_flag", -10)

        return max(0, min(100, score))

    def _score_skill_match(self, job: NormalizedJob) -> float:
        """Score skill matching (0.0 - 1.0)."""
        required_skills = self.config.user_profile.get("required_skills", [])
        preferred_skills = self.config.user_profile.get("preferred_skills", [])

        if not required_skills:
            return 0.5

        # Check must-have skills
        must_match = sum(1 for skill in required_skills if skill.lower() in [t.lower() for t in job.tech_stack])
        must_score = must_match / len(required_skills)

        # Check nice-to-have skills
        nice_match = sum(1 for skill in preferred_skills if skill.lower() in [t.lower() for t in job.tech_stack])
        nice_score = nice_match / max(len(preferred_skills), 1) if preferred_skills else 0

        # Weight: 80% must-have, 20% nice-to-have
        return 0.8 * must_score + 0.2 * nice_score

    def _score_seniority_fit(self, job: NormalizedJob) -> float:
        """Score seniority level fit (0.0 - 1.0)."""
        user_level = self.config.user_profile.get("seniority_level", "mid")
        job_level = job.seniority

        level_hierarchy = {"junior": 1, "mid": 2, "senior": 3, "lead": 4}
        user_rank = level_hierarchy.get(user_level, 2)
        job_rank = level_hierarchy.get(job_level, 2)

        # Perfect match
        if user_rank == job_rank:
            return 1.0

        # Close match (1 level difference)
        if abs(user_rank - job_rank) == 1:
            return 0.7

        # Distant match
        return 0.3

    def _score_domain_fit(self, job: NormalizedJob) -> float:
        """Score domain/industry fit (0.0 - 1.0)."""
        preferred_domains = self.config.user_profile.get("preferred_domains", [])

        if not preferred_domains:
            return 0.5

        domain_match = any(domain in job.domain for domain in preferred_domains)
        return 1.0 if domain_match else 0.3

    def _score_work_type_fit(self, job: NormalizedJob) -> float:
        """Score work type preference fit (0.0 - 1.0)."""
        preferred_type = self.config.user_profile.get("work_type_preference", "hybrid")

        if job.work_type == preferred_type:
            return 1.0
        elif job.work_type == "hybrid" or preferred_type == "hybrid":
            return 0.8
        else:
            return 0.4

    def _score_recency(self, job: NormalizedJob) -> float:
        """Score job posting recency (0.0 - 1.0)."""
        if job.recency_days <= 3:
            return 1.0
        elif job.recency_days <= 7:
            return 0.8
        elif job.recency_days <= 14:
            return 0.5
        elif job.recency_days <= 30:
            return 0.2
        else:
            return 0.0

    def _score_language_fit(self, job: NormalizedJob) -> float:
        """Score language requirements fit (0.0 - 1.0)."""
        user_languages = set(self.config.user_profile.get("language_skills", ["KR"]))
        job_languages = set(job.languages)

        if not job_languages:
            return 0.8  # Assume Korean if not specified

        # Can handle all required languages
        if job_languages.issubset(user_languages):
            return 1.0

        # Can handle some languages
        overlap = len(job_languages.intersection(user_languages))
        return overlap / len(job_languages) if job_languages else 0.8

    def _score_red_flags(self, job: NormalizedJob) -> float:
        """Score red flags (negative penalties)."""
        if not job.red_flags:
            return 0.0

        # Each red flag reduces score
        penalty_per_flag = 1.0 / max(len(job.red_flags), 1)
        return -penalty_per_flag * len(job.red_flags)

    def classify_priority(self, score: float) -> str:
        """Classify job priority based on score."""
        if score >= self.config.thresholds.get("shortlist", 75):
            return "shortlist"
        elif score >= self.config.thresholds.get("consider", 60):
            return "consider"
        else:
            return "backlog"

    def get_fit_label(self, score: float) -> str:
        """Get fit label (A/B/C) based on score."""
        if score >= 80:
            return "A"
        elif score >= 60:
            return "B"
        else:
            return "C"