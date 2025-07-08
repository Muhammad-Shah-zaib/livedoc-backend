from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone

from .managers import CustomUserManager

class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(("email address"), unique=True)
    first_name = models.CharField("First Name", max_length=150, null=False, blank=False)
    last_name = models.CharField("Last Name", max_length=150, blank=True)
    is_email_verified = models.BooleanField("Email Verified", default=False)
    is_oauth_verified = models.BooleanField("OAuth Verified", default=False)
    is_staff = models.BooleanField("is staff", default=False)
    is_active = models.BooleanField("is active", default=True)
    date_joined = models.DateTimeField("date joined", default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name"]

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.id}: {self.first_name} {self.last_name} <{self.email}>"


