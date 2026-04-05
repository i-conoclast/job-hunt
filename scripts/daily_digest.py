#!/usr/bin/env python3
"""Daily job digest pipeline.

collect(Wanted) → normalize → score → DB 저장 → 이메일 발송.
GitHub Actions 또는 수동 실행용.

사용법:
    uv run python scripts/daily_digest.py
    uv run python scripts/daily_digest.py --skip-email
    uv run python scripts/daily_digest.py --keywords "RAG,LLM,AI Engineer"
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.scrapers.multi_source_scraper import MultiSourceScraper
from src.core.job_normalizer import JobNormalizer, NormalizedJob
from src.core.job_scorer import JobScorer
from src.core.database import DatabaseManager, JobData
from src.utils.email_sender import EmailSender


def collect_jobs(keywords: list[str], limit: int = 50) -> list[dict]:
    """Wanted API에서 공고 수집."""
    print(f"Collecting jobs: keywords={keywords}, limit={limit}")
    scraper = MultiSourceScraper()
    jobs = scraper.scrape_source("wanted", keywords=keywords, limit=limit)
    print(f"  Collected {len(jobs)} jobs")
    return jobs


def normalize_jobs(raw_jobs: list[dict]) -> list[NormalizedJob]:
    """원시 데이터를 NormalizedJob으로 변환."""
    normalizer = JobNormalizer()
    normalized = []
    for raw in raw_jobs:
        try:
            normalized.append(normalizer.normalize(raw))
        except Exception as e:
            print(f"  Normalize error: {e}")
    print(f"  Normalized {len(normalized)}/{len(raw_jobs)} jobs")
    return normalized


def score_jobs(jobs: list[NormalizedJob]) -> list[NormalizedJob]:
    """점수화 및 정렬."""
    scorer = JobScorer()
    for job in jobs:
        score = scorer.score_job(job)
        job.priority_score = score
        job.fit_label = scorer.get_fit_label(score)
        job.status = scorer.classify_priority(score)
    jobs.sort(key=lambda j: j.priority_score, reverse=True)
    shortlist = sum(1 for j in jobs if j.status == "shortlist")
    consider = sum(1 for j in jobs if j.status == "consider")
    print(f"  Scored: {shortlist} shortlist, {consider} consider, "
          f"{len(jobs) - shortlist - consider} backlog")
    return jobs


def save_to_db(raw_jobs: list[dict]) -> dict:
    """SQLite DB에 저장 (중복 제거 포함)."""
    db = DatabaseManager()
    db.create_tables()

    job_data_list = []
    for raw in raw_jobs:
        job_data_list.append(JobData(
            source=raw.get("source", "wanted"),
            source_method="api",
            external_id=str(raw.get("id", "")),
            company_name=raw.get("company", ""),
            title=raw.get("title", ""),
            description=raw.get("description", ""),
            location=raw.get("location", ""),
            work_type=raw.get("work_type", ""),
            employment_type="full-time",
            url=raw.get("url", ""),
            tags=raw.get("tech_stack", []),
        ))

    stats = db.bulk_insert_jobs_optimized(job_data_list)
    print(f"  DB: {stats['new']} new, {stats['updated']} updated, "
          f"{stats['skipped']} skipped")
    return stats


def save_json(jobs: list[NormalizedJob], raw_jobs: list[dict]) -> Path:
    """결과를 JSON 파일로 저장."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = PROJECT_ROOT / "data" / "digests"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"digest_{ts}.json"

    data = {
        "timestamp": ts,
        "total": len(jobs),
        "shortlist": [j.__dict__ for j in jobs if j.status == "shortlist"],
        "consider": [j.__dict__ for j in jobs if j.status == "consider"],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"  Saved digest to {out_path}")
    return out_path


def send_email(jobs: list[NormalizedJob], stats: dict) -> bool:
    """이메일 발송."""
    sender = EmailSender()
    top_jobs = [j for j in jobs if j.status in ("shortlist", "consider")]
    return sender.send_digest(top_jobs, stats)


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily job digest pipeline")
    parser.add_argument(
        "--keywords", "-k",
        default="AI,ML,RAG,LLM,LLM Engineer,RAG Engineer,ML Engineer",
        help="Comma-separated search keywords",
    )
    parser.add_argument("--limit", "-l", type=int, default=50)
    parser.add_argument("--skip-email", action="store_true")
    parser.add_argument("--skip-db", action="store_true")
    args = parser.parse_args()

    keywords = [k.strip() for k in args.keywords.split(",")]

    print(f"\n=== Daily Job Digest ({datetime.now():%Y-%m-%d %H:%M}) ===\n")

    # 1. Collect
    raw_jobs = collect_jobs(keywords, args.limit)
    if not raw_jobs:
        print("No jobs collected. Exiting.")
        sys.exit(1)

    # 2. Normalize
    jobs = normalize_jobs(raw_jobs)

    # 3. Score
    jobs = score_jobs(jobs)

    # Stats
    stats = {
        "collected": len(raw_jobs),
        "normalized": len(jobs),
        "shortlist": sum(1 for j in jobs if j.status == "shortlist"),
        "consider": sum(1 for j in jobs if j.status == "consider"),
    }

    # 4. Save to DB
    if not args.skip_db:
        save_to_db(raw_jobs)

    # 5. Save JSON
    save_json(jobs, raw_jobs)

    # 6. Email
    if not args.skip_email:
        success = send_email(jobs, stats)
        if not success:
            print("Email send failed (non-fatal)")

    print(f"\n=== Done: {stats['shortlist']} shortlist, "
          f"{stats['consider']} consider out of {stats['collected']} ===\n")


if __name__ == "__main__":
    main()
