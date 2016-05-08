from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import ugettext_lazy as _
from .models import Repository


def repository_name_validator(name):
    if Repository(name).exists():
        raise ValidationError(
            _('%(name)s already exists'),
            params={'name': name},
        )


class RepositoryForm(forms.Form):
    name = forms.CharField(validators=[repository_name_validator])
    git = forms.CharField(validators=[
        RegexValidator(Repository.GIT_REGEX, _('Git repository must match: '+Repository.GIT_REGEX))])
