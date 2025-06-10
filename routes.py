from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from app import db
from models import Job, JobApplication, User, RecruiterProfile, JobseekerProfile, Assessment, TestResult, Notification, AdminStats
from ai_service import AIService
from email_service import EmailService
from anti_cheat import AntiCheatService
from utils import allowed_file, save_uploaded_file, get_file_extension
import os
import json
from datetime import datetime, timedelta
from sqlalchemy import desc, func

main_bp = Blueprint('main', __name__)
ai_service = AIService()
email_service = EmailService()
anti_cheat_service = AntiCheatService()

@main_bp.route('/')
def index():
    """Main landing page"""
    featured_jobs = Job.query.filter_by(is_active=True, is_featured=True).limit(6).all()
    return render_template('index.html', featured_jobs=featured_jobs)

@main_bp.route('/jobs')
def jobs():
    """Browse all jobs"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    location = request.args.get('location', '')
    employment_type = request.args.get('employment_type', '')
    
    query = Job.query.filter_by(is_active=True)
    
    if search:
        query = query.filter(Job.title.contains(search) | Job.description.contains(search))
    if location:
        query = query.filter(Job.location.contains(location))
    if employment_type:
        query = query.filter_by(employment_type=employment_type)
    
    jobs_pagination = query.order_by(desc(Job.created_at)).paginate(
        page=page, per_page=12, error_out=False
    )
    
    return render_template('jobseeker/browse_jobs.html', 
                         jobs=jobs_pagination.items,
                         pagination=jobs_pagination,
                         search=search,
                         location=location,
                         employment_type=employment_type)

@main_bp.route('/job/<int:job_id>')
def job_detail(job_id):
    """Job detail page"""
    job = Job.query.get_or_404(job_id)
    
    # Check if user has already applied
    has_applied = False
    if current_user.is_authenticated and current_user.role == 'jobseeker':
        has_applied = JobApplication.query.filter_by(
            job_id=job_id, 
            jobseeker_id=current_user.jobseeker_profile.id
        ).first() is not None
    
    return render_template('jobseeker/job_detail.html', job=job, has_applied=has_applied)

@main_bp.route('/apply/<int:job_id>', methods=['GET', 'POST'])
@login_required
def apply_job(job_id):
    """Apply for a job"""
    if current_user.role != 'jobseeker':
        flash('Only job seekers can apply for jobs.', 'error')
        return redirect(url_for('main.job_detail', job_id=job_id))
    
    job = Job.query.get_or_404(job_id)
    
    # Check if already applied
    existing_application = JobApplication.query.filter_by(
        job_id=job_id, 
        jobseeker_id=current_user.jobseeker_profile.id
    ).first()
    
    if existing_application:
        flash('You have already applied for this job.', 'info')
        return redirect(url_for('main.job_detail', job_id=job_id))
    
    if request.method == 'POST':
        cover_letter = request.form.get('cover_letter', '')
        
        application = JobApplication(
            job_id=job_id,
            jobseeker_id=current_user.jobseeker_profile.id,
            cover_letter=cover_letter
        )
        
        db.session.add(application)
        db.session.commit()
        
        # Send notification to recruiter
        notification = Notification(
            user_id=job.recruiter.user_id,
            title='New Job Application',
            message=f'{current_user.get_full_name()} has applied for {job.title}',
            type='info'
        )
        db.session.add(notification)
        db.session.commit()
        
        # Send email notification
        email_service.send_application_notification(job, current_user)
        
        flash('Your application has been submitted successfully!', 'success')
        return redirect(url_for('main.jobseeker_dashboard'))
    
    return render_template('jobseeker/apply.html', job=job)

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Redirect to appropriate dashboard based on user role"""
    if current_user.role == 'recruiter':
        return redirect(url_for('main.recruiter_dashboard'))
    else:
        return redirect(url_for('main.jobseeker_dashboard'))

