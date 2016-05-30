from django.contrib import auth
from django.contrib.auth import load_backend
from django.core.exceptions import ImproperlyConfigured
from .models import Shipmaster, Repository, Infrastructure, Build, Job
from .auth import AccessTokenUserBackend


class ShipmasterMiddleware:

    def process_view(self, request, view, args, kwargs):
        request.shipmaster = Shipmaster('/var/lib/shipmaster')
        request.infrastructure = request.shipmaster.infrastructure
        request.current_repo = None
        request.current_build = None
        request.current_job = None
        if 'repo' in kwargs:
            if kwargs['repo'] == 'infrastructure':
                request.current_repo = request.infrastructure
            else:
                request.current_repo = Repository.load(request.shipmaster, kwargs['repo'])
            if 'build' in kwargs:
                request.current_build = Build.load(request.current_repo, kwargs['build'])
                if 'job' in kwargs:
                    request.current_job = Job.load(request.current_build, kwargs['job'])

    def process_template_response(self, request, response):
        if hasattr(response, 'context_data'):
            response.context_data['shipmaster'] = request.shipmaster
            response.context_data['infrastructure'] = request.infrastructure
            response.context_data['current_repo'] = request.current_repo
            response.context_data['current_build'] = request.current_build
            response.context_data['current_job'] = request.current_job
        return response


class AccessTokenUserMiddleware(object):

    def process_request(self, request):
        # AuthenticationMiddleware is required so that request.user exists.
        if not hasattr(request, 'user'):
            raise ImproperlyConfigured(
                "The Django remote user auth middleware requires the"
                " authentication middleware to be installed.  Edit your"
                " MIDDLEWARE_CLASSES setting to insert"
                " 'django.contrib.auth.middleware.AuthenticationMiddleware'"
                " before the AccessTokenUserMiddleware class.")
        try:
            username = request.META["REMOTE_USER"]
            access_token = request.META["HTTP_X_FORWARDED_ACCESS_TOKEN"]
        except KeyError:
            # If specified header doesn't exist then remove any existing
            # authenticated remote-user, or return (leaving request.user set to
            # AnonymousUser by the AuthenticationMiddleware).
            if request.user.is_authenticated():
                self._remove_invalid_user(request)
            return
        # If the user is already authenticated and that user is the user we are
        # getting passed in the headers, then the correct user is already
        # persisted in the session and we don't need to continue.
        if request.user.is_authenticated():
            if request.user.get_username() == self.clean_username(username, request):
                return
            else:
                # An authenticated user is associated with the request, but
                # it does not match the authorized user in the header.
                self._remove_invalid_user(request)

        # We are seeing this user for the first time in this session, attempt
        # to authenticate the user.
        user = auth.authenticate(remote_user=username, access_token=access_token)
        if user:
            # User is valid.  Set request.user and persist user in the session
            # by logging the user in.
            request.user = user
            auth.login(request, user)

    def clean_username(self, username, request):
        """
        Allows the backend to clean the username, if the backend defines a
        clean_username method.
        """
        backend_str = request.session[auth.BACKEND_SESSION_KEY]
        backend = auth.load_backend(backend_str)
        try:
            username = backend.clean_username(username)
        except AttributeError:  # Backend has no clean_username method.
            pass
        return username

    def _remove_invalid_user(self, request):
        """
        Removes the current authenticated user in the request which is invalid
        but only if the user is authenticated via the RemoteUserBackend.
        """
        try:
            stored_backend = load_backend(request.session.get(auth.BACKEND_SESSION_KEY, ''))
        except ImportError:
            # backend failed to load
            auth.logout(request)
        else:
            if isinstance(stored_backend, AccessTokenUserBackend):
                auth.logout(request)
