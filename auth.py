from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from models import User, RecruiterProfile, JobseekerProfile
import re

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember_me = bool(request.form.get('remember_me'))
        
        if not email or not password:
            flash('Please provide both email and password.', 'error')
            return render_template('auth/login.html')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact support.', 'error')
                return render_template('auth/login.html')
            
            login_user(user, remember=remember_me)
            user.last_login = db.func.now()
            db.session.commit()
            
            # Redirect to appropriate dashboard or intended page
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            
            if user.role == 'recruiter':
                return redirect(url_for('main.recruiter_dashboard'))
            else:
                return redirect(url_for('main.jobseeker_dashboard'))
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    role = request.args.get('role', 'jobseeker')
    if role not in ['recruiter', 'jobseeker']:
        role = 'jobseeker'
    
    if request.method == 'POST':
        # Get form data
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        role = request.form.get('role', 'jobseeker')
        
        # Validation
        errors = []
        
        if not email or not is_valid_email(email):
            errors.append('Please provide a valid email address.')
        
        if User.query.filter_by(email=email).first():
            errors.append('An account with this email already exists.')
        
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters long.')
        
        if password != confirm_password:
            errors.append('Passwords do not match.')
        
        if not first_name or not last_name:
            errors.append('Please provide both first and last name.')
        
        if role not in ['recruiter', 'jobseeker']:
            errors.append('Please select a valid role.')
        
        # Role-specific validation
        if role == 'recruiter':
            company = request.form.get('company', '').strip()
            if not company:
                errors.append('Company name is required for recruiters.')
        
        if role == 'jobseeker':
            phone = request.form.get('phone', '').strip()
            if phone and not is_valid_phone(phone):
                errors.append('Please provide a valid phone number.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('auth/register.html', role=role)
        
        # Create user
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Create role-specific profile
        if role == 'recruiter':
            recruiter_profile = RecruiterProfile(
                user_id=user.id,
                company=request.form.get('company', '').strip(),
                position=request.form.get('position', '').strip(),
                phone=request.form.get('phone', '').strip(),
                linkedin_url=request.form.get('linkedin_url', '').strip()
            )
            db.session.add(recruiter_profile)
        else:
            jobseeker_profile = JobseekerProfile(
                user_id=user.id,
                phone=request.form.get('phone', '').strip(),
                linkedin_url=request.form.get('linkedin_url', '').strip(),
                github_url=request.form.get('github_url', '').strip()
            )
            db.session.add(jobseeker_profile)
        
        db.session.commit()
        
        # Log in the user
        login_user(user)
        
        flash('Account created successfully! Welcome to Hirica!', 'success')
        
        # Redirect to profile completion
        return redirect(url_for('main.profile'))
    
    return render_template('auth/register.html', role=role)

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('main.index'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password form"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email or not is_valid_email(email):
            flash('Please provide a valid email address.', 'error')
            return render_template('auth/forgot_password.html')
        
        user = User.query.filter_by(email=email).first()
        
        if user:
            # In a real application, you would send a password reset email here
            # For now, we'll just show a message
            flash('If an account with this email exists, you will receive password reset instructions.', 'info')
        else:
            # Don't reveal whether the email exists or not
            flash('If an account with this email exists, you will receive password reset instructions.', 'info')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html')

def is_valid_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def is_valid_phone(phone):
    """Validate phone number format"""
    # Simple validation - you might want to use a proper phone validation library
    pattern = r'^[\+]?[1-9][\d]{0,15}$'
    return re.match(pattern, re.sub(r'[\s\-\(\)]', '', phone)) is not None