@main_bp.route('/recruiter/dashboard')
@login_required
def recruiter_dashboard():
    """Recruiter dashboard"""
    if current_user.role != 'recruiter':
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    
    # Get statistics
    total_jobs = Job.query.filter_by(recruiter_id=current_user.recruiter_profile.id).count()
    active_jobs = Job.query.filter_by(recruiter_id=current_user.recruiter_profile.id, is_active=True).count()
    total_applications = db.session.query(JobApplication).join(Job).filter(
        Job.recruiter_id == current_user.recruiter_profile.id
    ).count()
    pending_applications = db.session.query(JobApplication).join(Job).filter(
        Job.recruiter_id == current_user.recruiter_profile.id,
        JobApplication.status == 'pending'
    ).count()
    
    # Recent jobs
    recent_jobs = Job.query.filter_by(
        recruiter_id=current_user.recruiter_profile.id
    ).order_by(desc(Job.created_at)).limit(5).all()
    
    # Recent applications
    recent_applications = db.session.query(JobApplication).join(Job).filter(
        Job.recruiter_id == current_user.recruiter_profile.id
    ).order_by(desc(JobApplication.applied_at)).limit(5).all()
    
    return render_template('recruiter/dashboard.html',
                         total_jobs=total_jobs,
                         active_jobs=active_jobs,
                         total_applications=total_applications,
                         pending_applications=pending_applications,
                         recent_jobs=recent_jobs,
                         recent_applications=recent_applications)

@main_bp.route('/jobseeker/dashboard')
@login_required
def jobseeker_dashboard():
    """Job seeker dashboard"""
    if current_user.role != 'jobseeker':
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    
    # Get statistics
    total_applications = JobApplication.query.filter_by(
        jobseeker_id=current_user.jobseeker_profile.id
    ).count()
    pending_applications = JobApplication.query.filter_by(
        jobseeker_id=current_user.jobseeker_profile.id,
        status='pending'
    ).count()
    approved_applications = JobApplication.query.filter_by(
        jobseeker_id=current_user.jobseeker_profile.id,
        status='approved'
    ).count()
    test_taken = TestResult.query.join(JobApplication).filter(
        JobApplication.jobseeker_id == current_user.jobseeker_profile.id,
        TestResult.status == 'completed'
    ).count()
    
    # Recent applications
    recent_applications = JobApplication.query.filter_by(
        jobseeker_id=current_user.jobseeker_profile.id
    ).order_by(desc(JobApplication.applied_at)).limit(5).all()
    
    # Available tests
    available_tests = JobApplication.query.filter_by(
        jobseeker_id=current_user.jobseeker_profile.id,
        status='test_generated'
    ).all()
    
    return render_template('jobseeker/dashboard.html',
                         total_applications=total_applications,
                         pending_applications=pending_applications,
                         approved_applications=approved_applications,
                         test_taken=test_taken,
                         recent_applications=recent_applications,
                         available_tests=available_tests)

@main_bp.route('/recruiter/post-job', methods=['GET', 'POST'])
@login_required
def post_job():
    """Post a new job"""
    if current_user.role != 'recruiter':
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        # Extract form data
        title = request.form.get('title')
        description = request.form.get('description')
        requirements = request.form.get('requirements')
        responsibilities = request.form.get('responsibilities')
        skills_required = request.form.getlist('skills')
        location = request.form.get('location')
        employment_type = request.form.get('employment_type')
        experience_level = request.form.get('experience_level')
        salary_range = request.form.get('salary_range')
        degree_required = request.form.get('degree_required')
        expires_in_days = int(request.form.get('expires_in_days', 30))
        
        # Create job
        job = Job(
            recruiter_id=current_user.recruiter_profile.id,
            title=title,
            description=description,
            requirements=requirements,
            responsibilities=responsibilities,
            skills_required=json.dumps(skills_required),
            location=location,
            employment_type=employment_type,
            experience_level=experience_level,
            salary_range=salary_range,
            degree_required=degree_required,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days)
        )
        
        db.session.add(job)
        db.session.commit()
        
        flash('Job posted successfully!', 'success')
        return redirect(url_for('main.recruiter_dashboard'))
    
    return render_template('recruiter/post_job.html')

