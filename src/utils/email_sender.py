"""이메일 발송 모듈.

수집된 공고 결과를 HTML 이메일로 발송한다.
NormalizedJob (scored) 리스트를 받아 상위 결과를 포맷팅.
"""

import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from dotenv import load_dotenv

from ..core.job_normalizer import NormalizedJob


class EmailSender:
    """공고 수집 결과 이메일 발송."""

    def __init__(self) -> None:
        load_dotenv()
        self.smtp_server = os.getenv("SMTP_SERVER") or "smtp.gmail.com"
        self.smtp_port = int(os.getenv("SMTP_PORT") or "587")
        self.email_user = os.getenv("EMAIL_USER", "")
        self.email_password = os.getenv("EMAIL_PASSWORD", "")
        self.recipients = [
            r.strip()
            for r in os.getenv("EMAIL_RECIPIENTS", "").split(",")
            if r.strip()
        ]

    def send_digest(
        self,
        jobs: list[NormalizedJob],
        stats: Optional[dict] = None,
    ) -> bool:
        """상위 공고 결과를 이메일로 발송.

        Args:
            jobs: 점수순 정렬된 NormalizedJob 리스트.
            stats: 파이프라인 통계 (collected, shortlist, consider 등).

        Returns:
            발송 성공 여부.
        """
        if not all([self.email_user, self.email_password, self.recipients]):
            print("Email config incomplete (EMAIL_USER/EMAIL_PASSWORD/EMAIL_RECIPIENTS)")
            return False

        stats = stats or {}
        date_str = datetime.now().strftime("%Y-%m-%d")
        subject = f"Job Digest - {date_str} ({len(jobs)} opportunities)"

        html = self._build_html(jobs, stats, date_str)

        msg = MIMEMultipart()
        msg["From"] = self.email_user
        msg["To"] = ", ".join(self.recipients)
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html", "utf-8"))

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                server.send_message(msg)
            print(f"Email sent to {len(self.recipients)} recipients")
            return True
        except Exception as e:
            print(f"Email send failed: {e}")
            return False

    def _build_html(
        self,
        jobs: list[NormalizedJob],
        stats: dict,
        date_str: str,
    ) -> str:
        """HTML 이메일 본문 생성."""
        rows = []
        for i, job in enumerate(jobs, 1):
            status_color = (
                "#22c55e" if job.status == "shortlist"
                else "#eab308" if job.status == "consider"
                else "#94a3b8"
            )
            tech = ", ".join(job.tech_stack[:5])
            flags = (
                f'<br><span style="color:#ef4444;font-size:12px">'
                f'{"".join(job.red_flags)}</span>'
                if job.red_flags else ""
            )
            rows.append(f"""
            <tr>
              <td style="padding:8px;border-bottom:1px solid #eee;text-align:center">{i}</td>
              <td style="padding:8px;border-bottom:1px solid #eee">
                <span style="display:inline-block;width:8px;height:8px;
                  border-radius:50%;background:{status_color};margin-right:6px"></span>
                <strong>{job.company}</strong> — {job.role_title}
              </td>
              <td style="padding:8px;border-bottom:1px solid #eee;text-align:center">
                {job.priority_score:.0f}
              </td>
              <td style="padding:8px;border-bottom:1px solid #eee">
                {job.location} / {job.work_type}
              </td>
              <td style="padding:8px;border-bottom:1px solid #eee;font-size:13px">
                {tech}{flags}
              </td>
              <td style="padding:8px;border-bottom:1px solid #eee">
                <a href="{job.source_url}" style="color:#2563eb">Link</a>
              </td>
            </tr>""")

        job_rows = "".join(rows) if rows else (
            '<tr><td colspan="6" style="padding:20px;text-align:center">'
            'No matching jobs found</td></tr>'
        )

        collected = stats.get("collected", "?")
        shortlist = stats.get("shortlist", "?")
        consider = stats.get("consider", "?")

        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,sans-serif;max-width:900px;margin:0 auto;padding:20px">
  <h2 style="color:#1e293b">Job Digest — {date_str}</h2>
  <p style="color:#64748b">
    Collected: <strong>{collected}</strong> |
    Shortlist: <strong>{shortlist}</strong> |
    Consider: <strong>{consider}</strong>
  </p>
  <table style="width:100%;border-collapse:collapse;font-size:14px">
    <thead>
      <tr style="background:#f8fafc">
        <th style="padding:10px;text-align:center">#</th>
        <th style="padding:10px;text-align:left">Company — Position</th>
        <th style="padding:10px;text-align:center">Score</th>
        <th style="padding:10px">Location</th>
        <th style="padding:10px">Tech Stack</th>
        <th style="padding:10px">Link</th>
      </tr>
    </thead>
    <tbody>
      {job_rows}
    </tbody>
  </table>
  <p style="color:#94a3b8;font-size:12px;margin-top:20px">
    Generated by job-hunt daily digest
  </p>
</body></html>"""
