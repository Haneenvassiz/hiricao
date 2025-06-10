# Use this Flask blueprint for Google authentication. Do not use flask-dance.

import json
import os

import requests
from app import db
from flask import Blueprint, redirect, request, url_for, flash
from flask_login import login_required, login_user, logout_user, current_user
from models import User, RecruiterProfile, JobseekerProfile
from oauthlib.oauth2 import WebApplicationClient

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# OAuth redirect URL configuration
if os.environ.get("REPLIT_DEV_DOMAIN"):
    DEV_REDIRECT_URL = f'https://{os.environ["REPLIT_DEV_DOMAIN"]}/oauth/google_login/callback'
else:
    DEV_REDIRECT_URL = 'http://localhost:5000/oauth/google_login/callback'

# Display setup instructions if Google OAuth is not properly configured
if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    print(f"""
    ⚠️  Google OAuth Configuration Required ⚠️
    
    To enable Google authentication:
    1. Go to https://console.cloud.google.com/apis/credentials
    2. Create a new OAuth 2.0 Client ID
    3. Add {DEV_REDIRECT_URL} to Authorized redirect URIs
    4. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables
    
    For detailed instructions, see:
    https://docs.replit.com/additional-resources/google-auth-in-flask#set-up-your-oauth-app--client
    """)

client = WebApplicationClient(GOOGLE_CLIENT_ID) if GOOGLE_CLIENT_ID else None

google_auth = Blueprint("google_auth", __name__)


@google_auth.route("/google_login")
def login():
    """Initiate Google OAuth login"""
    if not client:
        flash('Google authentication is not configured.', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]

        request_uri = client.prepare_request_uri(
            authorization_endpoint,
            redirect_uri=request.base_url.replace("http://", "https://") + "/callback",
            scope=["openid", "email", "profile"],
        )
        return redirect(request_uri)
    except Exception as e:
        flash('Failed to connect to Google. Please try again later.', 'error')
        return redirect(url_for('auth.login'))


@google_auth.route("/google_login/callback")
def callback():
    """Handle Google OAuth callback"""
    if not client:
        flash('Google authentication is not configured.', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        code = request.args.get("code")
        if not code:
            flash('Authorization failed. Please try again.', 'error')
            return redirect(url_for('auth.login'))
        
        google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
        token_endpoint = google_provider_cfg["token_endpoint"]

        token_url, headers, body = client.prepare_token_request(
            token_endpoint,
            authorization_response=request.url.replace("http://", "https://"),
            redirect_url=request.base_url.replace("http://", "https://"),
            code=code,
        )
        
        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
        )

        if not token_response.ok:
            flash('Failed to obtain access token from Google.', 'error')
            return redirect(url_for('auth.login'))

        client.parse_request_body_response(json.dumps(token_response.json()))

        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        uri, headers, body = client.add_token(userinfo_endpoint)
        userinfo_response = requests.get(uri, headers=headers, data=body)

        if not userinfo_response.ok:
            flash('Failed to get user information from Google.', 'error')
            return redirect(url_for('auth.login'))

        userinfo = userinfo_response.json()
        
        if not userinfo.get("email_verified"):
            flash("Google account email not verified. Please verify your email with Google first.", 'error')
            return redirect(url_for('auth.login'))

        users_email = userinfo["email"].lower()
        users_name = userinfo.get("name", "")
        users_given_name = userinfo.get("given_name", "")
        users_family_name = userinfo.get("family_name", "")
        google_id = userinfo.get("sub", "")

        # Check if user exists
        user = User.query.filter_by(email=users_email).first()
        
        if user:
            # Update Google ID if not set
            if not user.google_id:
                user.google_id = google_id
                db.session.commit()
            
            # Log in existing user
            login_user(user)
            user.last_login = db.func.now()
            db.session.commit()
            
            flash(f'Welcome back, {user.first_name}!', 'success')
            
            if user.role == 'recruiter':
                return redirect(url_for('main.recruiter_dashboard'))
            else:
                return redirect(url_for('main.jobseeker_dashboard'))
        else:
            # New user - redirect to role selection/registration
            # Store Google user info in session for registration
            from flask import session
            session['google_user'] = {
                'email': users_email,
                'given_name': users_given_name or '',
                'family_name': users_family_name or '',
                'google_id': google_id
            }
            
            flash('Please complete your registration by selecting your role.', 'info')
            return redirect(url_for('auth.register'))

    except Exception as e:
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))


@google_auth.route("/complete-google-registration", methods=['POST'])
def complete_google_registration():
    """Complete registration for Google OAuth users"""
    from flask import session
    
    google_user = session.get('google_user')
    if not google_user:
        flash('Registration session expired. Please try again.', 'error')
        return redirect(url_for('auth.register'))
    
    role = request.form.get('role')
    if role not in ['recruiter', 'jobseeker']:
        flash('Please select a valid role.', 'error')
        return redirect(url_for('auth.register'))
    
    try:
        # Create new user
        user = User(
            email=google_user['email'],
            first_name=google_user['given_name'],
            last_name=google_user['family_name'],
            role=role,
            google_id=google_user['google_id']
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Create role-specific profile
        if role == 'recruiter':
            company = request.form.get('company', '').strip()
            if not company:
                flash('Company name is required for recruiters.', 'error')
                return redirect(url_for('auth.register'))
            
            recruiter_profile = RecruiterProfile(
                user_id=user.id,
                company=company,
                position=request.form.get('position', '').strip(),
                phone=request.form.get('phone', '').strip()
            )
            db.session.add(recruiter_profile)
        else:
            jobseeker_profile = JobseekerProfile(
                user_id=user.id,
                phone=request.form.get('phone', '').strip()
            )
            db.session.add(jobseeker_profile)
        
        db.session.commit()
        
        # Clear session data
        session.pop('google_user', None)
        
        # Log in the user
        login_user(user)
        
        flash('Account created successfully! Welcome to Hirica!', 'success')
        return redirect(url_for('main.profile'))
        
    except Exception as e:
        db.session.rollback()
        flash('Failed to create account. Please try again.', 'error')
        return redirect(url_for('auth.register'))


@google_auth.route("/logout")
@login_required
def logout():
    """Logout user"""
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('main.index'))