@main_bp.route('/recruiter/manage-jobs')
@login_required
def manage_jobs():
    """Manage jobs"""
    if current_user.role != 'recruiter':
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    
    page = request.args.get('page', 1, type=int)
    jobs_pagination = Job.query.filter_by(
        recruiter_id=current_user.recruiter_profile.id
    ).order_by(desc(Job.created_at)).paginate(
        page=page, per_page=10, error_out=False
    )
    
    return render_template('recruiter/manage_jobs.html', 
                         jobs=jobs_pagination.items,
                         pagination=jobs_pagination)

@main_bp.route('/recruiter/job/<int:job_id>/applications')
@login_required
def view_applications(job_id):
    """View applications for a job"""
    if current_user.role != 'recruiter':
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    
    job = Job.query.filter_by(
        id=job_id, 
        recruiter_id=current_user.recruiter_profile.id
    ).first_or_404()
    
    applications = JobApplication.query.filter_by(job_id=job_id).order_by(
        desc(JobApplication.applied_at)
    ).all()
    
    return render_template('recruiter/view_applications.html', 
                         job=job, 
                         applications=applications)

@main_bp.route('/recruiter/application/<int:application_id>/action', methods=['POST'])
@login_required
def application_action(application_id):
    """Handle application actions (approve/reject)"""
    if current_user.role != 'recruiter':
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    
    application = JobApplication.query.get_or_404(application_id)
    
    # Verify ownership
    if application.job.recruiter_id != current_user.recruiter_profile.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.recruiter_dashboard'))
    
    action = request.form.get('action')
    
    if action == 'approve':
        application.status = 'approved'
        application.reviewed_at = datetime.utcnow()
        
        # Send notification
        notification = Notification(
            user_id=application.jobseeker.user_id,
            title='Application Approved',
            message=f'Your application for {application.job.title} has been approved!',
            type='success'
        )
        db.session.add(notification)
        
        flash('Application approved successfully!', 'success')
        
    elif action == 'reject':
        application.status = 'rejected'
        application.reviewed_at = datetime.utcnow()
        
        # Send notification
        notification = Notification(
            user_id=application.jobseeker.user_id,
            title='Application Status Update',
            message=f'Thank you for your interest in {application.job.title}. We have decided to move forward with other candidates.',
            type='info'
        )
        db.session.add(notification)
        
        flash('Application rejected.', 'info')
    
    db.session.commit()
    return redirect(url_for('main.view_applications', job_id=application.job_id))

@main_bp.route('/recruiter/application/<int:application_id>/generate-assessment', methods=['GET', 'POST'])
@login_required
def generate_assessment(application_id):
    """Generate AI assessment for application"""
    if current_user.role != 'recruiter':
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    
    application = JobApplication.query.get_or_404(application_id)
    
    # Verify ownership
    if application.job.recruiter_id != current_user.recruiter_profile.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.recruiter_dashboard'))
    
    if request.method == 'POST':
        # Generate assessment using AI
        try:
            assessment_data = ai_service.generate_assessment(application.job)
            
            assessment = Assessment(
                job_id=application.job_id,
                title=f"Assessment for {application.job.title}",
                questions=json.dumps(assessment_data['questions']),
                projects=json.dumps(assessment_data['projects']),
                anti_cheat_rules=json.dumps(assessment_data['anti_cheat_rules']),
                time_limit=assessment_data['time_limit']
            )
            
            db.session.add(assessment)
            db.session.commit()
            
            flash('Assessment generated successfully!', 'success')
            return redirect(url_for('main.edit_assessment', assessment_id=assessment.id))
            
        except Exception as e:
            current_app.logger.error(f"Error generating assessment: {str(e)}")
            flash('Failed to generate assessment. Please try again.', 'error')
    
    return render_template('recruiter/generate_assessment.html', application=application)

