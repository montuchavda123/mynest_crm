from django.db import models
from django.contrib.auth.models import AbstractUser
from auditlog.registry import auditlog

class User(AbstractUser):
    ADMIN = 'ADMIN'
    MANAGER = 'MANAGER'
    TELECALLER = 'TELECALLER'
    VIEWER = 'VIEWER'
    
    ROLE_CHOICES = (
        (ADMIN, 'Admin'),
        (MANAGER, 'Manager'),
        (TELECALLER, 'Telecaller'),
        (VIEWER, 'Viewer'),
    )
    
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=TELECALLER)
    phone = models.CharField(max_length=15, blank=True, null=True)
    is_approved = models.BooleanField(default=True)
    google_id = models.CharField(max_length=255, blank=True, null=True, unique=True)

    REQUIRED_FIELDS = ['username']
    USERNAME_FIELD = 'email'

    @property
    def is_admin_role(self):
        return self.role == self.ADMIN

    @property
    def is_manager_role(self):
        return self.role in [self.ADMIN, self.MANAGER]

    @property
    def is_telecaller_role(self):
        return self.role == self.TELECALLER

    def __str__(self):
        return f"{self.email} ({self.role})"

# Register with auditlog
auditlog.register(User)
