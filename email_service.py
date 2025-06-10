import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, render_template_string
from flask_mail import Message, Mail
from app import mail

class EmailService:
    """Email service for sending notifications"""
    
    def __init__(self):
        self.smtp_server = 'smtp.gmail.com'
        self.smtp_port = 587
        self.username = os.environ.get('SENDGRID_FROM_EMAIL', 'hirica.tetraquard@gmail.com')
        self.password = os.environ.get('MAIL_PASSWORD', '')
        self.from_email = os.environ.get('SENDGRID_FROM_EMAIL', 'hirica.tetraquard@gmail.com')
    
    def send_application_notification(self, job, candidate):
        """Send email notification when someone applies for a job"""
        try:
            subject = f"New Application for {job.title}"
            
            # Email to recruiter
            recruiter_email = job.recruiter.user.email
            recruiter_body = f"""
            Dear {job.recruiter.user.first_name},
            
            You have received a new application for your job posting: {job.title}
            
            Candidate Details:
            - Name: {candidate.get_full_name()}
            - Email: {candidate.email}
            - Applied: Just now
            
            Please log in to your Hirica dashboard to review the application.
            
            Best regards,
            The Hirica Team
            """
            
            self._send_email(recruiter_email, subject, recruiter_body)
            
            # Confirmation email to candidate
            candidate_subject = f"Application Confirmed - {job.title}"
            candidate_body = f"""
            Dear {candidate.first_name},
            
            Thank you for applying to the {job.title} position at {job.recruiter.company}.
            
            Your application has been successfully submitted and is now under review.
            We will notify you once the recruiter has reviewed your application.
            
            Job Details:
            - Position: {job.title}
            - Company: {job.recruiter.company}
            - Location: {job.location}
            
            Best regards,
            The Hirica Team
            """
            
            self._send_email(candidate.email, candidate_subject, candidate_body)
            
        except Exception as e:
            current_app.logger.error(f"Error sending application notification: {str(e)}")
    
    def send_assessment_notification(self, application, assessment):
        """Send notification when assessment is ready"""
        try:
            candidate = application.jobseeker.user
            job = application.job
            
            subject = f"Assessment Ready - {job.title}"
            body = f"""
            Dear {candidate.first_name},
            
            Great news! Your application for {job.title} at {job.recruiter.company} has been approved.
            
            The next step is to complete an assessment that has been specifically designed for this role.
            
            Assessment Details:
            - Time Limit: {assessment.time_limit} minutes
            - Questions: {len(assessment.get_questions_list())} questions
            - Projects: {len(assessment.get_projects_list())} projects
            
            Important Instructions:
            - Ensure you have a stable internet connection
            - Use a quiet environment with good lighting
            - Have your webcam and microphone ready
            - Do not use any external resources unless specified
            
            Please log in to your Hirica account to begin the assessment.
            
            Best regards,
            The Hirica Team
            """
            
            self._send_email(candidate.email, subject, body)
            
        except Exception as e:
            current_app.logger.error(f"Error sending assessment notification: {str(e)}")
    
    def send_test_completion_notification(self, test_result):
        """Send notification when test is completed"""
        try:
            application = test_result.application
            recruiter = application.job.recruiter.user
            candidate = application.jobseeker.user
            
            # Notification to recruiter
            recruiter_subject = f"Assessment Completed - {application.job.title}"
            recruiter_body = f"""
            Dear {recruiter.first_name},
            
            {candidate.get_full_name()} has completed the assessment for {application.job.title}.
            
            Assessment Results:
            - Score: {test_result.score:.1f}%
            - Completion Time: {test_result.time_taken} minutes
            - Status: {test_result.status.replace('_', ' ').title()}
            
            Please log in to your dashboard to review the detailed results.
            
            Best regards,
            The Hirica Team
            """
            
            self._send_email(recruiter.email, recruiter_subject, recruiter_body)
            
            # Confirmation to candidate
            candidate_subject = f"Assessment Submitted - {application.job.title}"
            candidate_body = f"""
            Dear {candidate.first_name},
            
            Thank you for completing the assessment for {application.job.title}.
            
            Your assessment has been successfully submitted and the recruiter has been notified.
            You will receive an update once your assessment has been reviewed.
            
            Best regards,
            The Hirica Team
            """
            
            self._send_email(candidate.email, candidate_subject, candidate_body)
            
        except Exception as e:
            current_app.logger.error(f"Error sending test completion notification: {str(e)}")
    
    def send_welcome_email(self, user):
        """Send welcome email to new users"""
        try:
            subject = "Welcome to Hirica!"
            
            if user.role == 'recruiter':
                body = f"""
                Dear {user.first_name},
                
                Welcome to Hirica! We're excited to help you find the best talent for your organization.
                
                As a recruiter, you can:
                - Post job openings with detailed requirements
                - Generate AI-powered assessments
                - Review candidate applications and test results
                - Manage your hiring pipeline effectively
                
                Next Steps:
                1. Complete your company profile
                2. Post your first job opening
                3. Start receiving applications
                
                If you need any assistance, please don't hesitate to contact our support team.
                
                Best regards,
                The Hirica Team
                """
            else:
                body = f"""
                Dear {user.first_name},
                
                Welcome to Hirica! We're here to help you find your dream job.
                
                As a job seeker, you can:
                - Browse and apply for jobs from top companies
                - Take AI-powered assessments to showcase your skills
                - Track your application status in real-time
                - Build a comprehensive professional profile
                
                Next Steps:
                1. Complete your profile and upload your resume
                2. Browse available job opportunities
                3. Apply for positions that match your skills
                
                Best of luck with your job search!
                
                Best regards,
                The Hirica Team
                """
            
            self._send_email(user.email, subject, body)
            
        except Exception as e:
            current_app.logger.error(f"Error sending welcome email: {str(e)}")
    
    def send_password_reset(self, user, reset_token):
        """Send password reset email"""
        try:
            subject = "Password Reset - Hirica"
            body = f"""
            Dear {user.first_name},
            
            You have requested to reset your password for your Hirica account.
            
            Please click the link below to reset your password:
            [Reset Password Link - Implementation needed]
            
            If you did not request this password reset, please ignore this email.
            
            This link will expire in 1 hour for security reasons.
            
            Best regards,
            The Hirica Team
            """
            
            self._send_email(user.email, subject, body)
            
        except Exception as e:
            current_app.logger.error(f"Error sending password reset email: {str(e)}")
    
    def _send_email(self, to_email, subject, body):
        """Send email using SMTP"""
        try:
            # Try using Flask-Mail first
            if current_app.config.get('MAIL_SERVER'):
                msg = Message(
                    subject=subject,
                    recipients=[to_email],
                    body=body,
                    sender=self.from_email
                )
                mail.send(msg)
                current_app.logger.info(f"Email sent via Flask-Mail to {to_email}")
                return
            
            # Fallback to direct SMTP
            if not self.password:
                current_app.logger.warning("Email password not configured, skipping email send")
                return
            
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            
            current_app.logger.info(f"Email sent via SMTP to {to_email}")
            
        except Exception as e:
            current_app.logger.error(f"Failed to send email to {to_email}: {str(e)}")
            # Don't raise the exception to avoid breaking the main flow
    
    def send_bulk_notification(self, recipients, subject, body):
        """Send bulk notification emails"""
        for recipient in recipients:
            try:
                self._send_email(recipient, subject, body)
            except Exception as e:
                current_app.logger.error(f"Failed to send bulk email to {recipient}: {str(e)}")
                continue
