"""Job data normalization and standardization module."""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
import re


@dataclass
class NormalizedJob:
    """Standardized job data structure."""
    job_id: str
    source_url: str
    source: str
    company: str
    role_title: str
    location: str
    work_type: str  # onsite/hybrid/remote
    seniority: str  # junior/mid/senior/lead
    salary_range: Optional[str]
    posted_at: datetime
    expires_at: Optional[datetime]
    recency_days: int
    requirements_must: List[str]
    requirements_nice: List[str]
    responsibilities: List[str]
    tech_stack: List[str]
    domain: List[str]
    languages: List[str]
    red_flags: List[str]
    notes: str
    status: str = "backlog"
    priority_score: float = 0.0
    fit_label: str = "C"


class JobNormalizer:
    """Normalizes raw job data into standardized format."""

    SENIORITY_MAPPING = {
        "신입": "junior",
        "경력": "mid",
        "시니어": "senior",
        "리드": "lead",
        "주니어": "junior",
        "junior": "junior",
        "mid": "mid",
        "senior": "senior",
        "lead": "lead"
    }

    WORK_TYPE_MAPPING = {
        "재택": "remote",
        "원격": "remote",
        "하이브리드": "hybrid",
        "혼합": "hybrid",
        "출근": "onsite",
        "사무실": "onsite",
        "remote": "remote",
        "hybrid": "hybrid",
        "onsite": "onsite"
    }

    TECH_STACK_KEYWORDS = [
        "python", "pytorch", "tensorflow", "scikit-learn", "pandas", "numpy",
        "fastapi", "django", "flask", "react", "vue", "javascript", "typescript",
        "aws", "azure", "gcp", "docker", "kubernetes", "mlflow", "airflow",
        "postgresql", "mongodb", "redis", "elasticsearch", "kafka",
        "rag", "llm", "transformer", "bert", "gpt", "langchain", "llamaindex"
    ]

    RED_FLAG_KEYWORDS = [
        "야근", "주말근무", "출장 100%", "회식", "술자리", "과도한 업무",
        "무급 야근", "강제 회식", "과도한 출장"
    ]

    def normalize(self, raw_job: Dict[str, Any]) -> NormalizedJob:
        """Convert raw job data to normalized format."""
        job_id = self._generate_job_id(raw_job)

        return NormalizedJob(
            job_id=job_id,
            source_url=raw_job.get("url", ""),
            source=raw_job.get("source", "unknown"),
            company=self._clean_text(raw_job.get("company", "")),
            role_title=self._clean_text(raw_job.get("title", "")),
            location=self._normalize_location(raw_job.get("location", "")),
            work_type=self._normalize_work_type(raw_job.get("work_type", "")),
            seniority=self._normalize_seniority(raw_job.get("experience", "")),
            salary_range=self._normalize_salary(raw_job.get("salary", "")),
            posted_at=self._parse_date(raw_job.get("posted_at")),
            expires_at=self._parse_date(raw_job.get("expires_at")),
            recency_days=self._calculate_recency(raw_job.get("posted_at")),
            requirements_must=self._extract_requirements(raw_job.get("description", ""), required=True),
            requirements_nice=self._extract_requirements(raw_job.get("description", ""), required=False),
            responsibilities=self._extract_responsibilities(raw_job.get("description", "")),
            tech_stack=self._extract_tech_stack(raw_job.get("description", "")),
            domain=self._extract_domain(raw_job.get("company", ""), raw_job.get("description", "")),
            languages=self._extract_languages(raw_job.get("description", "")),
            red_flags=self._extract_red_flags(raw_job.get("description", "")),
            notes=""
        )

    def _generate_job_id(self, raw_job: Dict[str, Any]) -> str:
        """Generate unique job ID."""
        source = raw_job.get("source", "unknown")
        company = raw_job.get("company", "unknown")
        title = raw_job.get("title", "unknown")
        timestamp = str(int(datetime.now().timestamp()))[-6:]
        return f"{source}_{company}_{title}_{timestamp}".replace(" ", "_").replace("/", "_")[:50]

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text.strip())

    def _normalize_location(self, location: str) -> str:
        """Normalize location information."""
        if not location:
            return "unknown"

        location_mapping = {
            "서울": "Seoul",
            "부산": "Busan",
            "대구": "Daegu",
            "인천": "Incheon",
            "광주": "Gwangju",
            "대전": "Daejeon",
            "울산": "Ulsan",
            "경기": "Gyeonggi",
            "강남": "Seoul-Gangnam",
            "판교": "Pangyo"
        }

        for korean, english in location_mapping.items():
            if korean in location:
                return english

        return self._clean_text(location)

    def _normalize_work_type(self, work_type: str) -> str:
        """Normalize work type."""
        work_type_lower = work_type.lower()
        for keyword, normalized in self.WORK_TYPE_MAPPING.items():
            if keyword in work_type_lower:
                return normalized
        return "unknown"

    def _normalize_seniority(self, experience: str) -> str:
        """Normalize seniority level."""
        experience_lower = experience.lower()
        for keyword, normalized in self.SENIORITY_MAPPING.items():
            if keyword in experience_lower:
                return normalized
        return "unknown"

    def _normalize_salary(self, salary: str) -> Optional[str]:
        """Normalize salary information."""
        if not salary or salary == "0":
            return None
        return self._clean_text(salary)

    def _parse_date(self, date_str: Any) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None

        if isinstance(date_str, datetime):
            return date_str

        try:
            if isinstance(date_str, str):
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            pass

        return None

    def _calculate_recency(self, posted_at: Any) -> int:
        """Calculate days since posting."""
        if not posted_at:
            return 999

        posted_date = self._parse_date(posted_at)
        if not posted_date:
            return 999

        return (datetime.now() - posted_date).days

    def _extract_requirements(self, description: str, required: bool = True) -> List[str]:
        """Extract required or preferred requirements."""
        if not description:
            return []

        requirements = []
        description_lower = description.lower()

        if required:
            patterns = [r'필수.*?(?=우대|기타|$)', r'required.*?(?=preferred|$)', r'must.*?(?=nice|$)']
        else:
            patterns = [r'우대.*?(?=기타|$)', r'preferred.*?(?=$)', r'nice.*?(?=$)']

        for pattern in patterns:
            matches = re.findall(pattern, description_lower, re.DOTALL)
            for match in matches:
                lines = [line.strip() for line in match.split('\n') if line.strip()]
                requirements.extend(lines)

        return requirements[:5]  # Limit to 5 most relevant

    def _extract_responsibilities(self, description: str) -> List[str]:
        """Extract job responsibilities."""
        if not description:
            return []

        responsibilities = []
        patterns = [r'담당업무.*?(?=자격요건|$)', r'responsibilities.*?(?=requirements|$)']

        for pattern in patterns:
            matches = re.findall(pattern, description.lower(), re.DOTALL)
            for match in matches:
                lines = [line.strip() for line in match.split('\n') if line.strip()]
                responsibilities.extend(lines)

        return responsibilities[:5]  # Limit to 5 most relevant

    def _extract_tech_stack(self, description: str) -> List[str]:
        """Extract technology stack."""
        if not description:
            return []

        tech_stack = []
        description_lower = description.lower()

        for tech in self.TECH_STACK_KEYWORDS:
            if tech in description_lower:
                tech_stack.append(tech)

        return list(set(tech_stack))

    def _extract_domain(self, company: str, description: str) -> List[str]:
        """Extract business domain."""
        domains = []
        text = f"{company} {description}".lower()

        domain_keywords = {
            "fintech": ["핀테크", "금융", "은행", "카드", "결제", "투자"],
            "ecommerce": ["이커머스", "쇼핑", "온라인몰", "유통", "리테일"],
            "healthcare": ["헬스케어", "의료", "병원", "제약", "바이오"],
            "education": ["교육", "에듀테크", "학습", "강의", "교육용"],
            "gaming": ["게임", "엔터테인먼트", "모바일게임"],
            "public": ["공공", "정부", "행정", "공기업"]
        }

        for domain, keywords in domain_keywords.items():
            if any(keyword in text for keyword in keywords):
                domains.append(domain)

        return domains

    def _extract_languages(self, description: str) -> List[str]:
        """Extract language requirements."""
        if not description:
            return ["KR"]

        languages = []
        description_lower = description.lower()

        if any(keyword in description_lower for keyword in ["영어", "english", "toeic", "opic"]):
            languages.append("EN")

        if any(keyword in description_lower for keyword in ["한국어", "korean"]):
            languages.append("KR")

        return languages if languages else ["KR"]

    def _extract_red_flags(self, description: str) -> List[str]:
        """Extract potential red flags."""
        if not description:
            return []

        red_flags = []
        description_lower = description.lower()

        for flag in self.RED_FLAG_KEYWORDS:
            if flag in description_lower:
                red_flags.append(flag)

        return red_flags