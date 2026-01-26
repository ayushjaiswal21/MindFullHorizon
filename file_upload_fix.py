# File Upload Fix for MindFull Horizon
# This file contains the missing file validation functions and improved upload handling

import os
import magic
import hashlib
from werkzeug.utils import secure_filename
from PIL import Image
import uuid
import logging

logger = logging.getLogger(__name__)

# File upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'wav', 'mp3', 'ogg', 'pdf', 'doc', 'docx'}
ALLOWED_MIME_TYPES = {
    'image/png', 'image/jpeg', 'image/jpg', 'image/gif',
    'audio/wav', 'audio/mpeg', 'audio/ogg', 'audio/mp4',
    'application/pdf', 'application/msword', 
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
}

MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB
MAX_IMAGE_SIZE = 5 * 1024 * 1024   # 5MB for images
MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10MB for audio

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    """Determine file type based on extension"""
    if not filename or '.' not in filename:
        return 'unknown'
    
    ext = filename.rsplit('.', 1)[1].lower()
    
    if ext in {'png', 'jpg', 'jpeg', 'gif'}:
        return 'image'
    elif ext in {'wav', 'mp3', 'ogg'}:
        return 'audio'
    elif ext in {'pdf', 'doc', 'docx'}:
        return 'document'
    else:
        return 'unknown'

def validate_file_security(file):
    """
    Comprehensive file validation for security and compatibility
    Returns: (is_valid: bool, error_message: str)
    """
    try:
        # Check if file exists
        if not file or not file.filename:
            return False, "No file selected"
        
        # Check file extension
        if not allowed_file(file.filename):
            return False, f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        
        # Get file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer
        
        # Check file size limits
        file_type = get_file_type(file.filename)
        if file_type == 'image' and file_size > MAX_IMAGE_SIZE:
            return False, f"Image file too large. Maximum size: {MAX_IMAGE_SIZE // (1024*1024)}MB"
        elif file_type == 'audio' and file_size > MAX_AUDIO_SIZE:
            return False, f"Audio file too large. Maximum size: {MAX_AUDIO_SIZE // (1024*1024)}MB"
        elif file_size > MAX_FILE_SIZE:
            return False, f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
        
        # Check MIME type using python-magic (more secure than trusting headers)
        try:
            file_content = file.read(1024)  # Read first 1KB for magic number detection
            file.seek(0)  # Reset file pointer
            
            mime_type = magic.from_buffer(file_content, mime=True)
            
            if mime_type not in ALLOWED_MIME_TYPES:
                return False, f"Invalid file type detected: {mime_type}"
                
        except Exception as e:
            logger.warning(f"Could not detect MIME type, falling back to extension check: {e}")
            # If magic fails, rely on extension check (already done above)
        
        # Additional validation for images
        if file_type == 'image':
            try:
                file.seek(0)
                with Image.open(file) as img:
                    # Check image dimensions (prevent extremely large images)
                    if img.width > 4000 or img.height > 4000:
                        return False, "Image dimensions too large. Maximum: 4000x4000 pixels"
                    
                    # Verify image format matches extension
                    expected_format = file.filename.rsplit('.', 1)[1].upper()
                    if expected_format == 'JPG':
                        expected_format = 'JPEG'
                    
                    if img.format != expected_format:
                        return False, f"Image format mismatch. Expected: {expected_format}, Got: {img.format}"
                
                file.seek(0)  # Reset for actual saving
                
            except Exception as e:
                return False, f"Invalid or corrupted image file: {str(e)}"
        
        # Check for malicious content in filename
        if any(char in file.filename for char in ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']):
            return False, "Invalid characters in filename"
        
        return True, "File validation successful"
        
    except Exception as e:
        logger.error(f"Error during file validation: {e}")
        return False, f"File validation error: {str(e)}"

def save_uploaded_file(file, upload_folder, prefix=""):
    """
    Safely save uploaded file with security measures
    Returns: (success: bool, filename: str, error_message: str)
    """
    try:
        # Validate file first
        is_valid, error_message = validate_file_security(file)
        if not is_valid:
            return False, None, error_message
        
        # Generate secure filename
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        
        # Create unique filename to prevent conflicts
        unique_id = str(uuid.uuid4())
        if prefix:
            new_filename = f"{prefix}_{unique_id}.{file_extension}"
        else:
            new_filename = f"{unique_id}_{original_filename}"
        
        # Ensure upload directory exists
        os.makedirs(upload_folder, exist_ok=True)
        
        # Create full file path
        file_path = os.path.join(upload_folder, new_filename)
        
        # Security check: ensure path is within upload folder
        if not os.path.abspath(file_path).startswith(os.path.abspath(upload_folder)):
            return False, None, "Invalid file path detected"
        
        # Save the file
        file.save(file_path)
        
        # Verify file was saved correctly
        if not os.path.exists(file_path):
            return False, None, "File save failed"
        
        # Additional security: verify file size matches
        saved_size = os.path.getsize(file_path)
        file.seek(0, os.SEEK_END)
        original_size = file.tell()
        
        if saved_size != original_size:
            os.remove(file_path)  # Clean up
            return False, None, "File corruption detected during save"
        
        logger.info(f"File uploaded successfully: {new_filename}")
        return True, new_filename, "File uploaded successfully"
        
    except Exception as e:
        logger.error(f"Error saving uploaded file: {e}")
        return False, None, f"Upload error: {str(e)}"

def delete_uploaded_file(filename, upload_folder):
    """
    Safely delete uploaded file
    Returns: (success: bool, error_message: str)
    """
    try:
        if not filename:
            return False, "No filename provided"
        
        file_path = os.path.join(upload_folder, filename)
        
        # Security check: ensure path is within upload folder
        if not os.path.abspath(file_path).startswith(os.path.abspath(upload_folder)):
            return False, "Invalid file path"
        
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"File deleted successfully: {filename}")
            return True, "File deleted successfully"
        else:
            return False, "File not found"
            
    except Exception as e:
        logger.error(f"Error deleting file {filename}: {e}")
        return False, f"Delete error: {str(e)}"

