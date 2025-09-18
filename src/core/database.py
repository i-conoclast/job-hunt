#!/usr/bin/env python3
"""
Database setup and models for TCIS
PostgreSQL with pgvector extension for embeddings
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import hashlib

from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, JSON, UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

# Use JSON instead of JSONB for SQLite compatibility
try:
    from sqlalchemy.dialects.postgresql import JSONB
except ImportError:
    JSONB = JSON

# Handle ARRAY type for SQLite
try:
    from sqlalchemy.dialects.postgresql import ARRAY
except ImportError:
    from sqlalchemy import Text as ARRAY

Base = declarative_base()


class JobPosting(Base):
    """Job posting model with vector embeddings"""
    __tablename__ = 'job_postings'
    
    # Primary identifiers
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(50), nullable=False)  # wanted, saramin, jobkorea
    source_method = Column(String(20), nullable=False)  # api, scraping, rss
    external_id = Column(String(255), nullable=False)
    
    # Basic information
    company_name = Column(String(255))
    title = Column(String(500), nullable=False)
    description = Column(Text)
    
    # Structured data
    requirements = Column(JSON)  # {"required": [...], "preferred": [...]}
    benefits = Column(JSON)
    salary_range = Column(JSON)  # {"min": 50000000, "max": 70000000, "currency": "KRW"}
    
    # Location and work style
    location = Column(String(255))
    work_type = Column(String(50))  # remote, hybrid, office
    employment_type = Column(String(50))  # full-time, contract, internship
    
    # Experience and dates
    experience_range = Column(JSON)  # [3, 5] means 3-5 years - using JSON for SQLite compatibility
    posted_date = Column(DateTime)
    deadline = Column(DateTime)
    
    # URLs and tags
    url = Column(String(500))
    tags = Column(JSON)  # Using JSON for SQLite compatibility
    
    # ML features (will be added later)
    # embedding = Column(Vector(768))  # Requires pgvector extension
    
    # Raw data storage
    api_response = Column(JSON)  # Store raw API/scraped data
    
    # Metadata
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Deduplication hash
    content_hash = Column(String(64))  # SHA256 hash of key fields
    
    # Constraints and Performance Indexes
    __table_args__ = (
        UniqueConstraint('source', 'external_id', name='uq_source_external_id'),
        Index('ix_company_name', 'company_name'),
        Index('ix_posted_date', 'posted_date'),
        Index('ix_content_hash', 'content_hash'),
        # Composite indexes for performance
        Index('ix_source_external_id_composite', 'source', 'external_id'),
        Index('ix_content_hash_source', 'content_hash', 'source'),
        Index('ix_created_at_source', 'created_at', 'source'),
        Index('ix_company_title_composite', 'company_name', 'title'),
    )
    
    def calculate_content_hash(self) -> str:
        """Calculate hash for deduplication"""
        key_fields = {
            'company': self.company_name,
            'title': self.title,
            'location': self.location,
            'description': self.description[:500] if self.description else ''
        }
        content = json.dumps(key_fields, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


class APIEndpoint(Base):
    """Track discovered API endpoints"""
    __tablename__ = 'api_endpoints'
    
    id = Column(Integer, primary_key=True)
    site_name = Column(String(50), nullable=False)
    endpoint_url = Column(Text, nullable=False)
    method = Column(String(10), default='GET')
    headers = Column(JSON)
    params = Column(JSON)
    discovered_at = Column(DateTime, default=func.now())
    last_used = Column(DateTime)
    success_rate = Column(Float)
    is_active = Column(Integer, default=1)  # SQLite doesn't have boolean
    notes = Column(Text)


class CollectionLog(Base):
    """Track data collection runs"""
    __tablename__ = 'collection_logs'
    
    id = Column(Integer, primary_key=True)
    source = Column(String(50), nullable=False)
    start_time = Column(DateTime, default=func.now())
    end_time = Column(DateTime)
    jobs_collected = Column(Integer, default=0)
    jobs_new = Column(Integer, default=0)
    jobs_updated = Column(Integer, default=0)
    errors = Column(JSON)
    status = Column(String(20))  # running, completed, failed


@dataclass
class JobData:
    """Data class for job postings"""
    source: str
    source_method: str
    external_id: str
    company_name: str
    title: str
    description: str = None
    requirements: Dict = None
    benefits: Dict = None
    salary_range: Dict = None
    location: str = None
    work_type: str = None
    employment_type: str = None
    experience_range: List[int] = None
    posted_date: datetime = None
    deadline: datetime = None
    url: str = None
    tags: List[str] = None
    api_response: Dict = None
    
    def to_db_model(self) -> JobPosting:
        """Convert to database model"""
        job = JobPosting(**asdict(self))
        job.content_hash = job.calculate_content_hash()
        return job


class DatabaseManager:
    """Database connection and operations manager"""
    
    def __init__(self, connection_string: str = None):
        """
        Initialize database connection
        
        Args:
            connection_string: PostgreSQL connection string
                             If None, uses DATABASE_URL env var or SQLite fallback
        """
        if connection_string:
            self.connection_string = connection_string
        else:
            # Try environment variable
            self.connection_string = os.getenv('DATABASE_URL')
            
            if not self.connection_string:
                # Fallback to SQLite in project data directory
                from pathlib import Path
                data_dir = Path(__file__).parent.parent.parent / "data"
                data_dir.mkdir(exist_ok=True)
                db_file = data_dir / 'tcis_jobs.db'
                self.connection_string = f'sqlite:///{db_file}'
                print(f"Using SQLite database at {db_file}")
        
        # Optimized engine with connection pooling
        if 'sqlite' in self.connection_string.lower():
            # SQLite-specific optimizations
            self.engine = create_engine(
                self.connection_string,
                pool_pre_ping=True,
                connect_args={"check_same_thread": False}
            )
        else:
            # PostgreSQL-specific optimizations  
            self.engine = create_engine(
                self.connection_string,
                pool_size=20,              # Number of connections to maintain
                max_overflow=30,           # Additional connections on demand
                pool_pre_ping=True,        # Validate connections before use
                pool_recycle=3600,         # Recycle connections every hour
                echo=False                 # Set to True for SQL debugging
            )
        
        self.SessionLocal = sessionmaker(bind=self.engine)
        
    def create_tables(self):
        """Create all database tables"""
        Base.metadata.create_all(self.engine)
        print("Database tables created successfully")
    
    def get_session(self) -> Session:
        """Get database session"""
        return self.SessionLocal()
    
    def insert_job(self, job_data: JobData) -> bool:
        """
        Insert or update a job posting
        
        Args:
            job_data: JobData object
        
        Returns:
            True if inserted/updated, False if duplicate
        """
        session = self.get_session()
        try:
            job = job_data.to_db_model()
            
            # Check for existing job
            existing = session.query(JobPosting).filter_by(
                source=job.source,
                external_id=job.external_id
            ).first()
            
            if existing:
                # Update if content changed
                if existing.content_hash != job.content_hash:
                    for key, value in asdict(job_data).items():
                        if value is not None:
                            setattr(existing, key, value)
                    existing.content_hash = job.content_hash
                    existing.updated_at = datetime.now()
                    session.commit()
                    return True
                return False
            else:
                # Insert new job
                session.add(job)
                session.commit()
                return True
                
        except Exception as e:
            session.rollback()
            print(f"Error inserting job: {e}")
            return False
        finally:
            session.close()
    
    def bulk_insert_jobs(self, jobs: List[JobData]) -> Dict[str, int]:
        """
        DEPRECATED: Use bulk_insert_jobs_optimized for better performance
        
        Args:
            jobs: List of JobData objects
        
        Returns:
            Dictionary with counts
        """
        print("Warning: Using deprecated bulk_insert_jobs. Use bulk_insert_jobs_optimized instead.")
        return self.bulk_insert_jobs_optimized(jobs)
    
    def bulk_insert_jobs_optimized(self, jobs: List[JobData]) -> Dict[str, int]:
        """
        Optimized bulk insert with batch processing and efficient duplicate detection
        
        Performance improvements:
        - Single database session for all operations
        - Batch check for existing jobs using IN clause
        - SQLAlchemy bulk operations for new inserts
        - Optimized update operations
        
        Args:
            jobs: List of JobData objects
        
        Returns:
            Dictionary with counts: {'new': int, 'updated': int, 'skipped': int, 'errors': int}
        """
        if not jobs:
            return {'new': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
            
        stats = {'new': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        session = self.get_session()
        
        try:
            # Step 1: Prepare job data with content hashes
            job_models = []
            source_external_pairs = []
            content_hash_map = {}
            
            for job_data in jobs:
                try:
                    job_model = job_data.to_db_model()
                    job_models.append(job_model)
                    source_external_pairs.append((job_model.source, job_model.external_id))
                    content_hash_map[(job_model.source, job_model.external_id)] = job_model
                except Exception as e:
                    print(f"Error preparing job data: {e}")
                    stats['errors'] += 1
            
            if not job_models:
                return stats
            
            # Step 2: Batch check for existing jobs using efficient IN query
            from sqlalchemy import tuple_
            existing_jobs = session.query(
                JobPosting.source, 
                JobPosting.external_id, 
                JobPosting.content_hash,
                JobPosting.id
            ).filter(
                tuple_(JobPosting.source, JobPosting.external_id).in_(source_external_pairs)
            ).all()
            
            # Create lookup dictionaries for O(1) access
            existing_lookup = {(job.source, job.external_id): job for job in existing_jobs}
            
            # Step 3: Separate new jobs from existing ones
            new_jobs = []
            jobs_to_update = []
            
            for job_model in job_models:
                key = (job_model.source, job_model.external_id)
                existing = existing_lookup.get(key)
                
                if existing:
                    # Check if content changed
                    if existing.content_hash != job_model.content_hash:
                        jobs_to_update.append((existing.id, job_model))
                    else:
                        stats['skipped'] += 1
                else:
                    new_jobs.append(job_model)
            
            # Step 4: Bulk insert new jobs
            if new_jobs:
                try:
                    # Convert to dictionaries for bulk_insert_mappings
                    job_dicts = []
                    for job in new_jobs:
                        job_dict = {c.name: getattr(job, c.name) for c in job.__table__.columns}
                        # Ensure we have UUIDs
                        if job_dict['id'] is None:
                            job_dict['id'] = uuid.uuid4()
                        job_dicts.append(job_dict)
                    
                    session.bulk_insert_mappings(JobPosting, job_dicts)
                    stats['new'] = len(new_jobs)
                except Exception as e:
                    print(f"Error in bulk insert: {e}")
                    stats['errors'] += len(new_jobs)
            
            # Step 5: Batch update existing jobs
            if jobs_to_update:
                try:
                    update_mappings = []
                    for existing_id, job_model in jobs_to_update:
                        update_dict = {c.name: getattr(job_model, c.name) for c in job_model.__table__.columns}
                        update_dict['id'] = existing_id  # Keep existing ID
                        update_dict['updated_at'] = datetime.now()
                        update_mappings.append(update_dict)
                    
                    session.bulk_update_mappings(JobPosting, update_mappings)
                    stats['updated'] = len(jobs_to_update)
                except Exception as e:
                    print(f"Error in bulk update: {e}")
                    stats['errors'] += len(jobs_to_update)
            
            # Commit all operations
            session.commit()
            
        except Exception as e:
            session.rollback()
            print(f"Error in bulk_insert_jobs_optimized: {e}")
            stats['errors'] = len(jobs)
        finally:
            session.close()
        
        return stats
    
    def find_duplicates(self, company: str, title: str) -> List[JobPosting]:
        """Find potential duplicate jobs"""
        session = self.get_session()
        try:
            # Simple duplicate detection by company and title
            duplicates = session.query(JobPosting).filter(
                JobPosting.company_name == company,
                JobPosting.title.ilike(f'%{title[:30]}%')
            ).all()
            return duplicates
        finally:
            session.close()
    
    def get_recent_jobs(self, limit: int = 100, source: str = None) -> List[JobPosting]:
        """Get recent job postings"""
        session = self.get_session()
        try:
            query = session.query(JobPosting)
            if source:
                query = query.filter_by(source=source)
            return query.order_by(JobPosting.created_at.desc()).limit(limit).all()
        finally:
            session.close()
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        session = self.get_session()
        try:
            total = session.query(JobPosting).count()
            by_source = {}
            for source in ['wanted', 'saramin', 'jobkorea']:
                count = session.query(JobPosting).filter_by(source=source).count()
                by_source[source] = count
            
            return {
                'total_jobs': total,
                'by_source': by_source,
                'unique_companies': session.query(JobPosting.company_name).distinct().count(),
                'last_updated': session.query(func.max(JobPosting.created_at)).scalar()
            }
        finally:
            session.close()


def get_session_factory():
    """Get database session factory for dependency injection"""
    db = DatabaseManager()
    return db.SessionLocal


def main():
    """Test database setup"""
    # Initialize database
    db = DatabaseManager()
    
    # Create tables
    db.create_tables()
    
    # Test with sample data
    sample_job = JobData(
        source='wanted',
        source_method='api',
        external_id='test_123',
        company_name='Test Company',
        title='ML Engineer',
        description='Build ML systems',
        location='Seoul',
        tags=['Python', 'PyTorch', 'MLOps']
    )
    
    # Insert job
    result = db.insert_job(sample_job)
    print(f"Job inserted: {result}")
    
    # Get stats
    stats = db.get_stats()
    print(f"Database stats: {stats}")


if __name__ == "__main__":
    main()