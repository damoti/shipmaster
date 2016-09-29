from requests_oauthlib import OAuth2Session
from oauthlib.oauth2.rfc6749.errors import MismatchingStateError
from django.views.generic import View
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.conf import settings
from django.contrib.auth import login

from .user import User


class GitHub(View):
    SESSION_STATE = 'GITHUB_STATE'
    BASE_URL = 'https://github.com/login/oauth/authorize'
    TOKEN_URL = 'https://github.com/login/oauth/access_token'


class GitHubLogin(GitHub):

    def get(self, request, *args, **kwargs):
        github = OAuth2Session(settings.OAUTH_KEY)
        authorization_url, state = github.authorization_url(self.BASE_URL)
        request.session[self.SESSION_STATE] = state
        return HttpResponseRedirect(authorization_url)


class GitHubAuthorized(GitHub):

    def get(self, request, *args, **kwargs):
        state = request.session[self.SESSION_STATE]
        github = OAuth2Session(settings.OAUTH_KEY, state=state)

        if state != request.GET['state']:
            raise MismatchingStateError()

        github.fetch_token(
            self.TOKEN_URL,
            code=request.GET['code'],
            client_secret=settings.OAUTH_SECRET
        )

        data = github.get('https://api.github.com/user').json()

        if not data['login']:
            raise AttributeError('Username not provided by GitHub during authorization.')

        user, created = User.objects.get_or_create(username=data['login'])
        user.name = data.get('name') or ''
        user.email = data.get('email') or ''
        user.avatar = data.get('avatar_url') or ''
        user.json = data
        user.save()

        login(request, user)

        return HttpResponseRedirect(reverse('dashboard'))


class GitHubEvent(GitHub):

    def get(self, request, *args, **kwargs):
        state = request.session[self.SESSION_STATE]
        github = OAuth2Session(settings.OAUTH_KEY, state=state)

        github.fetch_token(
            self.TOKEN_URL,
            client_secret=settings.OAUTH_SECRET,
            authorization_response=request.url
        )

        data = github.get('https://api.github.com/user').json()

        user = User.get_or_create(username=data['login'])
        user.name = data['name']
        user.email = data['email']
        user.avatar = data['avatar_url']
        user.json = data
        user.save()

        login(request, user)

        return HttpResponseRedirect(reverse('dashboard'))


class UrlPatterns:
    urlpatterns = [
    ]
urls = UrlPatterns()