def get_file_hash(file_path):
    """Generate SHA-256 hash of file for integrity checking"""
    try:
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        logger.error(f"Error generating file hash: {e}")
        return None

def compress_image(file_path, max_size_kb=500, quality=85):
    """
    Compress image file to reduce size while maintaining quality
    Returns: (success: bool, new_size: int, error_message: str)
    """
    try:
        with Image.open(file_path) as img:
            # Convert to RGB if necessary (for JPEG compatibility)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Calculate new dimensions if image is too large
            max_dimension = 1920  # Max width or height
            if img.width > max_dimension or img.height > max_dimension:
                ratio = min(max_dimension / img.width, max_dimension / img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Save with compression
            img.save(file_path, optimize=True, quality=quality)
            
            # Check if file size is acceptable
            new_size = os.path.getsize(file_path)
            if new_size > max_size_kb * 1024:
                # Try with lower quality
                if quality > 60:
                    return compress_image(file_path, max_size_kb, quality - 10)
                else:
                    return False, new_size, f"Could not compress image below {max_size_kb}KB"
            
            return True, new_size, "Image compressed successfully"
            
    except Exception as e:
        logger.error(f"Error compressing image: {e}")
        return False, 0, f"Compression error: {str(e)}"

# Flask route helpers
def handle_file_upload(request, field_name, upload_folder, prefix="", compress_images=True):
    """
    Complete file upload handler for Flask routes
    Returns: (success: bool, filename: str, error_message: str)
    """
    try:
        if field_name not in request.files:
            return False, None, "No file field in request"
        
        file = request.files[field_name]
        
        if not file or file.filename == '':
            return False, None, "No file selected"
        
        # Save the file
        success, filename, error_msg = save_uploaded_file(file, upload_folder, prefix)
        
        if success and compress_images and get_file_type(filename) == 'image':
            # Compress image if it's an image file
            file_path = os.path.join(upload_folder, filename)
            compress_success, new_size, compress_msg = compress_image(file_path)
            
            if not compress_success:
                logger.warning(f"Image compression failed: {compress_msg}")
                # Don't fail the upload, just log the warning
        
        return success, filename, error_msg
        
    except Exception as e:
        logger.error(f"Error in file upload handler: {e}")
        return False, None, f"Upload handler error: {str(e)}"

# Example usage in Flask routes:
"""
from file_upload_fix import handle_file_upload, validate_file_security

@app.route('/upload', methods=['POST'])
def upload_file():
    success, filename, error_msg = handle_file_upload(
        request, 
        'profile_pic', 
        app.config['UPLOAD_FOLDER'], 
        prefix='profile',
        compress_images=True
    )
    
    if success:
        # Update user profile with new filename
        current_user.profile_picture = filename
        db.session.commit()
        flash('File uploaded successfully!', 'success')
    else:
        flash(f'Upload failed: {error_msg}', 'error')
    
    return redirect(url_for('profile'))
"""