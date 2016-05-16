from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, UserManager


class User(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(_('username'), max_length=120, unique=True)
    name = models.CharField(_('full name'), max_length=120, blank=True)
    email = models.EmailField(_('email address'), blank=True)
    avatar = models.CharField(_('avatar'), max_length=1024)
    json = models.TextField(_('json'))

    objects = UserManager()

    USERNAME_FIELD = 'username'

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def get_full_name(self):
        return self.name.strip()

    def get_short_name(self):
        return self.get_full_name().split()[0]