@main_bp.route('/recruiter/assessment/<int:assessment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_assessment(assessment_id):
    """Edit assessment before approval"""
    if current_user.role != 'recruiter':
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    
    assessment = Assessment.query.get_or_404(assessment_id)
    
    # Verify ownership
    if assessment.job.recruiter_id != current_user.recruiter_profile.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.recruiter_dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'approve':
            assessment.is_approved = True
            
            # Update application status
            applications = JobApplication.query.filter_by(job_id=assessment.job_id).all()
            for app in applications:
                if app.status == 'approved':
                    app.status = 'test_generated'
                    
                    # Send notification
                    notification = Notification(
                        user_id=app.jobseeker.user_id,
                        title='Assessment Ready',
                        message=f'Your assessment for {assessment.job.title} is now available!',
                        type='info'
                    )
                    db.session.add(notification)
            
            db.session.commit()
            flash('Assessment approved and sent to candidates!', 'success')
            return redirect(url_for('main.recruiter_dashboard'))
        
        elif action == 'save':
            # Update assessment with form data
            questions_data = []
            projects_data = []
            
            # Process questions
            question_count = int(request.form.get('question_count', 0))
            for i in range(question_count):
                question = {
                    'id': i + 1,
                    'type': request.form.get(f'question_{i}_type'),
                    'question': request.form.get(f'question_{i}_text'),
                    'time_limit': int(request.form.get(f'question_{i}_time', 30)),
                    'rules': {
                        'copy_paste_allowed': request.form.get(f'question_{i}_copy_paste') == 'on',
                        'tab_switching_allowed': request.form.get(f'question_{i}_tab_switch') == 'on',
                        'webcam_required': request.form.get(f'question_{i}_webcam') == 'on',
                        'fullscreen_required': request.form.get(f'question_{i}_fullscreen') == 'on'
                    }
                }
                
                if question['type'] == 'multiple_choice':
                    question['options'] = [
                        request.form.get(f'question_{i}_option_0'),
                        request.form.get(f'question_{i}_option_1'),
                        request.form.get(f'question_{i}_option_2'),
                        request.form.get(f'question_{i}_option_3')
                    ]
                    question['correct_answer'] = int(request.form.get(f'question_{i}_correct', 0))
                
                questions_data.append(question)
            
            # Process projects
            has_short_project = request.form.get('has_short_project') == 'on'
            has_long_project = request.form.get('has_long_project') == 'on'
            
            if has_short_project:
                projects_data.append({
                    'type': 'short',
                    'title': request.form.get('short_project_title'),
                    'description': request.form.get('short_project_description'),
                    'time_limit': int(request.form.get('short_project_time', 120))
                })
            
            if has_long_project:
                projects_data.append({
                    'type': 'long',
                    'title': request.form.get('long_project_title'),
                    'description': request.form.get('long_project_description'),
                    'deadline_days': int(request.form.get('long_project_deadline', 7))
                })
            
            assessment.questions = json.dumps(questions_data)
            assessment.projects = json.dumps(projects_data)
            assessment.time_limit = int(request.form.get('total_time_limit', 120))
            
            db.session.commit()
            flash('Assessment saved successfully!', 'success')
    
    return render_template('recruiter/edit_assessment.html', assessment=assessment)

@main_bp.route('/assessment/<int:application_id>/instructions')
@login_required
def assessment_instructions(application_id):
    """Show assessment instructions to job seeker"""
    if current_user.role != 'jobseeker':
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    
    application = JobApplication.query.filter_by(
        id=application_id,
        jobseeker_id=current_user.jobseeker_profile.id,
        status='test_generated'
    ).first_or_404()
    
    assessment = Assessment.query.filter_by(
        job_id=application.job_id,
        is_approved=True
    ).first_or_404()
    
    return render_template('assessment/instructions.html', 
                         application=application, 
                         assessment=assessment)

@main_bp.route('/assessment/<int:application_id>/start', methods=['POST'])
@login_required
def start_assessment(application_id):
    """Start taking the assessment"""
    if current_user.role != 'jobseeker':
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    
    application = JobApplication.query.filter_by(
        id=application_id,
        jobseeker_id=current_user.jobseeker_profile.id,
        status='test_generated'
    ).first_or_404()
    
    assessment = Assessment.query.filter_by(
        job_id=application.job_id,
        is_approved=True
    ).first_or_404()
    
    # Create test result record
    test_result = TestResult(
        application_id=application_id,
        assessment_id=assessment.id,
        status='in_progress'
    )
    
    db.session.add(test_result)
    db.session.commit()
    
    return redirect(url_for('main.take_assessment', test_result_id=test_result.id))

@main_bp.route('/assessment/take/<int:test_result_id>')
@login_required
def take_assessment(test_result_id):
    """Take the assessment"""
    if current_user.role != 'jobseeker':
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    
    test_result = TestResult.query.filter_by(
        id=test_result_id,
        status='in_progress'
    ).first_or_404()
    
    # Verify ownership
    if test_result.application.jobseeker_id != current_user.jobseeker_profile.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.jobseeker_dashboard'))
    
    return render_template('assessment/take_test.html', test_result=test_result)

@main_bp.route('/assessment/submit/<int:test_result_id>', methods=['POST'])
@login_required
def submit_assessment(test_result_id):
    """Submit assessment answers"""
    if current_user.role != 'jobseeker':
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    
    test_result = TestResult.query.get_or_404(test_result_id)
    
    # Verify ownership
    if test_result.application.jobseeker_id != current_user.jobseeker_profile.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.jobseeker_dashboard'))
    
    # Process answers
    answers = {}
    for key, value in request.form.items():
        if key.startswith('question_'):
            answers[key] = value
    
    # Calculate score using AI
    try:
        score = ai_service.calculate_score(test_result.assessment, answers)
    except Exception as e:
        current_app.logger.error(f"Error calculating score: {str(e)}")
        score = 0.0
    
    # Update test result
    test_result.answers = json.dumps(answers)
    test_result.score = score
    test_result.completed_at = datetime.utcnow()
    test_result.status = 'completed'
    
    # Update application status
    test_result.application.status = 'test_taken'
    
    db.session.commit()
    
    # Send notification to recruiter
    notification = Notification(
        user_id=test_result.application.job.recruiter.user_id,
        title='Assessment Completed',
        message=f'{current_user.get_full_name()} has completed the assessment for {test_result.application.job.title}',
        type='info'
    )
    db.session.add(notification)
    db.session.commit()
    
    flash('Assessment submitted successfully!', 'success')
    return redirect(url_for('main.assessment_results', test_result_id=test_result_id))

@main_bp.route('/assessment/results/<int:test_result_id>')
@login_required
def assessment_results(test_result_id):
    """View assessment results"""
    test_result = TestResult.query.get_or_404(test_result_id)
    
    # Check permissions
    if current_user.role == 'jobseeker':
        if test_result.application.jobseeker_id != current_user.jobseeker_profile.id:
            flash('Access denied.', 'error')
            return redirect(url_for('main.jobseeker_dashboard'))
    elif current_user.role == 'recruiter':
        if test_result.application.job.recruiter_id != current_user.recruiter_profile.id:
            flash('Access denied.', 'error')
            return redirect(url_for('main.recruiter_dashboard'))
    else:
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    
    return render_template('assessment/results.html', test_result=test_result)

@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile page"""
    if request.method == 'POST':
        # Update basic user info
        current_user.first_name = request.form.get('first_name')
        current_user.last_name = request.form.get('last_name')
        
        if current_user.role == 'recruiter':
            profile = current_user.recruiter_profile
            if not profile:
                profile = RecruiterProfile(user_id=current_user.id)
                db.session.add(profile)
            
            profile.company = request.form.get('company')
            profile.position = request.form.get('position')
            profile.phone = request.form.get('phone')
            profile.linkedin_url = request.form.get('linkedin_url')
            profile.company_website = request.form.get('company_website')
            profile.company_description = request.form.get('company_description')
        
        else:  # jobseeker
            profile = current_user.jobseeker_profile
            if not profile:
                profile = JobseekerProfile(user_id=current_user.id)
                db.session.add(profile)
            
            profile.phone = request.form.get('phone')
            profile.linkedin_url = request.form.get('linkedin_url')
            profile.github_url = request.form.get('github_url')
            profile.skills = request.form.get('skills')
            profile.experience_years = int(request.form.get('experience_years', 0) or 0)
            profile.current_position = request.form.get('current_position')
            profile.education = request.form.get('education')
            profile.location = request.form.get('location')
            
            # Handle resume upload
            if 'resume' in request.files:
                file = request.files['resume']
                if file and file.filename and allowed_file(file.filename):
                    filename = save_uploaded_file(file, 'resumes')
                    if filename:
                        profile.resume_filename = filename
        
        current_user.profile_completed = True
        db.session.commit()
        
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('main.profile'))
    
    return render_template('jobseeker/profile.html')

@main_bp.route('/notifications')
@login_required
def notifications():
    """Get user notifications (AJAX)"""
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(desc(Notification.created_at)).limit(10).all()
    
    # Mark as read
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    
    return jsonify([{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'type': n.type,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M')
    } for n in notifications])

@main_bp.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Admin monitoring dashboard"""
    # For now, allow any logged-in user to access admin dashboard
    # In production, you'd want proper admin role checking
    
    # Calculate statistics
    total_users = User.query.count()
    total_recruiters = User.query.filter_by(role='recruiter').count()
    total_jobseekers = User.query.filter_by(role='jobseeker').count()
    total_jobs = Job.query.count()
    active_jobs = Job.query.filter_by(is_active=True).count()
    total_applications = JobApplication.query.count()
    total_assessments = Assessment.query.count()
    
    # Anti-cheat violations
    from models import AntiCheatLog
    recent_violations = db.session.query(func.count()).select_from(AntiCheatLog).scalar() or 0
    
    # Recent activity
    recent_users = User.query.order_by(desc(User.created_at)).limit(5).all()
    recent_jobs = Job.query.order_by(desc(Job.created_at)).limit(5).all()
    recent_applications = JobApplication.query.order_by(desc(JobApplication.applied_at)).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_recruiters=total_recruiters,
                         total_jobseekers=total_jobseekers,
                         total_jobs=total_jobs,
                         active_jobs=active_jobs,
                         total_applications=total_applications,
                         total_assessments=total_assessments,
                         recent_violations=recent_violations,
                         recent_users=recent_users,
                         recent_jobs=recent_jobs,
                         recent_applications=recent_applications)

