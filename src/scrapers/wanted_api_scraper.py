#!/usr/bin/env python3
"""
Wanted API Scraper
API-based job scraper for Wanted.co.kr inspired by quick-job-finder approach
"""

import requests
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class WantedJob:
    """Wanted API job data structure"""
    id: str
    title: str
    company: str
    url: str
    description: str
    requirements: str
    location: str
    employment_type: str
    experience_level: str
    skills: List[str]
    salary: Optional[str] = None
    benefits: Optional[str] = None


class WantedAPIScraper:
    """API-based scraper for Wanted.co.kr"""
    
    def __init__(self):
        self.base_url = 'https://www.wanted.co.kr'
        self.list_api = 'https://www.wanted.co.kr/api/chaos/navigation/v1/results'
        self.detail_api = 'https://www.wanted.co.kr/api/v4/jobs'
        
        # Headers to mimic browser requests
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Referer': 'https://www.wanted.co.kr/',
            'Origin': 'https://www.wanted.co.kr',
        }
    
    def scrape_jobs(self, keywords: List[str] = None, include_details: bool = True) -> List[Dict]:
        """키워드별로 /api/v4/jobs 검색 API를 호출하여 공고를 수집한다."""
        if keywords is None:
            keywords = ["LLM", "RAG", "AI Engineer", "ML Engineer", "AI Agent", "NLP"]

        seen_ids: set[str] = set()
        jobs: list[Dict] = []

        print(f"🔍 Searching Wanted API for {len(keywords)} keywords")

        for kw in keywords:
            try:
                params = {
                    'query': kw,
                    'country': 'kr',
                    'limit': 20,
                    'offset': 0,
                }
                response = requests.get(
                    f"{self.base_url}/api/v4/jobs",
                    headers=self.headers,
                    params=params,
                )
                response.raise_for_status()
                api_jobs = response.json().get('data', [])
                new_count = 0

                for api_job in api_jobs:
                    job_id = str(api_job.get('id', ''))
                    if not job_id or job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    try:
                        job = self._process_job(api_job)
                        if job:
                            job['search_keyword'] = kw
                            jobs.append(job)
                            new_count += 1
                            print(f"  ✅ Added: {job['title']} at {job['company_name']}")
                        time.sleep(0.3)
                    except Exception as e:
                        print(f"  ⚠️ Error processing job {job_id}: {e}")

                print(f"  📌 query=\"{kw}\" → {len(api_jobs)}개 중 신규 {new_count}개")
                time.sleep(0.5)

            except Exception as e:
                print(f"  ❌ Error searching \"{kw}\": {e}")

        print(f"✅ Total {len(jobs)} unique jobs collected")
        return jobs
    
    def _process_job(self, api_job: Dict) -> Optional[Dict]:
        """Process individual job from API response"""
        job_id = api_job.get('id')
        if not job_id:
            return None
        
        # Get basic info from list API
        title = api_job.get('position', '')
        company_info = api_job.get('company', {})
        company_name = company_info.get('name', '')
        
        # Format location
        address = api_job.get('address', {})
        location_parts = []
        if address.get('location'):
            location_parts.append(address['location'])
        if address.get('district'):
            location_parts.append(address['district'])
        location = ' '.join(location_parts)
        
        # Get detailed info from detail API
        detail_data = self._get_job_detail(job_id)
        
        # Extract information
        description = self._extract_description(detail_data)
        requirements = self._extract_requirements(detail_data)
        skills = self._extract_skills(detail_data, title + ' ' + description)
        employment_type = self._extract_employment_type(detail_data, api_job)
        experience_level = self._extract_experience(detail_data, api_job)
        benefits = self._extract_benefits(detail_data)
        salary = self._extract_salary(detail_data)
        
        return {
            'job_id': str(job_id),
            'title': title,
            'company_name': company_name,
            'url': f"{self.base_url}/wd/{job_id}",
            'location': location,
            'experience': experience_level,
            'education': "",  # Not available in Wanted API
            'employment_type': employment_type,
            'deadline': "",  # Not available in Wanted API
            'tags': skills,
            'skills': skills,
            'description': description,
            'salary': salary or "",
            'source': 'wanted',
            'search_keyword': '',  # Will be set during filtering
            'scraped_at': datetime.now().isoformat(),
            'requirements': [requirements] if requirements else [],
            'benefits': benefits
        }
    
    def _get_job_detail(self, job_id: str) -> Dict:
        """Get detailed job information from detail API"""
        try:
            detail_url = f"{self.detail_api}/{job_id}"
            response = requests.get(detail_url, headers=self.headers)
            response.raise_for_status()
            return response.json().get('job', {})
        except Exception as e:
            print(f"    ⚠️ Could not fetch details for job {job_id}: {e}")
            return {}
    
    def _extract_description(self, detail_data: Dict) -> str:
        """Extract job description from detail data"""
        detail = detail_data.get('detail', {})
        if not detail:
            return ""
        
        parts = []
        if detail.get('intro'):
            parts.append(f"회사 소개:\n{detail['intro']}")
        if detail.get('main_tasks'):
            parts.append(f"주요 업무:\n{detail['main_tasks']}")
        if detail.get('benefits'):
            parts.append(f"혜택 및 복지:\n{detail['benefits']}")
        
        return "\n\n".join(parts)
    
    def _extract_requirements(self, detail_data: Dict) -> str:
        """Extract job requirements"""
        detail = detail_data.get('detail', {})
        if not detail:
            return ""
        
        parts = []
        if detail.get('requirements'):
            parts.append(f"자격 요건:\n{detail['requirements']}")
        if detail.get('preferred_points'):
            parts.append(f"우대 사항:\n{detail['preferred_points']}")
        
        return "\n\n".join(parts)
    
    def _extract_skills(self, detail_data: Dict, text: str) -> List[str]:
        """Extract skills from detail data and text"""
        skills = set()
        
        # From skill_tags
        skill_tags = detail_data.get('skill_tags', [])
        for tag in skill_tags:
            if isinstance(tag, dict) and tag.get('title'):
                skills.add(tag['title'])
            elif isinstance(tag, str):
                skills.add(tag)
        
        # From text pattern matching
        text_lower = text.lower()
        tech_patterns = [
            'python', 'java', 'javascript', 'typescript', 'react', 'vue', 'angular',
            'node.js', 'spring', 'django', 'flask', 'aws', 'docker', 'kubernetes',
            'mysql', 'postgresql', 'mongodb', 'redis', 'tensorflow', 'pytorch',
            'machine learning', 'ai', 'deep learning', 'data science', 'ml'
        ]
        
        for pattern in tech_patterns:
            if pattern in text_lower:
                skills.add(pattern.title())
        
        return list(skills)[:10]  # Limit to 10 skills
    
    def _extract_employment_type(self, detail_data: Dict, api_job: Dict) -> str:
        """Extract employment type"""
        emp_type = (detail_data.get('position_type') or 
                   detail_data.get('employment_type') or 
                   api_job.get('employment_type', ''))
        
        if 'regular' in emp_type.lower() or '정규직' in emp_type:
            return '정규직'
        elif 'contract' in emp_type.lower() or '계약직' in emp_type:
            return '계약직'
        elif 'intern' in emp_type.lower() or '인턴' in emp_type:
            return '인턴'
        else:
            return '정규직'  # Default
    
    def _extract_experience(self, detail_data: Dict, api_job: Dict) -> str:
        """Extract experience level"""
        if api_job.get('is_newbie'):
            return '신입'
        
        annual_from = api_job.get('annual_from')
        annual_to = api_job.get('annual_to')
        
        if annual_from is not None and annual_to is not None:
            if annual_from == 0 and annual_to == 0:
                return '신입'
            elif annual_from == annual_to:
                return f'{annual_from}년'
            else:
                return f'{annual_from}-{annual_to}년'
        
        # Fallback to text analysis
        exp_text = detail_data.get('experience_level', '') or detail_data.get('career', '')
        if '신입' in exp_text:
            return '신입'
        
        return '경력무관'
    
    def _extract_benefits(self, detail_data: Dict) -> Optional[str]:
        """Extract benefits information"""
        benefits = []
        
        # From company tags
        company_tags = detail_data.get('company_tags', [])
        for tag in company_tags:
            if isinstance(tag, dict) and tag.get('title'):
                benefits.append(tag['title'])
        
        if benefits:
            return ', '.join(benefits[:5])  # Limit to 5 benefits
        
        return None
    
    def _extract_salary(self, detail_data: Dict) -> Optional[str]:
        """Extract salary information"""
        salary = detail_data.get('salary') or detail_data.get('annual_salary')
        if salary:
            return str(salary)
        return None
    
    def _matches_keywords(self, job: Dict, keywords: List[str]) -> bool:
        """Check if job matches any of the keywords"""
        if not keywords:
            return True
        
        title = job.get('title', '')
        description = job.get('description', '')
        requirements = ' '.join(job.get('requirements', []))
        skills = ' '.join(job.get('skills', []))
        text = f"{title} {description} {requirements} {skills}".lower()
        return any(keyword.lower() in text for keyword in keywords)


def main():
    """Test the scraper"""
    scraper = WantedAPIScraper()
    keywords = ["AI", "머신러닝", "데이터사이언스", "Machine Learning"]
    jobs = scraper.scrape_jobs(keywords)
    
    print(f"\n📊 Test Results:")
    print(f"Found {len(jobs)} jobs")
    for job in jobs[:3]:
        print(f"\n- {job['title']} at {job['company_name']}")
        print(f"  Skills: {', '.join(job['skills'][:5])}")
        print(f"  Description length: {len(job['description'])} chars")


if __name__ == "__main__":
    main()