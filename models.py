from datetime import datetime, timedelta
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.sql import func
import json

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'recruiter' or 'jobseeker'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    profile_completed = db.Column(db.Boolean, default=False)
    google_id = db.Column(db.String(100), unique=True)
    
    # Relationships
    recruiter_profile = db.relationship('RecruiterProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    jobseeker_profile = db.relationship('JobseekerProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def __repr__(self):
        return f'<User {self.email}>'

class RecruiterProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    linkedin_url = db.Column(db.String(200))
    company_website = db.Column(db.String(200))
    company_description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    jobs = db.relationship('Job', backref='recruiter', lazy=True, cascade='all, delete-orphan')

class JobseekerProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    phone = db.Column(db.String(20))
    linkedin_url = db.Column(db.String(200))
    github_url = db.Column(db.String(200))
    resume_filename = db.Column(db.String(200))
    skills = db.Column(db.Text)  # JSON string
    experience_years = db.Column(db.Integer)
    current_position = db.Column(db.String(100))
    education = db.Column(db.Text)
    location = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    applications = db.relationship('JobApplication', backref='jobseeker', lazy=True, cascade='all, delete-orphan')

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recruiter_id = db.Column(db.Integer, db.ForeignKey('recruiter_profile.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    requirements = db.Column(db.Text)
    responsibilities = db.Column(db.Text)
    skills_required = db.Column(db.Text)  # JSON string
    location = db.Column(db.String(100), nullable=False)
    employment_type = db.Column(db.String(50), nullable=False)  # Full-time, Part-time, Internship
    experience_level = db.Column(db.String(50))  # Entry, Mid, Senior
    salary_range = db.Column(db.String(100))
    degree_required = db.Column(db.String(100))
    expires_at = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    applications = db.relationship('JobApplication', back_populates='job', cascade='all, delete-orphan')
    assessments = db.relationship('Assessment', backref='job', cascade='all, delete-orphan')
    
    def is_expired(self):
        return datetime.utcnow() > self.expires_at
    
    def get_skills_list(self):
        if self.skills_required:
            try:
                return json.loads(self.skills_required)
            except:
                return []
        return []

class JobApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    jobseeker_id = db.Column(db.Integer, db.ForeignKey('jobseeker_profile.id'), nullable=False)
    cover_letter = db.Column(db.Text)
    status = db.Column(db.String(50), default='pending')  # pending, approved, rejected, test_generated, test_taken
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    
    # Relationships
    job = db.relationship('Job', back_populates='applications')
    test_results = db.relationship('TestResult', backref='application', cascade='all, delete-orphan')

class Assessment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    questions = db.Column(db.Text)  # JSON string
    projects = db.Column(db.Text)  # JSON string
    anti_cheat_rules = db.Column(db.Text)  # JSON string
    time_limit = db.Column(db.Integer)  # in minutes
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    test_results = db.relationship('TestResult', backref='assessment', cascade='all, delete-orphan')
    
    def get_questions_list(self):
        if self.questions:
            try:
                return json.loads(self.questions)
            except:
                return []
        return []
    
    def get_projects_list(self):
        if self.projects:
            try:
                return json.loads(self.projects)
            except:
                return []
        return []
    
    def get_anti_cheat_rules(self):
        if self.anti_cheat_rules:
            try:
                return json.loads(self.anti_cheat_rules)
            except:
                return {}
        return {}

class TestResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('job_application.id'), nullable=False)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessment.id'), nullable=False)
    answers = db.Column(db.Text)  # JSON string
    project_files = db.Column(db.Text)  # JSON string with file paths
    score = db.Column(db.Float)
    completed_at = db.Column(db.DateTime)
    time_taken = db.Column(db.Integer)  # in minutes
    violations = db.Column(db.Text)  # JSON string of anti-cheat violations
    status = db.Column(db.String(50), default='in_progress')  # in_progress, completed, pending_projects
    
    def get_answers_dict(self):
        if self.answers:
            try:
                return json.loads(self.answers)
            except:
                return {}
        return {}
    
    def get_violations_list(self):
        if self.violations:
            try:
                return json.loads(self.violations)
            except:
                return []
        return []

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), default='info')  # info, success, warning, error
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='notifications')

class AntiCheatLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_result_id = db.Column(db.Integer, db.ForeignKey('test_result.id'), nullable=False)
    violation_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    severity = db.Column(db.String(20), default='medium')  # low, medium, high
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    
    # Relationships
    test_result = db.relationship('TestResult', backref='cheat_logs')

class AdminStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    total_users = db.Column(db.Integer, default=0)
    total_recruiters = db.Column(db.Integer, default=0)
    total_jobseekers = db.Column(db.Integer, default=0)
    total_jobs = db.Column(db.Integer, default=0)
    total_applications = db.Column(db.Integer, default=0)
    total_assessments = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
