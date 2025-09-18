#!/usr/bin/env python3
"""
Email sender for job application pipeline results
Similar to weekly KPI email system
"""

import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Dict, List, Optional
import yaml
from dataclasses import asdict
from dotenv import load_dotenv

from ..pipeline.job_application_pipeline import JobPosting


class JobApplicationEmailSender:
    """Send job application pipeline results via email"""
    
    def __init__(self, config_path: Optional[str] = None):
        # Load environment variables
        load_dotenv()
        
        self.config = self._load_email_config(config_path)
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.email_user = os.getenv('EMAIL_USER')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.email_recipients = os.getenv('EMAIL_RECIPIENTS', '').split(',')
        
    def _load_email_config(self, config_path: Optional[str]) -> Dict:
        """Load email configuration"""
        if config_path and Path(config_path).exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config.get('email', {})
        
        return {
            'enabled': True,
            'subject_template': "🎯 Job Application Results - {date} ({total_jobs} opportunities)"
        }
    
    def send_pipeline_results(self, final_jobs: List[JobPosting], pipeline_stats: Dict) -> bool:
        """Send pipeline results email"""
        
        if not self.config.get('enabled', False):
            print("📧 Email notification disabled in config")
            return False
            
        if not all([self.email_user, self.email_password, self.email_recipients[0]]):
            print("❌ Email configuration incomplete. Missing EMAIL_USER, EMAIL_PASSWORD, or EMAIL_RECIPIENTS")
            return False
        
        try:
            # Generate email content
            email_content = self._generate_email_content(final_jobs, pipeline_stats)
            
            # Create email
            msg = MIMEMultipart()
            msg['From'] = self.email_user
            msg['To'] = ', '.join(self.email_recipients)
            
            # Generate subject
            total_jobs = len(final_jobs)
            date_str = datetime.now().strftime("%Y-%m-%d")
            subject = self.config['subject_template'].format(
                date=date_str,
                total_jobs=total_jobs
            )
            msg['Subject'] = subject
            
            # Add content
            html_content = self._generate_html_email_content(final_jobs, pipeline_stats)
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                server.send_message(msg)
            
            print(f"✅ Job application results email sent to {len(self.email_recipients)} recipients")
            print(f"📧 Subject: {subject}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send email: {e}")
            return False
    
    def _generate_email_content(self, final_jobs: List[JobPosting], pipeline_stats: Dict) -> str:
        """Generate email content from template"""
        
        # Calculate filtered counts
        stage1_filtered = pipeline_stats['stage1_collected'] - pipeline_stats['stage1_passed']
        stage2_filtered = pipeline_stats['stage1_passed'] - pipeline_stats['stage2_passed']  
        stage3_filtered = pipeline_stats['stage2_passed'] - pipeline_stats['stage3_processed']
        stage4_filtered = pipeline_stats['stage3_processed'] - pipeline_stats['stage4_analyzed']
        
        # Generate job details
        job_details = self._generate_job_details(final_jobs)
        
        # Count priorities
        high_priority_count = sum(1 for job in final_jobs 
                                 if job.stage4_analysis and job.stage4_analysis.get('application_priority') == 'high')
        medium_priority_count = len(final_jobs) - high_priority_count
        
        # Format template
        template_vars = {
            'date': datetime.now().strftime("%Y-%m-%d %H:%M KST"),
            'cost': pipeline_stats.get('cost_estimate', 0),
            'stage1_collected': pipeline_stats['stage1_collected'],
            'stage1_passed': pipeline_stats['stage1_passed'],
            'stage1_filtered': stage1_filtered,
            'stage2_passed': pipeline_stats['stage2_passed'],
            'stage2_filtered': stage2_filtered,
            'stage3_processed': pipeline_stats['stage3_processed'],
            'stage3_filtered': stage3_filtered,
            'stage4_analyzed': pipeline_stats['stage4_analyzed'],
            'stage4_filtered': stage4_filtered,
            'job_details': job_details,
            'high_priority_count': high_priority_count,
            'medium_priority_count': medium_priority_count,
            'total_jobs': len(final_jobs)
        }
        
        # Use template from config or default
        template = self.config.get('email_template', self._get_default_template())
        
        return template.format(**template_vars)
    
    def _generate_html_email_content(self, final_jobs: List[JobPosting], pipeline_stats: Dict) -> str:
        """Generate HTML email content using template file"""
        
        # Load HTML template
        template_path = Path(__file__).parent.parent.parent / "templates" / "email_template.html"
        if not template_path.exists():
            print(f"⚠️ Template not found at {template_path}, using fallback")
            return self._generate_fallback_html_content(final_jobs, pipeline_stats)
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
        
        # Sort jobs by score
        sorted_jobs = sorted(final_jobs, key=lambda x: x.stage3_score or 0, reverse=True)
        
        # Calculate stats
        total_jobs = len(final_jobs)
        avg_score = sum(job.stage3_score or 0 for job in final_jobs) / total_jobs if total_jobs > 0 else 0
        max_score = max(job.stage3_score or 0 for job in final_jobs) if final_jobs else 0
        
        # Count priorities
        high_priority_count = sum(1 for job in final_jobs 
                                 if job.stage4_analysis and job.stage4_analysis.get('application_priority') == 'high')
        medium_priority_count = len(final_jobs) - high_priority_count
        
        # Generate job rows
        job_rows = []
        for i, job in enumerate(sorted_jobs[:10], 1):  # Top 10 jobs
            analysis = job.stage4_analysis or {}
            priority = analysis.get('application_priority', 'medium')
            priority_emoji = "🔥" if priority == 'high' else "📌"
            
            score = job.stage3_score or 0
            stars = '⭐' * min(int(round(score)), 10)  # Max 10 stars
            
            strengths = analysis.get('key_strengths', [])
            strength_list = ''.join(f"<li>{strength}</li>" for strength in strengths[:3])
            
            # Handle company name if it's a dict
            company_name = job.company
            if isinstance(company_name, dict):
                company_name = company_name.get('name', 'Unknown Company')
            
            job_row = f"""
            <tr>
                <td style="text-align: center; padding: 12px; border-bottom: 1px solid #eee;">
                    {i}
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #eee;">
                    {priority_emoji} <a href="{job.url}" style="color: #0066cc; text-decoration: none; font-weight: bold;" target="_blank">{job.title}</a><br>
                    <span style="color: #666; font-size: 14px;">{company_name}</span>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: center;">
                    {score:.1f}/10<br>
                    <span style="font-size: 14px;">{stars}</span>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #eee;">
                    <div style="font-size: 12px; color: #666;">
                        Priority: {priority.upper()}<br>
                        Employment: {job.employment_type}<br>
                        Experience: {job.experience_level}<br>
                        Skills: {len(job.skills)} found
                    </div>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #eee;">
                    {job.location or 'N/A'}<br>
                    <span style="color: #666; font-size: 14px;">{job.salary or '급여 비공개'}</span>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #eee;">
                    <ul style="margin: 0; padding-left: 20px; font-size: 14px;">
                        {strength_list}
                    </ul>
                </td>
            </tr>
            """
            job_rows.append(job_row)
        
        job_rows_html = ''.join(job_rows)
        
        # Calculate filtered counts
        stage1_filtered = pipeline_stats['stage1_collected'] - pipeline_stats['stage1_passed']
        stage2_filtered = pipeline_stats['stage1_passed'] - pipeline_stats['stage2_passed']  
        stage3_filtered = pipeline_stats['stage2_passed'] - pipeline_stats['stage3_processed']
        stage4_filtered = pipeline_stats['stage3_processed'] - pipeline_stats['stage4_analyzed']
        
        date_str = datetime.now().strftime("%Y년 %m월 %d일")
        
        # Format template with data
        return template.format(
            date_str=date_str,
            cost_estimate=pipeline_stats.get('cost_estimate', 0),
            stage1_collected=pipeline_stats['stage1_collected'],
            stage1_passed=pipeline_stats['stage1_passed'],
            stage1_filtered=stage1_filtered,
            stage2_passed=pipeline_stats['stage2_passed'],
            stage2_filtered=stage2_filtered,
            stage3_processed=pipeline_stats['stage3_processed'],
            stage3_filtered=stage3_filtered,
            stage4_analyzed=pipeline_stats['stage4_analyzed'],
            stage4_filtered=stage4_filtered,
            total_jobs=total_jobs,
            avg_score=avg_score,
            max_score=max_score,
            high_priority_count=high_priority_count,
            medium_priority_count=medium_priority_count,
            job_rows_html=job_rows_html
        )
    
    def _generate_fallback_html_content(self, final_jobs: List[JobPosting], pipeline_stats: Dict) -> str:
        """Fallback HTML content if template file is not found"""
        return f"""
        <html><body>
        <h1>Job Application Pipeline Results</h1>
        <p>Found {len(final_jobs)} jobs with average score: {sum(job.stage3_score or 0 for job in final_jobs) / len(final_jobs) if final_jobs else 0:.1f}/10</p>
        <p>Template file not found. Please check templates/email_template.html</p>
        </body></html>
        """
    
    def _generate_job_details(self, final_jobs: List[JobPosting]) -> str:
        """Generate detailed job listings for email"""
        
        if not final_jobs:
            return "No high-scoring jobs found in this run."
        
        details = []
        
        for i, job in enumerate(final_jobs, 1):
            analysis = job.stage4_analysis or {}
            priority = analysis.get('application_priority', 'medium')
            priority_emoji = "🔥" if priority == 'high' else "📌"
            
            # Generate star rating (quick-job-finder style)
            score = job.stage3_score or 0
            stars = '⭐' * int(round(score))
            
            strengths = analysis.get('key_strengths', analysis.get('strengths', []))
            strength_text = ", ".join(strengths[:2]) if strengths else "Good match"
            
            # Handle company name if it's a dict
            company_name = job.company
            if isinstance(company_name, dict):
                company_name = company_name.get('name', 'Unknown Company')
            
            job_detail = f"""
{i}. {priority_emoji} **{job.title}** at **{company_name}**
   Score: {score:.1f}/10 {stars}
   Priority: {priority.upper()} | Location: {job.location}
   Strengths: {strength_text}
   Apply: {job.url}
"""
            details.append(job_detail.strip())
        
        return "\n\n".join(details)
    
    def _get_default_template(self) -> str:
        """Default email template"""
        return """🎯 Job Application Pipeline Results

Pipeline Run: {date}
Total Cost: ₩{cost:.0f}

📊 Pipeline Stats
- Collected: {stage1_collected} jobs
- Basic Filter: {stage1_passed} jobs (-{stage1_filtered})
- Advanced Filter: {stage2_passed} jobs (-{stage2_filtered})
- LLM Scored: {stage3_processed} jobs (-{stage3_filtered})
- Final Analysis: {stage4_analyzed} jobs (-{stage4_filtered})

⭐ Top Job Opportunities

{job_details}

📋 Action Items
- High Priority: {high_priority_count} applications
- Medium Priority: {medium_priority_count} applications
- Custom Cover Letters: {total_jobs} needed

---
Generated by Career Transition Automation System"""


def main():
    """Test email functionality"""
    # Create test data
    from ..pipeline.job_application_pipeline import JobPosting
    
    test_job = JobPosting(
        id="test-1",
        title="AI Engineer",
        company="Test Company",
        url="https://example.com",
        description="Test description",
        requirements="Python, ML",
        location="서울",
        employment_type="정규직",
        experience_level="3년",
        skills=["Python", "AI"],
        source="test"
    )
    test_job.stage3_score = 85.0
    test_job.stage4_analysis = {
        "application_priority": "high",
        "key_strengths": ["AI focus", "Good salary", "Remote work"]
    }
    
    test_stats = {
        'stage1_collected': 100,
        'stage1_passed': 50,
        'stage2_passed': 25,
        'stage3_processed': 15,
        'stage4_analyzed': 5,
        'cost_estimate': 3500
    }
    
    sender = JobApplicationEmailSender()
    success = sender.send_pipeline_results([test_job], test_stats)
    
    if success:
        print("✅ Test email sent successfully")
    else:
        print("❌ Test email failed")


if __name__ == "__main__":
    main()