#!/usr/bin/env python3
"""
Saramin HTML Scraper
Scrapes job listings from Saramin using BeautifulSoup
Configuration-driven approach
"""

import time
import re
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin, quote

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from core.config_loader import get_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SaraminScraper:
    """Scraper for Saramin job listings"""
    
    def __init__(self):
        self.config = get_config()
        self.site_config = self.config.get_site_config('saramin')
        self.session = requests.Session()
        self.last_request_time = 0
        self.setup_headers()
        
        # Load configuration values with defaults
        self.BASE_URL = self.config.get_site_url('saramin')
        self.SEARCH_URL = self.site_config.get('search_url', 'https://www.saramin.co.kr/zf_user/search/recruit')
        self.RATE_LIMIT_SECONDS = self.config.get_rate_limit('saramin')
        self.MAX_PAGES = self.config.get_max_pages('saramin')
        self.ITEMS_PER_PAGE = self.site_config.get('items_per_page', 50)
        # Default selectors for saramin
        self.selectors = {
            'job_item': '.item_recruit',
            'title': '.job_tit a',
            'company': '.corp_name a',
            'location': '.job_condition span:nth-of-type(1)',
            'experience': '.job_condition span:nth-of-type(2)',
            'education': '.job_condition span:nth-of-type(3)',
            'employment_type': '.job_condition span:nth-of-type(4)',
            'deadline': '.job_date .date',
            'tags': '.job_sector'
        }
    
    def setup_headers(self):
        """Set up request headers from config"""
        headers = self.config.get_site_headers('saramin')
        self.session.headers.update(headers)
    
    def _rate_limit(self):
        """Enforce rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.RATE_LIMIT_SECONDS:
            sleep_time = self.RATE_LIMIT_SECONDS - time_since_last
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def search_jobs(self, 
                   keyword: str,
                   page: int = 1) -> List[Dict]:
        """
        Search for jobs on Saramin
        
        Args:
            keyword: Search keyword
            page: Page number
        
        Returns:
            List of job dictionaries
        """
        self._rate_limit()
        
        params = {
            'searchType': 'search',
            'searchword': keyword,
            'recruitPage': page,
            'recruitSort': 'relation',  # relevance
            'recruitPageCount': self.ITEMS_PER_PAGE
        }
        
        # Add category if configured
        if 'category_codes' in self.site_config:
            params['cat_kewd'] = '2'  # IT 카테고리 코드
        
        try:
            response = self.session.get(self.SEARCH_URL, params=params)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser', from_encoding='utf-8')
            jobs = self.parse_search_results(soup)
            
            logger.info(f"Found {len(jobs)} jobs on page {page} for '{keyword}'")
            return jobs
            
        except Exception as e:
            logger.error(f"Error searching Saramin: {e}")
            return []
    
    def parse_search_results(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse job listings from search results page"""
        jobs = []
        
        # Use selector from config
        job_items = soup.select(self.selectors['job_item'])
        logger.debug(f"Found {len(job_items)} job items with selector: {self.selectors['job_item']}")
        
        for item in job_items:
            try:
                job = self.parse_job_item(item)
                if job:
                    jobs.append(job)
                else:
                    logger.debug("Job item parsed but missing external_id")
            except Exception as e:
                logger.debug(f"Error parsing job item: {e}")
                continue
        
        return jobs
    
    def parse_job_item(self, item) -> Optional[Dict]:
        """Parse individual job listing using config selectors"""
        job = {
            'source': 'saramin',
            'source_method': 'scraping'
        }
        
        # Try multiple selectors for company
        company_elem = None
        company_selectors = ['a.str_tit', '.corp_name a', '.company_nm a', 'h4 a']
        for selector in company_selectors:
            company_elem = item.select_one(selector)
            if company_elem:
                break
        
        if company_elem:
            job['company_name'] = company_elem.get_text(strip=True)
            company_link = company_elem.get('href')
            if company_link:
                job['company_url'] = urljoin(self.BASE_URL, company_link)
        
        # Try multiple selectors for job title
        title_elem = None
        title_selectors = ['h2.job_tit a', '.job_tit a', '.notification_info .job_tit a', 'h3 a']
        for selector in title_selectors:
            title_elem = item.select_one(selector)
            if title_elem:
                break
        
        if title_elem:
            job['title'] = title_elem.get('title', '').strip() or title_elem.get_text(strip=True)
            job_url = title_elem.get('href')
            if job_url:
                job['url'] = urljoin(self.BASE_URL, job_url)
                # Extract job ID from URL - try multiple patterns
                job_id_patterns = [r'rec_idx=(\d+)', r'recruit/(\d+)', r'/(\d+)/?$']
                for pattern in job_id_patterns:
                    job_id_match = re.search(pattern, job_url)
                    if job_id_match:
                        job['external_id'] = job_id_match.group(1)
                        break
        
        # Try multiple selectors for job conditions
        conditions = None
        condition_selectors = ['div.job_condition', '.job_condition', '.recruit_condition', '.conditions']
        for selector in condition_selectors:
            conditions = item.select_one(selector)
            if conditions:
                break
        
        if conditions:
            condition_text = conditions.get_text(strip=True)
            
            # Parse using config functions
            job['location'] = self._extract_location(condition_text)
            job['employment_type'] = self.config.parse_employment_type(condition_text)
            job['experience_level'] = self.config.parse_experience_level(condition_text)
            job['education_level'] = self.config.parse_education_level(condition_text)
            
            # Check for remote work
            if self.config.is_remote_work(condition_text):
                job['work_type'] = 'remote'
            elif '하이브리드' in condition_text:
                job['work_type'] = 'hybrid'
            else:
                job['work_type'] = 'office'
        
        # Try multiple selectors for tags
        tags = []
        tag_selectors = ['div.job_sector span', '.job_sector span', '.recruit_sector span', '.job_meta span']
        for selector in tag_selectors:
            tags_elem = item.select(selector)
            if tags_elem:
                for elem in tags_elem:
                    tag = elem.get_text(strip=True)
                    if tag and tag != ',' and tag not in tags:
                        tags.append(tag)
                break
        job['tags'] = tags
        
        # Try multiple selectors for deadline
        deadline_elem = None
        deadline_selectors = ['span.job_day', '.job_day', '.dday', '.deadline']
        for selector in deadline_selectors:
            deadline_elem = item.select_one(selector)
            if deadline_elem:
                break
        
        if deadline_elem:
            deadline_text = deadline_elem.get_text(strip=True)
            job['deadline_text'] = deadline_text
            job['deadline'] = self.parse_deadline(deadline_text)
        
        # Badge information
        badge_elem = item.select_one('span.badge')
        if badge_elem:
            job['badge'] = badge_elem.get_text(strip=True)
        
        # Add basic info even without external_id for debugging
        job['crawled_at'] = datetime.now().isoformat()
        
        return job
    
    def _extract_location(self, text: str) -> Optional[str]:
        """Extract location from text using config"""
        locations = self.config.get_locations()
        all_locations = locations['major_cities'] + locations['remote']
        
        for location in all_locations:
            if location in text:
                return location
        
        # Try to find any location pattern
        location_match = re.search(r'(서울|경기|인천|부산|대구|대전|광주|울산|세종)[^\s]*', text)
        if location_match:
            return location_match.group(0)
        
        return None
    
    def parse_deadline(self, deadline_text: str) -> Optional[datetime]:
        """Parse deadline text to datetime using config patterns"""
        parsing_rules = self.config.config.get('parsing_rules', {}).get('deadline_patterns', [])
        
        for rule in parsing_rules:
            pattern = rule.get('pattern')
            
            if rule.get('type') == 'regex':
                match = re.search(pattern, deadline_text)
                if match:
                    days = int(match.group(1))
                    return datetime.now() + timedelta(days=days)
            
            elif rule.get('type') == 'date':
                match = re.search(pattern, deadline_text)
                if match:
                    month = int(match.group(1))
                    day = int(match.group(2))
                    year = datetime.now().year
                    if month < datetime.now().month:
                        year += 1
                    return datetime(year, month, day)
            
            elif rule.get('type') == 'always':
                if pattern in deadline_text:
                    return None
            
            elif 'days' in rule:
                if pattern in deadline_text:
                    return datetime.now() + timedelta(days=rule['days'])
        
        return None
    
    def get_job_detail(self, job_url: str) -> Optional[Dict]:
        """Get detailed information for a specific job"""
        self._rate_limit()
        
        try:
            response = self.session.get(job_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser', from_encoding='utf-8')
            
            details = {}
            
            # Job description
            desc_elem = soup.find('div', class_='user_content')
            if desc_elem:
                details['description'] = desc_elem.get_text(strip=True)
            
            # Requirements
            req_elem = soup.find('div', class_='col_require')
            if req_elem:
                requirements = {}
                for dt, dd in zip(req_elem.find_all('dt'), req_elem.find_all('dd')):
                    key = dt.get_text(strip=True)
                    value = dd.get_text(strip=True)
                    requirements[key] = value
                details['requirements'] = requirements
            
            # Benefits
            benefit_elem = soup.find('div', class_='col_benefit')
            if benefit_elem:
                benefits = []
                for span in benefit_elem.find_all('span'):
                    benefit = span.get_text(strip=True)
                    if benefit:
                        benefits.append(benefit)
                details['benefits'] = benefits
            
            return details
            
        except Exception as e:
            logger.error(f"Error getting job detail: {e}")
            return None
    
    def get_ml_jobs(self, max_pages: int = None) -> List[Dict]:
        """Get ML/AI related jobs using config keywords"""
        if max_pages is None:
            max_pages = min(self.MAX_PAGES, 3)
        
        # Get keywords from config
        keywords = self.config.get_primary_keywords()[:3]  # Limit to 3 primary keywords
        
        all_jobs = []
        seen_ids = set()
        
        for keyword in keywords:
            logger.info(f"Searching for '{keyword}'...")
            
            for page in range(1, max_pages + 1):
                jobs = self.search_jobs(keyword, page)
                
                for job in jobs:
                    job_id = job.get('external_id')
                    if job_id and job_id not in seen_ids:
                        seen_ids.add(job_id)
                        
                        # Score job based on config criteria
                        job['relevance_score'] = self.config.score_job(job)
                        
                        # Only add if matches basic criteria
                        if self.config.matches_criteria(job):
                            all_jobs.append(job)
                
                if not jobs:
                    break
                
                time.sleep(1)  # Extra delay between pages
            
            time.sleep(2)  # Extra delay between keywords
        
        # Sort by relevance score
        all_jobs.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        logger.info(f"Found {len(all_jobs)} unique ML/AI jobs matching criteria")
        return all_jobs
    
    def scrape_jobs(self, keywords: List[str] = None, include_details: bool = False) -> List[Dict]:
        """Scrape jobs for multi-source compatibility"""
        return self.get_ml_jobs(max_pages=3)
    
    def parse_to_standard_format(self, raw_job: Dict) -> Dict:
        """Convert Saramin format to standard format"""
        return {
            'source': 'saramin',
            'source_method': 'scraping',
            'external_id': raw_job.get('external_id'),
            'company_name': raw_job.get('company_name'),
            'title': raw_job.get('title'),
            'description': raw_job.get('description'),
            'requirements': raw_job.get('requirements'),
            'benefits': raw_job.get('benefits'),
            'location': raw_job.get('location'),
            'work_type': raw_job.get('work_type'),
            'employment_type': raw_job.get('employment_type'),
            'experience_level': raw_job.get('experience_level'),
            'education_level': raw_job.get('education_level'),
            'url': raw_job.get('url'),
            'tags': raw_job.get('tags', []),
            'deadline': raw_job.get('deadline'),
            'relevance_score': raw_job.get('relevance_score', 0),
            'crawled_at': datetime.now().isoformat()
        }


def main():
    """Test Saramin scraper"""
    scraper = SaraminScraper()
    
    # Test search with primary keyword from config
    config = get_config()
    keywords = config.get_primary_keywords()
    
    if keywords:
        print(f"\n=== Testing Saramin Search with '{keywords[0]}' ===")
        jobs = scraper.search_jobs(keywords[0], page=1)
        print(f"Found {len(jobs)} jobs")
        
        if jobs:
            # Show first job
            first_job = jobs[0]
            print(f"\nFirst job:")
            print(f"  Company: {first_job.get('company_name')}")
            print(f"  Title: {first_job.get('title')}")
            print(f"  Location: {first_job.get('location')}")
            print(f"  Employment: {first_job.get('employment_type')}")
            print(f"  Experience: {first_job.get('experience_level')}")
            print(f"  Work type: {first_job.get('work_type')}")
            print(f"  URL: {first_job.get('url')}")
    
    # Get ML jobs
    print("\n=== Collecting ML Jobs ===")
    ml_jobs = scraper.get_ml_jobs(max_pages=1)
    
    print(f"\nTop 5 jobs by relevance:")
    for i, job in enumerate(ml_jobs[:5], 1):
        print(f"{i}. {job['title']} at {job['company_name']} (Score: {job['relevance_score']:.1f})")
    
    # Save to file
    import json
    output_file = "saramin_jobs.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(ml_jobs, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\nSaved {len(ml_jobs)} jobs to {output_file}")


if __name__ == "__main__":
    main()