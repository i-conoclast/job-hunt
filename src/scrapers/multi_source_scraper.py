#!/usr/bin/env python3
"""
Multi-Source Scraper
여러 채용 사이트에서 데이터를 수집하는 통합 스크래퍼
"""

import asyncio
import concurrent.futures
from typing import List, Dict, Optional, Set
import logging
from datetime import datetime
import json
from pathlib import Path

from src.scrapers.wanted_api_scraper import WantedAPIScraper
from src.scrapers.saramin_scraper import SaraminScraper
from src.scrapers.jobkorea_scraper import JobKoreaScraper
from src.scrapers.programmers_scraper import ProgrammersScraper
from src.scrapers.rocketpunch_scraper import RocketPunchScraper
from src.core.config_loader import get_config
from src.pipeline.deduplication_pipeline import DeduplicationPipeline, DeduplicationConfig
from src.pipeline.database_deduplication import DatabaseAwareDeduplication
from src.core.database import DatabaseManager

logger = logging.getLogger(__name__)


class MultiSourceScraper:
    """Multi-source job scraper that aggregates data from multiple sites"""
    
    def __init__(self):
        self.config = get_config()
        
        # Initialize scrapers
        self.scrapers = {
            'wanted': WantedAPIScraper(),
            'saramin': SaraminScraper(),
            'jobkorea': JobKoreaScraper(),
            'programmers': ProgrammersScraper(),
            'rocketpunch': RocketPunchScraper()
        }
        
        # Available sources (can be configured)
        self.enabled_sources = ['wanted', 'saramin', 'jobkorea', 'programmers', 'rocketpunch']
        
        # Initialize deduplication pipeline with config
        self.deduplication_pipeline = self._create_deduplication_pipeline()
        
        # Initialize database-aware deduplication
        self.database_manager = DatabaseManager()
        self.db_deduplication = DatabaseAwareDeduplication()
        
        # Ensure database tables exist
        self.database_manager.create_tables()
        
    def set_enabled_sources(self, sources: List[str]):
        """Set which sources to use for scraping"""
        available_sources = set(self.scrapers.keys())
        self.enabled_sources = [s for s in sources if s in available_sources]
        logger.info(f"Enabled sources: {self.enabled_sources}")
    
    def scrape_source(self, source: str, keywords: List[str], include_details: bool = False) -> List[Dict]:
        """Scrape jobs from a single source"""
        try:
            if source not in self.scrapers:
                logger.error(f"Unknown source: {source}")
                return []
            
            logger.info(f"Starting scraping from {source}")
            scraper = self.scrapers[source]
            jobs = scraper.scrape_jobs(keywords=keywords, include_details=include_details)
            
            # Add source metadata
            for job in jobs:
                job['source'] = source
                if 'scraped_at' not in job:
                    job['scraped_at'] = datetime.now().isoformat()
            
            logger.info(f"Completed scraping from {source}: {len(jobs)} jobs")
            return jobs
            
        except Exception as e:
            logger.error(f"Error scraping from {source}: {e}")
            return []
    
    def scrape_all_sources(self, keywords: List[str] = None, include_details: bool = False, 
                          max_workers: int = 3) -> Dict[str, List[Dict]]:
        """
        Scrape jobs from all enabled sources concurrently
        
        Args:
            keywords: Search keywords
            include_details: Whether to fetch detailed job information
            max_workers: Maximum number of concurrent workers
            
        Returns:
            Dictionary mapping source names to job lists
        """
        if keywords is None:
            # Use keywords from config
            keywords = self.config.get_search_keywords('primary')
            keywords.extend(self.config.get_search_keywords('secondary')[:3])  # Limit for testing
        
        logger.info(f"Starting multi-source scraping with {len(self.enabled_sources)} sources")
        logger.info(f"Keywords: {keywords}")
        
        results = {}
        
        # Use ThreadPoolExecutor for concurrent scraping
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit scraping tasks
            future_to_source = {
                executor.submit(self.scrape_source, source, keywords, include_details): source
                for source in self.enabled_sources
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    jobs = future.result(timeout=300)  # 5 minute timeout per source
                    results[source] = jobs
                    logger.info(f"✓ {source}: {len(jobs)} jobs")
                except Exception as e:
                    logger.error(f"✗ {source} failed: {e}")
                    results[source] = []
        
        return results
    
    def merge_and_deduplicate(self, source_results: Dict[str, List[Dict]]) -> List[Dict]:
        """
        Merge results from all sources and remove duplicates using database-aware deduplication
        
        Args:
            source_results: Dictionary mapping source names to job lists
            
        Returns:
            Deduplicated list of new jobs not already in database
        """
        all_new_jobs = []
        
        # Process each source with database-aware deduplication
        for source, jobs in source_results.items():
            if not jobs:
                continue
                
            logger.info(f"Processing {len(jobs)} jobs from {source}")
            
            # Filter out jobs already in database
            new_jobs, db_stats = self.db_deduplication.filter_new_jobs(jobs, source)
            
            # Save new jobs to database
            saved_count = self.db_deduplication.save_jobs_to_database(new_jobs, source)
            
            # Log collection run
            self.db_deduplication.log_collection_run(source, db_stats)
            
            all_new_jobs.extend(new_jobs)
            
            logger.info(f"Source {source}: {db_stats.total_scraped_jobs} scraped -> "
                       f"{db_stats.new_jobs} new -> {saved_count} saved")
        
        logger.info(f"Total new jobs across all sources: {len(all_new_jobs)}")
        
        # Apply additional memory-based deduplication across sources
        if all_new_jobs:
            final_unique_jobs, dedup_stats = self.deduplication_pipeline.deduplicate(all_new_jobs)
            logger.info(f"Final deduplication: {len(all_new_jobs)} -> {len(final_unique_jobs)}")
            return final_unique_jobs
        
        return all_new_jobs
    
    def _create_deduplication_pipeline(self) -> DeduplicationPipeline:
        """Create deduplication pipeline from config"""
        try:
            dedup_config_data = self.config.config.get('deduplication', {})
            
            # Create deduplication config from pipeline config
            dedup_config = DeduplicationConfig(
                title_similarity_threshold=dedup_config_data.get('title_similarity_threshold', 0.85),
                company_similarity_threshold=dedup_config_data.get('company_similarity_threshold', 0.90),
                combined_similarity_threshold=dedup_config_data.get('combined_similarity_threshold', 0.80),
                title_weight=dedup_config_data.get('title_weight', 0.6),
                company_weight=dedup_config_data.get('company_weight', 0.3),
                location_weight=dedup_config_data.get('location_weight', 0.1),
                source_priority=dedup_config_data.get('source_priority', {}),
                comparison_fields=dedup_config_data.get('comparison_fields', ['title', 'company_name', 'location']),
                enable_fuzzy_matching=dedup_config_data.get('enable_fuzzy_matching', True),
                enable_url_matching=dedup_config_data.get('enable_url_matching', True),
                enable_id_matching=dedup_config_data.get('enable_id_matching', True),
                preserve_most_detailed=dedup_config_data.get('preserve_most_detailed', True)
            )
            
            logger.info("Initialized deduplication pipeline with config")
            return DeduplicationPipeline(dedup_config)
            
        except Exception as e:
            logger.warning(f"Failed to load deduplication config: {e}. Using defaults.")
            return DeduplicationPipeline()
    
    def save_results(self, jobs: List[Dict], output_path: str = None) -> str:
        """Save scraping results to file"""
        if output_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"data/multi_source_jobs_{timestamp}.json"
        
        # Ensure directory exists
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Prepare metadata
        results = {
            'metadata': {
                'scraped_at': datetime.now().isoformat(),
                'total_jobs': len(jobs),
                'sources_used': self.enabled_sources,
                'deduplication_applied': True
            },
            'jobs': jobs
        }
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Results saved to {output_file}")
        return str(output_file)
    
    def get_source_statistics(self, source_results: Dict[str, List[Dict]]) -> Dict:
        """Get statistics about scraping results by source"""
        stats = {
            'total_jobs': sum(len(jobs) for jobs in source_results.values()),
            'by_source': {},
            'top_companies': {},
            'top_locations': {}
        }
        
        all_companies = []
        all_locations = []
        
        for source, jobs in source_results.items():
            stats['by_source'][source] = {
                'job_count': len(jobs),
                'companies': len(set(job.get('company_name', '') for job in jobs)),
                'avg_description_length': sum(len(job.get('description', '')) for job in jobs) / max(len(jobs), 1)
            }
            
            # Collect companies and locations for overall stats
            all_companies.extend([job.get('company_name', '') for job in jobs if job.get('company_name')])
            all_locations.extend([job.get('location', '') for job in jobs if job.get('location')])
        
        # Count top companies and locations
        from collections import Counter
        
        company_counts = Counter(all_companies)
        location_counts = Counter(all_locations)
        
        stats['top_companies'] = dict(company_counts.most_common(10))
        stats['top_locations'] = dict(location_counts.most_common(10))
        
        return stats
    
    def scrape_and_save(self, keywords: List[str] = None, include_details: bool = False,
                       output_path: str = None, sources: List[str] = None) -> str:
        """
        Complete scraping workflow: scrape, deduplicate, and save
        
        Args:
            keywords: Search keywords
            include_details: Whether to fetch detailed job information
            output_path: Output file path
            sources: List of sources to use (None for all enabled)
            
        Returns:
            Path to saved results file
        """
        if sources:
            self.set_enabled_sources(sources)
        
        # Scrape from all sources
        source_results = self.scrape_all_sources(keywords, include_details)
        
        # Log statistics
        stats = self.get_source_statistics(source_results)
        logger.info(f"Scraping statistics: {stats}")
        
        # Merge and deduplicate
        unique_jobs = self.merge_and_deduplicate(source_results)
        
        # Save results
        output_file = self.save_results(unique_jobs, output_path)
        
        logger.info(f"Multi-source scraping completed successfully!")
        logger.info(f"Total unique jobs: {len(unique_jobs)}")
        logger.info(f"Results saved to: {output_file}")
        
        return output_file


def main():
    """Test the multi-source scraper"""
    scraper = MultiSourceScraper()
    
    # Test with a subset of sources and keywords
    test_sources = ['wanted', 'saramin']  # Start with working sources
    test_keywords = ['머신러닝', 'AI']
    
    scraper.set_enabled_sources(test_sources)
    
    output_file = scraper.scrape_and_save(
        keywords=test_keywords,
        include_details=False,
        sources=test_sources
    )
    
    print(f"Test completed. Results saved to: {output_file}")


if __name__ == "__main__":
    main()