import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict
import logging
from sqlalchemy.orm import Session
from app import models
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailSender:
    """Email sender for job alerts"""
    
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.email_address = os.getenv("EMAIL_ADDRESS")
        self.email_password = os.getenv("EMAIL_APP_PASSWORD")
        
        if not self.email_address or not self.email_password:
            logger.warning("Email credentials not set. Email sending will be disabled.")
    
    def send_job_alert(self, to_email: str, user_name: str, jobs: List[Dict]) -> bool:
        """Send job alert email to user"""
        if not self.email_address or not self.email_password:
            logger.warning("Email credentials not configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_address
            msg['To'] = to_email
            msg['Subject'] = f"SmartApply: {len(jobs)} New Job Matches Found!"
            
            # Create HTML body
            html_body = self._create_email_html(user_name, jobs)
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_address, self.email_password)
                server.send_message(msg)
            
            logger.info(f"Sent job alert to {to_email} with {len(jobs)} jobs")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            return False
    
    def _create_email_html(self, user_name: str, jobs: List[Dict]) -> str:
        """Create HTML email body"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .job {{ border: 1px solid #ddd; margin: 15px 0; padding: 15px; border-radius: 5px; }}
                .job h3 {{ margin: 0 0 10px 0; color: #4CAF50; }}
                .job p {{ margin: 5px 0; }}
                .company {{ font-weight: bold; color: #666; }}
                .location {{ color: #999; }}
                .url {{ margin-top: 10px; }}
                .url a {{ background-color: #4CAF50; color: white; padding: 8px 15px; 
                          text-decoration: none; border-radius: 3px; display: inline-block; }}
                .footer {{ margin-top: 30px; text-align: center; color: #999; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>SmartApply Job Matches</h1>
                </div>
                
                <p>Hi {user_name},</p>
                
                <p>We found {len(jobs)} new job matches based on your CV!</p>
        """
        
        for job in jobs:
            html += f"""
                <div class="job">
                    <h3>{job['title']}</h3>
                    <p class="company">🏢 {job['company']}</p>
                    <p class="location">📍 {job.get('location', 'Location not specified')}</p>
                    <p>Match Score: <strong>{job.get('match_score', 'N/A')}</strong></p>
                    <div class="url">
                        <a href="{job['url']}" target="_blank">View Job</a>
                    </div>
                </div>
            """
        
        html += """
                <div class="footer">
                    <p>You received this email because you signed up for SmartApply job alerts.</p>
                    <p>To unsubscribe or update your preferences, please contact us.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_alerts_for_matches(self, db: Session, matches: Dict[int, List[tuple]]) -> int:
        """Send alerts for all matches and update database"""
        emails_sent = 0
        
        for user_id, user_matches in matches.items():
            user = db.query(models.User).filter(models.User.id == user_id).first()
            if not user:
                continue
            
            # Prepare job data for email
            jobs_for_email = []
            for job_data, score in user_matches:
                job_data['match_score'] = f"{score:.2%}"
                jobs_for_email.append(job_data)
            
            # Send email
            if self.send_job_alert(user.email, user.name, jobs_for_email):
                # Update alert records
                for job_data, score in user_matches:
                    alert = db.query(models.JobAlert).filter(
                        models.JobAlert.user_id == user_id,
                        models.JobAlert.job.has(url=job_data['url'])
                    ).first()
                    
                    if alert:
                        alert.email_sent = True
                        alert.sent_at = datetime.utcnow()
                
                db.commit()
                emails_sent += 1
        
        return emails_sent