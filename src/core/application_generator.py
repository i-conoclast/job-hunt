"""Application document generation module."""

from typing import Dict, List, Any, Optional
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import yaml
from datetime import datetime

from .job_normalizer import NormalizedJob


class ExperienceSnippet:
    """Represents a reusable experience snippet."""

    def __init__(self, data: Dict[str, Any]):
        self.id = data["id"]
        self.title = data["title"]
        self.one_liner_ko = data["one_liner_ko"]
        self.one_liner_en = data.get("one_liner_en", "")
        self.impact_metrics = data.get("impact_metrics", [])
        self.tags = data.get("tags", [])
        self.bullets_ko = data.get("bullets_ko", [])
        self.bullets_en = data.get("bullets_en", [])


class ApplicationGenerator:
    """Generates customized application documents."""

    def __init__(self, templates_dir: str = None, snippets_dir: str = None):
        """Initialize generator with templates and snippets."""
        if templates_dir:
            self.templates_dir = Path(templates_dir)
        else:
            self.templates_dir = Path(__file__).parent.parent.parent / "templates"

        if snippets_dir:
            self.snippets_dir = Path(snippets_dir)
        else:
            self.snippets_dir = Path(__file__).parent.parent.parent / "snippets"

        self.env = Environment(loader=FileSystemLoader(str(self.templates_dir)))
        self.snippets = self._load_snippets()

    def _load_snippets(self) -> Dict[str, ExperienceSnippet]:
        """Load experience snippets."""
        snippets = {}
        snippets_file = self.snippets_dir / "experience_snippets.yml"

        if snippets_file.exists():
            with open(snippets_file, 'r', encoding='utf-8') as f:
                snippets_data = yaml.safe_load(f)
                for snippet_data in snippets_data:
                    snippet = ExperienceSnippet(snippet_data)
                    snippets[snippet.id] = snippet

        return snippets

    def generate_resume(self, job: NormalizedJob, template_type: str = "ko_rag",
                       selected_snippets: List[str] = None) -> str:
        """Generate customized resume."""
        template_name = f"resume/{template_type}.html"
        template = self.env.get_template(template_name)

        # Select relevant snippets
        if not selected_snippets:
            selected_snippets = self._select_snippets_for_job(job, max_snippets=3)

        snippets = [self.snippets[sid] for sid in selected_snippets if sid in self.snippets]

        # Prepare template variables
        context = {
            "job": job,
            "snippets": snippets,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "top_skills": self._get_top_skills_for_job(job),
            "relevant_metrics": self._get_relevant_metrics(snippets)
        }

        return template.render(**context)

    def generate_cover_letter(self, job: NormalizedJob, template_type: str = "short",
                            selected_snippets: List[str] = None) -> str:
        """Generate customized cover letter."""
        template_name = f"cover_letter/{template_type}.html"
        template = self.env.get_template(template_name)

        # Select relevant snippets
        if not selected_snippets:
            selected_snippets = self._select_snippets_for_job(job, max_snippets=2)

        snippets = [self.snippets[sid] for sid in selected_snippets if sid in self.snippets]

        # Extract key requirements from job
        key_requirements = self._extract_key_requirements(job)

        context = {
            "job": job,
            "snippets": snippets,
            "key_requirements": key_requirements,
            "generated_at": datetime.now().strftime("%Y-%m-%d"),
            "talking_points": self._generate_talking_points(job, snippets)
        }

        return template.render(**context)

    def generate_email(self, job: NormalizedJob, email_type: str = "recruiter_dm") -> str:
        """Generate email/DM template."""
        template_name = f"emails/{email_type}.html"
        template = self.env.get_template(template_name)

        # Get best snippet for this job
        best_snippets = self._select_snippets_for_job(job, max_snippets=1)
        best_snippet = self.snippets[best_snippets[0]] if best_snippets else None

        context = {
            "job": job,
            "best_snippet": best_snippet,
            "contact_info": self._get_contact_info(),
            "generated_at": datetime.now().strftime("%Y-%m-%d")
        }

        return template.render(**context)

    def generate_job_kit(self, job: NormalizedJob, output_dir: str = None) -> Dict[str, str]:
        """Generate complete job application kit."""
        if not output_dir:
            output_dir = Path(__file__).parent.parent.parent / "out" / "jobkits" / job.job_id

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        kit = {}

        # Generate documents
        kit["resume_ko"] = self.generate_resume(job, "ko_rag")
        kit["cover_letter"] = self.generate_cover_letter(job, "short")
        kit["recruiter_email"] = self.generate_email(job, "recruiter_dm")
        kit["followup_email"] = self.generate_email(job, "followup")

        # Save to files
        for doc_type, content in kit.items():
            file_path = output_path / f"{doc_type}.html"
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

        # Generate summary
        summary = self._generate_kit_summary(job, kit)
        summary_path = output_path / "summary.txt"
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary)

        return kit

    def _select_snippets_for_job(self, job: NormalizedJob, max_snippets: int = 3) -> List[str]:
        """Select most relevant snippets for job."""
        snippet_scores = []

        for snippet_id, snippet in self.snippets.items():
            score = self._score_snippet_relevance(snippet, job)
            snippet_scores.append((snippet_id, score))

        # Sort by relevance and return top snippets
        snippet_scores.sort(key=lambda x: x[1], reverse=True)
        return [snippet_id for snippet_id, _ in snippet_scores[:max_snippets]]

    def _score_snippet_relevance(self, snippet: ExperienceSnippet, job: NormalizedJob) -> float:
        """Score how relevant a snippet is to a job."""
        score = 0.0

        # Tag matching
        job_tags = set(tag.lower() for tag in job.tech_stack)
        snippet_tags = set(tag.lower() for tag in snippet.tags)
        tag_overlap = len(job_tags.intersection(snippet_tags))
        score += tag_overlap * 10

        # Domain relevance
        snippet_text = f"{snippet.title} {' '.join(snippet.bullets_ko)}".lower()
        for domain in job.domain:
            if domain.lower() in snippet_text:
                score += 5

        # Required skills matching
        for requirement in job.requirements_must:
            if any(tag.lower() in requirement.lower() for tag in snippet.tags):
                score += 8

        return score

    def _extract_key_requirements(self, job: NormalizedJob) -> List[str]:
        """Extract 3 key requirements from job."""
        all_requirements = job.requirements_must + job.tech_stack[:3]
        return all_requirements[:3]

    def _generate_talking_points(self, job: NormalizedJob, snippets: List[ExperienceSnippet]) -> List[str]:
        """Generate talking points for cover letter."""
        points = []

        # Add snippet-based points
        for snippet in snippets:
            if snippet.impact_metrics:
                points.append(f"{snippet.title}: {snippet.impact_metrics[0]}")

        # Add tech stack alignment
        relevant_tech = [tech for tech in job.tech_stack if tech.lower() in ["rag", "llm", "python", "pytorch"]]
        if relevant_tech:
            points.append(f"Technology alignment: {', '.join(relevant_tech[:3])}")

        return points[:3]

    def _get_top_skills_for_job(self, job: NormalizedJob) -> List[str]:
        """Get top skills to highlight for job."""
        return job.tech_stack[:5] + job.requirements_must[:3]

    def _get_relevant_metrics(self, snippets: List[ExperienceSnippet]) -> List[str]:
        """Get relevant metrics from snippets."""
        metrics = []
        for snippet in snippets:
            metrics.extend(snippet.impact_metrics)
        return metrics[:3]

    def _get_contact_info(self) -> Dict[str, str]:
        """Get contact information."""
        return {
            "name": "김지원",  # This should be configurable
            "email": "example@email.com",
            "phone": "010-0000-0000",
            "portfolio": "https://portfolio.example.com"
        }

    def _generate_kit_summary(self, job: NormalizedJob, kit: Dict[str, str]) -> str:
        """Generate summary of generated kit."""
        summary = f"""Job Application Kit Generated
============================

Job: {job.role_title} at {job.company}
Score: {job.priority_score:.1f} ({job.fit_label})
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Documents Generated:
- Resume (Korean RAG version)
- Cover Letter (Short version)
- Recruiter Email/DM
- Follow-up Email

Key Highlights:
- Tech Stack Match: {', '.join(job.tech_stack[:3])}
- Domain: {', '.join(job.domain)}
- Work Type: {job.work_type}

Next Steps:
1. Review and customize documents
2. Submit application
3. Set follow-up reminder for {job.job_id}
"""
        return summary