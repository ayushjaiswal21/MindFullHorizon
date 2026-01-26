# Patch for app.py to fix file upload issues
# Add this code to your app.py file or import from file_upload_fix.py

import os
import magic
from werkzeug.utils import secure_filename
from PIL import Image
import uuid
import logging

logger = logging.getLogger(__name__)

# Add these functions to your app.py file:

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
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'wav', 'mp3', 'ogg'}
        if not ('.' in file.filename and 
                file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            return False, f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
        
        # Get file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer
        
        # Check file size (16MB max)
        max_size = 16 * 1024 * 1024
        if file_size > max_size:
            return False, f"File too large. Maximum size: {max_size // (1024*1024)}MB"
        
        # Check for malicious content in filename
        if any(char in file.filename for char in ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']):
            return False, "Invalid characters in filename"
        
        return True, "File validation successful"
        
    except Exception as e:
        logger.error(f"Error during file validation: {e}")
        return False, f"File validation error: {str(e)}"

def allowed_file(filename):
    """Check if file extension is allowed"""
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'wav', 'mp3', 'ogg'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

# Alternative simpler validation function if the above doesn't work:
def simple_file_validation(file):
    """Simple file validation as fallback"""
    if not file or not file.filename:
        return False, "No file selected"
    
    if not allowed_file(file.filename):
        return False, "File type not allowed"
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > 16 * 1024 * 1024:  # 16MB
        return False, "File too large"
    
    return True, "Valid file"

# Instructions for fixing your app.py:
"""
1. Add the above functions to your app.py file after the imports section
2. Or import them from file_upload_fix.py by adding this line:
   from file_upload_fix import validate_file_security, allowed_file

3. Make sure your upload folder exists and has proper permissions:
   os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

4. Check that your form has the correct enctype:
   <form enctype="multipart/form-data" method="POST">

5. Verify your HTML form field name matches what you're checking in the backend:
   <input type="file" name="profile_pic" accept="image/*">
"""