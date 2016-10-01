from .models import Shipmaster, Repository, Build, Deployment, Test


class ShipmasterMiddleware:

    @staticmethod
    def process_view(request, view, args, kwargs):
        request.shipmaster = Shipmaster.from_path('/var/lib/shipmaster')
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
                if 'test' in kwargs:
                    request.current_job = Test.load(request.current_build, kwargs['test'])
                if 'deployment' in kwargs:
                    request.current_job = Deployment.load(request.current_build, kwargs['deployment'])

    @staticmethod
    def process_template_response(request, response):
        if hasattr(response, 'context_data'):
            response.context_data['shipmaster'] = request.shipmaster
            response.context_data['infrastructure'] = request.infrastructure
            response.context_data['current_repo'] = request.current_repo
            response.context_data['current_build'] = request.current_build
            response.context_data['current_job'] = request.current_job
        return response
