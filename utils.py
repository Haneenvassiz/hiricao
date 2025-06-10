import os
import uuid
import mimetypes
from werkzeug.utils import secure_filename
from flask import current_app
from PIL import Image
import hashlib
from datetime import datetime

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    'resume': {'pdf', 'doc', 'docx'},
    'image': {'png', 'jpg', 'jpeg', 'gif'},
    'project': {'zip', 'rar', '7z', 'tar', 'gz'},
    'document': {'pdf', 'doc', 'docx', 'txt', 'rtf'}
}

def allowed_file(filename, file_type='resume'):
    """Check if file extension is allowed"""
    if not filename:
        return False
    
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS.get(file_type, set())

def get_file_extension(filename):
    """Get file extension"""
    if not filename:
        return ''
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

def generate_unique_filename(original_filename):
    """Generate unique filename while preserving extension"""
    if not original_filename:
        return str(uuid.uuid4())
    
    name, ext = os.path.splitext(secure_filename(original_filename))
    unique_name = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
    return unique_name

def save_uploaded_file(file, subfolder=''):
    """Save uploaded file and return filename"""
    try:
        if not file or not file.filename:
            return None
        
        # Generate unique filename
        filename = generate_unique_filename(file.filename)
        
        # Create upload directory
        upload_dir = current_app.config['UPLOAD_FOLDER']
        if subfolder:
            upload_dir = os.path.join(upload_dir, subfolder)
        
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save file
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)
        
        # Return relative path for database storage
        if subfolder:
            return os.path.join(subfolder, filename)
        return filename
        
    except Exception as e:
        current_app.logger.error(f"Error saving file: {str(e)}")
        return None

def get_file_size(file_path):
    """Get file size in bytes"""
    try:
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file_path)
        return os.path.getsize(full_path)
    except:
        return 0

def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def validate_image(file_path):
    """Validate if file is a valid image"""
    try:
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file_path)
        with Image.open(full_path) as img:
            img.verify()
        return True
    except:
        return False

def create_thumbnail(image_path, size=(150, 150)):
    """Create thumbnail for image"""
    try:
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image_path)
        
        with Image.open(full_path) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Create thumbnail filename
            name, ext = os.path.splitext(image_path)
            thumbnail_path = f"{name}_thumb{ext}"
            thumbnail_full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], thumbnail_path)
            
            img.save(thumbnail_full_path)
            return thumbnail_path
            
    except Exception as e:
        current_app.logger.error(f"Error creating thumbnail: {str(e)}")
        return None

def calculate_file_hash(file_path):
    """Calculate SHA-256 hash of file"""
    try:
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file_path)
        hash_sha256 = hashlib.sha256()
        
        with open(full_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        
        return hash_sha256.hexdigest()
        
    except Exception as e:
        current_app.logger.error(f"Error calculating file hash: {str(e)}")
        return None

def sanitize_filename(filename):
    """Sanitize filename for safe storage"""
    if not filename:
        return 'unnamed_file'
    
    # Remove or replace dangerous characters
    filename = secure_filename(filename)
    
    # Limit length
    name, ext = os.path.splitext(filename)
    if len(name) > 50:
        name = name[:50]
    
    return f"{name}{ext}"

def get_mime_type(filename):
    """Get MIME type for file"""
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or 'application/octet-stream'

def format_datetime(dt, format_str='%Y-%m-%d %H:%M'):
    """Format datetime for display"""
    if not dt:
        return ''
    return dt.strftime(format_str)

def time_ago(dt):
    """Get human-friendly time ago string"""
    if not dt:
        return ''
    
    now = datetime.utcnow()
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "Just now"

def truncate_text(text, length=100, suffix='...'):
    """Truncate text to specified length"""
    if not text:
        return ''
    
    if len(text) <= length:
        return text
    
    return text[:length - len(suffix)] + suffix

def generate_slug(title):
    """Generate URL-friendly slug from title"""
    if not title:
        return ''
    
    import re
    
    # Convert to lowercase and replace spaces with hyphens
    slug = title.lower().replace(' ', '-')
    
    # Remove special characters
    slug = re.sub(r'[^a-z0-9\-]', '', slug)
    
    # Remove multiple consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    
    return slug or 'untitled'

def validate_email_domain(email):
    """Validate email domain (basic check)"""
    if not email or '@' not in email:
        return False
    
    domain = email.split('@')[1]
    
    # Basic domain validation
    if '.' not in domain:
        return False
    
    # You could add more sophisticated domain validation here
    return True

def clean_phone_number(phone):
    """Clean and format phone number"""
    if not phone:
        return ''
    
    # Remove all non-digit characters
    digits = ''.join(filter(str.isdigit, phone))
    
    # Format based on length
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    else:
        return phone  # Return original if can't format

def is_safe_url(target):
    """Check if URL is safe for redirect"""
    if not target:
        return False
    
    # Basic URL safety check
    return target.startswith('/') and not target.startswith('//')

def paginate_query(query, page, per_page=20):
    """Helper function for pagination"""
    try:
        return query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
    except Exception as e:
        current_app.logger.error(f"Pagination error: {str(e)}")
        return None

def get_user_ip():
    """Get user's IP address"""
    from flask import request
    
    # Check for forwarded IP first (for reverse proxies)
    if 'X-Forwarded-For' in request.headers:
        return request.headers['X-Forwarded-For'].split(',')[0].strip()
    elif 'X-Real-IP' in request.headers:
        return request.headers['X-Real-IP']
    else:
        return request.remote_addr

def mask_sensitive_data(data, fields=['password', 'token', 'key']):
    """Mask sensitive data in logs"""
    if isinstance(data, dict):
        masked = {}
        for key, value in data.items():
            if any(field in key.lower() for field in fields):
                masked[key] = '*' * len(str(value)) if value else value
            else:
                masked[key] = mask_sensitive_data(value, fields)
        return masked
    elif isinstance(data, list):
        return [mask_sensitive_data(item, fields) for item in data]
    else:
        return data

def generate_random_string(length=32):
    """Generate random string for tokens"""
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def validate_json(json_string):
    """Validate if string is valid JSON"""
    try:
        json.loads(json_string)
        return True
    except:
        return False

class Timer:
    """Context manager for timing operations"""
    
    def __init__(self, description="Operation"):
        self.description = description
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.time()
        duration = end_time - self.start_time
        current_app.logger.info(f"{self.description} took {duration:.2f} seconds")
