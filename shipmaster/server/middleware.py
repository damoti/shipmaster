from django.contrib.auth.backends import RemoteUserBackend
from .models import Shipmaster, Repository, Build, Job


class ShipmasterMiddleware:

    def process_view(self, request, view, args, kwargs):
        request.shipmaster = Shipmaster('/var/lib/shipmaster')
        request.current_repo = None
        request.current_build = None
        request.current_job = None
        if 'repo' in kwargs:
            request.current_repo = Repository.load(request.shipmaster, kwargs['repo'])
            if 'build' in kwargs:
                request.current_build = Build.load(request.current_repo, kwargs['build'])
                if 'job' in kwargs:
                    request.current_job = Job.load(request.current_build, kwargs['job'])

    def process_template_response(self, request, response):
        if hasattr(response, 'context_data'):
            response.context_data['shipmaster'] = request.shipmaster
            response.context_data['current_repo'] = request.current_repo
            response.context_data['current_build'] = request.current_build
            response.context_data['current_job'] = request.current_job
        return response


class AccessTokenUserMiddleware(RemoteUserBackend):
    header = "HTTP_X_FORWARDED_ACCESS_TOKEN"
