#!/usr/bin/env python3
"""Job Hunt CLI - Main command interface for recruitment operations system."""

import click
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add parent directory to path for imports
import sys
sys.path.append(str(Path(__file__).parent.parent))

from src.core.job_normalizer import JobNormalizer, NormalizedJob
from src.core.job_scorer import JobScorer
from src.core.application_generator import ApplicationGenerator
from src.scrapers.multi_source_scraper import MultiSourceScraper


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Job Hunt - Recruitment Operations System CLI

    Automate job application workflows: collect → normalize → score → generate → track
    """
    pass


@cli.command()
@click.option('--source', '-s', multiple=True, default=['wanted'],
              help='Job sources to scrape (wanted, saramin, jobkorea)')
@click.option('--keywords', '-k', default='AI,ML,RAG,LLM',
              help='Search keywords (comma-separated)')
@click.option('--limit', '-l', default=50, help='Maximum jobs to collect')
@click.option('--output', '-o', help='Output file path')
def collect(source, keywords, limit, output):
    """Collect jobs from multiple sources."""
    click.echo(f"🔍 Collecting jobs from: {', '.join(source)}")
    click.echo(f"🎯 Keywords: {keywords}")

    scraper = MultiSourceScraper()
    keyword_list = [k.strip() for k in keywords.split(',')]

    all_jobs = []
    for src in source:
        click.echo(f"📡 Scraping {src}...")
        try:
            jobs = scraper.scrape_source(src, keywords=keyword_list, limit=limit)
            all_jobs.extend(jobs)
            click.echo(f"✅ Found {len(jobs)} jobs from {src}")
        except Exception as e:
            click.echo(f"❌ Error scraping {src}: {e}")

    # Save raw data
    if not output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"data/raw_jd/jobs_{timestamp}.json"

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_jobs, f, ensure_ascii=False, indent=2, default=str)

    click.echo(f"💾 Saved {len(all_jobs)} jobs to {output}")


@cli.command()
@click.argument('input_file')
@click.option('--output', '-o', help='Output file path')
def normalize(input_file, output):
    """Normalize raw job data to standardized format."""
    click.echo(f"🔄 Normalizing jobs from {input_file}")

    # Load raw jobs
    with open(input_file, 'r', encoding='utf-8') as f:
        raw_jobs = json.load(f)

    normalizer = JobNormalizer()
    normalized_jobs = []

    click.echo(f"📊 Processing {len(raw_jobs)} jobs...")
    with click.progressbar(raw_jobs, label='Normalizing jobs') as jobs:
        for raw_job in jobs:
            try:
                normalized = normalizer.normalize(raw_job)
                normalized_jobs.append(normalized.__dict__)
            except Exception as e:
                click.echo(f"⚠️  Error normalizing job: {e}")

    # Save normalized data
    if not output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"data/normalized/jobs_normalized_{timestamp}.json"

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(normalized_jobs, f, ensure_ascii=False, indent=2, default=str)

    click.echo(f"✅ Normalized {len(normalized_jobs)} jobs saved to {output}")


@cli.command()
@click.argument('input_file')
@click.option('--config', '-c', help='Scoring configuration file')
@click.option('--output', '-o', help='Output file path')
def score(input_file, config, output):
    """Score and prioritize normalized jobs."""
    click.echo(f"🎯 Scoring jobs from {input_file}")

    # Load normalized jobs
    with open(input_file, 'r', encoding='utf-8') as f:
        job_data = json.load(f)

    scorer = JobScorer(config)
    scored_jobs = []

    click.echo(f"🧮 Scoring {len(job_data)} jobs...")
    with click.progressbar(job_data, label='Scoring jobs') as jobs:
        for job_dict in jobs:
            # Convert dict back to NormalizedJob
            job = NormalizedJob(**job_dict)

            # Score the job
            score_value = scorer.score_job(job)
            priority = scorer.classify_priority(score_value)
            fit_label = scorer.get_fit_label(score_value)

            # Update job with scores
            job.priority_score = score_value
            job.fit_label = fit_label
            job.status = priority

            scored_jobs.append(job.__dict__)

    # Sort by score (highest first)
    scored_jobs.sort(key=lambda x: x['priority_score'], reverse=True)

    # Save scored data
    if not output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"data/normalized/jobs_scored_{timestamp}.json"

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(scored_jobs, f, ensure_ascii=False, indent=2, default=str)

    # Show summary
    shortlist = [j for j in scored_jobs if j['status'] == 'shortlist']
    consider = [j for j in scored_jobs if j['status'] == 'consider']

    click.echo(f"📊 Scoring Summary:")
    click.echo(f"   🟢 Shortlist: {len(shortlist)} jobs (score ≥ 75)")
    click.echo(f"   🟡 Consider: {len(consider)} jobs (score 60-74)")
    click.echo(f"   🔴 Backlog: {len(scored_jobs) - len(shortlist) - len(consider)} jobs")
    click.echo(f"💾 Saved scored jobs to {output}")


@cli.command()
@click.option('--job-id', required=True, help='Job ID to generate kit for')
@click.option('--resume', default='ko_rag', help='Resume template type')
@click.option('--cover', default='short', help='Cover letter template type')
@click.option('--snippets', help='Comma-separated snippet IDs to use')
@click.option('--output-dir', help='Output directory for job kit')
def generate(job_id, resume, cover, snippets, output_dir):
    """Generate application documents for a specific job."""
    click.echo(f"📝 Generating job kit for {job_id}")

    # Find job data (you'd typically search through scored jobs file)
    # For now, create a sample job
    sample_job = NormalizedJob(
        job_id=job_id,
        source_url="https://example.com",
        source="wanted",
        company="Example Corp",
        role_title="AI Engineer",
        location="Seoul",
        work_type="hybrid",
        seniority="mid",
        salary_range="60,000,000 - 80,000,000 KRW",
        posted_at=datetime.now(),
        expires_at=None,
        recency_days=1,
        requirements_must=["Python", "LLM", "RAG"],
        requirements_nice=["PyTorch", "FastAPI"],
        responsibilities=["AI model development", "System optimization"],
        tech_stack=["Python", "PyTorch", "LLM", "RAG", "FastAPI"],
        domain=["fintech"],
        languages=["KR", "EN"],
        red_flags=[],
        notes="High priority application",
        priority_score=85.0,
        fit_label="A"
    )

    generator = ApplicationGenerator()

    selected_snippets = None
    if snippets:
        selected_snippets = [s.strip() for s in snippets.split(',')]

    kit = generator.generate_job_kit(sample_job, output_dir)

    click.echo(f"✅ Generated job kit:")
    for doc_type in kit.keys():
        click.echo(f"   📄 {doc_type}")

    if output_dir:
        click.echo(f"💾 Saved to: {output_dir}")


@cli.command()
@click.argument('scored_jobs_file')
@click.option('--top', default=10, help='Number of top jobs to show')
def triage(scored_jobs_file, top):
    """Show today's triage - top-scored jobs for review."""
    click.echo(f"📋 Today's Job Triage (Top {top})")

    with open(scored_jobs_file, 'r', encoding='utf-8') as f:
        jobs = json.load(f)

    # Filter for shortlist and consider
    priority_jobs = [j for j in jobs if j['status'] in ['shortlist', 'consider']]
    top_jobs = priority_jobs[:top]

    click.echo("\n" + "="*80)
    for i, job in enumerate(top_jobs, 1):
        status_emoji = "🟢" if job['status'] == 'shortlist' else "🟡"
        click.echo(f"{i:2d}. {status_emoji} [{job['priority_score']:5.1f}] {job['company']} - {job['role_title']}")
        click.echo(f"     📍 {job['location']} | 💼 {job['work_type']} | 🏷️  {job['fit_label']}")
        click.echo(f"     🔧 {', '.join(job['tech_stack'][:4])}")
        if job['red_flags']:
            click.echo(f"     ⚠️  {', '.join(job['red_flags'])}")
        click.echo("")

    shortlist_count = len([j for j in jobs if j['status'] == 'shortlist'])
    click.echo(f"📊 Summary: {shortlist_count} shortlist jobs ready for immediate application")


@cli.command()
@click.argument('scored_jobs_file')
@click.option('--format', 'output_format', default='notion',
              type=click.Choice(['notion', 'airtable', 'csv']),
              help='Export format')
@click.option('--output', '-o', help='Output file path')
def export(scored_jobs_file, output_format, output):
    """Export jobs to external systems (Notion, Airtable, CSV)."""
    click.echo(f"📤 Exporting jobs to {output_format} format")

    with open(scored_jobs_file, 'r', encoding='utf-8') as f:
        jobs = json.load(f)

    if output_format == 'csv':
        import csv

        if not output:
            output = f"jobs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        with open(output, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['job_id', 'company', 'role_title', 'priority_score', 'fit_label',
                         'status', 'location', 'work_type', 'tech_stack', 'source_url']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for job in jobs:
                row = {field: job.get(field, '') for field in fieldnames}
                row['tech_stack'] = ', '.join(job.get('tech_stack', []))
                writer.writerow(row)

        click.echo(f"✅ Exported {len(jobs)} jobs to {output}")

    else:
        click.echo(f"⚠️  {output_format} export not yet implemented")


if __name__ == '__main__':
    cli()