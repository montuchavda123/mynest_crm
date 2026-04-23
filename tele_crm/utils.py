import os
import uuid
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

@deconstructible
class SecureFileUpload:
    def __init__(self, sub_directory):
        self.sub_directory = sub_directory

    def __call__(self, instance, filename):
        ext = filename.split('.')[-1]
        filename = f"{uuid.uuid4()}.{ext}"
        return os.path.join(self.sub_directory, filename)

def validate_file_size(value):
    filesize = value.size
    if filesize > 5 * 1024 * 1024:  # 5MB
        raise ValidationError("The maximum file size that can be uploaded is 5MB")
    return value

def validate_file_extension(value):
    import magic
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png']
    if not ext in valid_extensions:
        raise ValidationError('Unsupported file extension. Allowed: PDF, DOC, DOCX, JPG, PNG')
    
    # Check mime type for better security
    file_content = value.read(2048)
    value.seek(0)
    mime = magic.from_buffer(file_content, mime=True)
    valid_mimes = ['application/pdf', 'application/msword', 
                   'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                   'image/jpeg', 'image/png']
    if mime not in valid_mimes:
        raise ValidationError('Invalid file type detected.')
    return value
