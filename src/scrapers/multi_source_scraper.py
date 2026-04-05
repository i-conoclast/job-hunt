"""Multi-source job scraper using real APIs."""

from typing import List, Dict, Any
from datetime import datetime
import logging

try:
    from .wanted_api_scraper import WantedAPIScraper
except ImportError:
    WantedAPIScraper = None

logger = logging.getLogger(__name__)


class TestScraper:
    """Fallback test scraper for when real APIs are unavailable."""

    def scrape_jobs(self, keywords: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        """Generate sample job data for testing."""
        sample_jobs = []

        for i in range(min(limit, 3)):  # Generate up to 3 sample jobs
            job = {
                "id": f"test_job_{i+1}",
                "url": f"https://example.com/job/{i+1}",
                "source": "test_source",
                "company": f"Example Corp {i+1}",
                "title": f"AI Engineer - {keywords[0] if keywords else 'ML'} Specialist",
                "location": "Seoul, Korea",
                "work_type": "hybrid" if i % 2 == 0 else "remote",
                "experience": "mid" if i % 3 == 0 else "senior",
                "salary": f"{50000 + i*10000} - {70000 + i*10000} KRW",
                "posted_at": datetime.now().isoformat(),
                "expires_at": None,
                "description": f"""
We are looking for an {keywords[0] if keywords else 'AI'} engineer to join our team.

Required Skills:
- Python programming
- {keywords[0] if keywords else 'Machine Learning'} experience
- RAG system development
- LLM fine-tuning

Preferred Skills:
- PyTorch, TensorFlow
- FastAPI, Django
- AWS, Docker
- PostgreSQL

Responsibilities:
- Develop AI/ML solutions
- Build RAG systems
- Optimize model performance
- Collaborate with product team

Benefits:
- Competitive salary
- Remote work options
- Learning budget
""",
                "requirements": [
                    "Python 3+ years",
                    f"{keywords[0] if keywords else 'ML'} 2+ years",
                    "RAG development experience",
                    "LLM fine-tuning knowledge"
                ],
                "tech_stack": ["Python", "PyTorch", "RAG", "LLM", "FastAPI"],
                "scraped_at": datetime.now().isoformat()
            }
            sample_jobs.append(job)

        return sample_jobs


class MultiSourceScraper:
    """Multi-source scraper supporting real APIs and fallback."""

    def __init__(self):
        self.wanted_scraper = WantedAPIScraper() if WantedAPIScraper else None
        self.test_scraper = TestScraper()

    def scrape_source(self, source: str, keywords: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        """Scrape jobs from a specific source."""
        logger.info(f"Scraping from {source} with keywords: {keywords}")

        if source == "wanted" and self.wanted_scraper:
            try:
                # Use real Wanted API
                raw_jobs = self.wanted_scraper.scrape_jobs(keywords=keywords)

                # Convert to standard format
                converted_jobs = []
                for job in raw_jobs:
                    converted_job = self._convert_wanted_job(job)
                    converted_jobs.append(converted_job)

                logger.info(f"Successfully scraped {len(converted_jobs)} jobs from Wanted")
                return converted_jobs

            except Exception as e:
                logger.error(f"Error scraping Wanted: {e}")
                # Fall back to test data
                return self.test_scraper.scrape_jobs(keywords, min(limit, 2))

        elif source in ["saramin", "jobkorea", "test"]:
            # Use test scraper for other sources (not implemented yet)
            return self.test_scraper.scrape_jobs(keywords, min(limit, 2))

        else:
            logger.warning(f"Unknown source: {source}")
            return []

    def _convert_wanted_job(self, wanted_job: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Wanted API job to standard format."""
        return {
            "id": wanted_job.get("job_id", ""),
            "url": wanted_job.get("url", ""),
            "source": "wanted",
            "company": wanted_job.get("company_name", ""),
            "title": wanted_job.get("title", ""),
            "location": wanted_job.get("location", ""),
            "work_type": wanted_job.get("employment_type", "").lower(),
            "experience": wanted_job.get("experience_level", "").lower(),
            "salary": wanted_job.get("salary", ""),
            "posted_at": datetime.now().isoformat(),  # Wanted API doesn't provide this
            "expires_at": None,
            "description": wanted_job.get("description", ""),
            "requirements": [wanted_job.get("requirements", "")],
            "tech_stack": wanted_job.get("skills", []),
            "scraped_at": datetime.now().isoformat()
        }

    def scrape_all_sources(self, keywords: List[str], limit_per_source: int = 10) -> List[Dict[str, Any]]:
        """Scrape jobs from all available sources."""
        all_jobs = []
        sources = ["wanted", "test"]  # Start with Wanted and test fallback

        for source in sources:
            try:
                jobs = self.scrape_source(source, keywords, limit_per_source)
                all_jobs.extend(jobs)
                logger.info(f"Added {len(jobs)} jobs from {source}")
            except Exception as e:
                logger.error(f"Failed to scrape {source}: {e}")

        return all_jobs