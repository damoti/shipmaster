from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import ugettext_lazy as _
from .models import Repository


class RepositoryForm(forms.Form):
    name = forms.CharField()
    git = forms.CharField(validators=[
        RegexValidator(Repository.GIT_REGEX, _('Git repository must match: '+Repository.GIT_REGEX))])

    def __init__(self, *args, shipmaster=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.shipmaster = shipmaster

    def clean_name(self):
        name = self.cleaned_data['name']
        if Repository(self.shipmaster, name).exists():
            raise ValidationError(
                _('%(name)s already exists'),
                params={'name': name},
            )
        return name
