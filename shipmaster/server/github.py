from requests_oauthlib import OAuth2Session
from django_github_webhook.views import WebHookView
from oauthlib.oauth2.rfc6749.errors import MismatchingStateError
from django.views.generic import View
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.conf import settings
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied

from .models import Repository, Build
from .user import User


class GitHub(View):
    SESSION_STATE = 'GITHUB_STATE'
    AUTH_URL = 'https://github.com/login/oauth/authorize'
    TOKEN_URL = 'https://github.com/login/oauth/access_token'
    SCOPE = ','.join([
        'admin:org_hook',
        'read:org',
        'repo',
        'user:email',
    ])

    _BASE = 'https://api.github.com/'
    USER_URL = _BASE+'user'
    MEMBER_URL = _BASE+'orgs/{org}/members/{username}'

    def get_oauth2_session(self, **kwargs):
        return OAuth2Session(settings.OAUTH_KEY, scope=self.SCOPE, **kwargs)

    def get_member_url(self, username):
        return self.MEMBER_URL.format(org=settings.GITHUB_ORG, username=username)


class GitHubLogin(GitHub):

    def get(self, request, *args, **kwargs):
        github = self.get_oauth2_session()
        authorization_url, state = github.authorization_url(self.AUTH_URL)
        request.session[self.SESSION_STATE] = state
        return HttpResponseRedirect(authorization_url)


class GitHubAuthorized(GitHub):

    def get(self, request, *args, **kwargs):
        state = request.session[self.SESSION_STATE]
        github = self.get_oauth2_session(state=state)

        if state != request.GET['state']:
            raise MismatchingStateError()

        github.fetch_token(
            self.TOKEN_URL,
            code=request.GET['code'],
            client_secret=settings.OAUTH_SECRET,
        )

        data = github.get(self.USER_URL).json()

        if not data['login']:
            raise PermissionDenied(
                'Username not provided by GitHub during authorization.'
            )

        verify = github.get(self.get_member_url(data['login']))
        if verify.status_code != 204:
            raise PermissionDenied(
                "'{}' is not part of the '{}' organization in GitHub.".format(
                    data['login'], settings.GITHUB_ORG
                ))

        user, created = User.objects.get_or_create(username=data['login'])
        user.name = data.get('name') or ''
        user.email = data.get('email') or ''
        user.avatar = data.get('avatar_url') or ''
        user.profile_url = data.get('html_url') or ''
        user.location = data.get('location') or ''
        user.json = data
        user.save()

        login(request, user)

        return HttpResponseRedirect(reverse('dashboard'))


class GitHubEvent(WebHookView):
    secret = settings.WEBHOOK_SECRET

    @staticmethod
    def push(payload, request):
        repo_name = payload['repository']['name']
        branch_name = payload['ref'].split('/')[-1]
        repo = Repository.load(request.shipmaster, repo_name)
        Build.create(repo, branch_name, pull_request=True).build()
        return {'status': 'received'}