@main_bp.route('/legal/privacy')
def privacy_policy():
    """Privacy policy page"""
    return render_template('legal/privacy.html')

@main_bp.route('/legal/terms')
def terms_of_service():
    """Terms of service page"""
    return render_template('legal/terms.html')

@main_bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

# API endpoints for anti-cheat monitoring
@main_bp.route('/api/anti-cheat/log', methods=['POST'])
@login_required
def log_anti_cheat_violation():
    """Log anti-cheat violation"""
    data = request.get_json()
    
    test_result_id = data.get('test_result_id')
    violation_type = data.get('violation_type')
    description = data.get('description', '')
    
    if test_result_id and violation_type:
        from models import AntiCheatLog
        log_entry = AntiCheatLog(
            test_result_id=test_result_id,
            violation_type=violation_type,
            description=description,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        
        db.session.add(log_entry)
        db.session.commit()
        
        return jsonify({'status': 'success'})
    
    return jsonify({'status': 'error', 'message': 'Invalid data'}), 400

@main_bp.route('/api/test/heartbeat', methods=['POST'])
@login_required
def test_heartbeat():
    """Heartbeat endpoint for active test monitoring"""
    data = request.get_json()
    test_result_id = data.get('test_result_id')
    
    if test_result_id:
        # Update last activity timestamp
        test_result = TestResult.query.get(test_result_id)
        if test_result and test_result.application.jobseeker_id == current_user.jobseeker_profile.id:
            # You could store last_activity timestamp if needed
            return jsonify({'status': 'success'})
    
    return jsonify({'status': 'error'}), 400
