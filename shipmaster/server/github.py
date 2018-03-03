from requests_oauthlib import OAuth2Session
from django_github_webhook.views import WebHookView
from oauthlib.oauth2.rfc6749.errors import MismatchingStateError
from django.views.generic import View
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.conf import settings
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied

from shipmaster.base.config import ProjectConf
from .models import Repository, Build
from .user import User


class GitHubBaseView(View):
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


class GitHubLoginView(GitHubBaseView):

    def get(self, request, *args, **kwargs):
        github = self.get_oauth2_session()
        authorization_url, state = github.authorization_url(self.AUTH_URL)
        request.session[self.SESSION_STATE] = state
        return HttpResponseRedirect(authorization_url)


class GitHubAuthorizedView(GitHubBaseView):

    def get(self, request, *args, **kwargs):
        state = request.session[self.SESSION_STATE]
        github = self.get_oauth2_session(state=state)

        if state != request.GET['state']:
            raise MismatchingStateError()

        token = github.fetch_token(
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

        request.shipmaster.set_token_if_empty(token['access_token'])

        return HttpResponseRedirect(reverse('dashboard'))


class GitHubEventView(WebHookView):
    secret = settings.WEBHOOK_SECRET

    def pull_request(self, payload, request):
        if payload['action'] in ['opened', 'synchronize']:
            base = payload['pull_request']['base']
            branch = base['ref'].split('/')[-1]
            sha = base['sha']
            number = payload['number']
            self.maybe_build(
                request, payload['repository']['full_name'],
                branch, sha, number
            )
        return {'status': 'received'}

    def push(self, payload, request):
        branch = payload['ref'].split('/')[-1]
        sha = payload['after']
        self.maybe_build(
            request, payload['repository']['full_name'],
            branch, sha
        )
        return {'status': 'received'}

    @staticmethod
    def maybe_build(request, full_name, branch, sha, pull=None):
        account_name, repo_name = full_name.split('/')

        repo = Repository.load(request.shipmaster, repo_name)
        github = repo.get_github()

        yaml_contents = github.file_contents('.shipmaster.yaml', sha)
        if yaml_contents:
            yaml_src = yaml_contents.decoded.decode('utf-8')
            conf = ProjectConf.from_string(yaml_src)
            if (pull is not None and conf.build.pull_requests) or\
               (pull is None and branch in conf.build.branches):
                Build.create(repo, branch, sha, pull, automated=True).build()
