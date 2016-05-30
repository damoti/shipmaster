import io
import time
from subprocess import CalledProcessError
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http import StreamingHttpResponse
from django.http import FileResponse
from django.views.generic import View, TemplateView, FormView
from django.core.urlresolvers import reverse

from docker import Client

from .models import Repository, Build, Job
from .forms import RepositoryForm


class Dashboard(TemplateView):
    template_name = "shipmaster/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        client = Client('unix://var/run/docker.sock')
        context['containers'] = client.containers()
        return context


class ViewCodeRepository(TemplateView):
    template_name = "shipmaster/repository.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        return context


class ViewInfrastructureRepository(TemplateView):
    template_name = "shipmaster/infrastructure.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        return context


class ViewRepository(View):
    def dispatch(self, request, *args, **kwargs):
        if self.request.current_repo.is_infrastructure:
            view = ViewInfrastructureRepository.as_view()
        else:
            view = ViewCodeRepository.as_view()
        return view(request, *args, **kwargs)


class CreateRepository(FormView):
    template_name = "shipmaster/repository_form.html"
    form_class = RepositoryForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'shipmaster': self.request.shipmaster
        })
        return kwargs

    def form_valid(self, form):
        try:
            repo = Repository.create(shipmaster=self.request.shipmaster, **form.cleaned_data)
        except CalledProcessError as err:
            form.add_error(None, err.output)
            return super().form_invalid(form)
        else:
            return HttpResponseRedirect(reverse('repository', args=[repo.name]))


class PullRequest(View):

    def pull(self, repo):
        if repo.is_infrastructure:
            repo.sync()
            return HttpResponseRedirect(reverse('repository', args=[repo.name]))
        else:
            build = Build.create(repo, 'dev')
            build.build()
            return HttpResponseRedirect(reverse('build.view', args=[repo.name, build.number]))

    def post(self, request, *args, **kwargs):
        repo = request.current_repo
        try:
            self.pull(repo)
        except:
            return HttpResponse('FAILED')
        else:
            return HttpResponse('OK')

    def get(self, request, *args, **kwargs):
        return self.pull(request.current_repo)


class ViewBuild(TemplateView):

    template_name = "shipmaster/build.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        return context


class ViewLog(View):

    def get(self, request, *args, **kwargs):
        try:
            def streamer(path):
                with open(path, 'r') as file:
                    waited = 0
                    while True:
                        line = file.readline()
                        if line != "":
                            waited = 0
                            yield "data: {}\n\n".format(line).encode('utf-8')
                        else:
                            waited += 1
                            if waited == 10:
                                yield "data: closed\n\n".encode('utf-8')
                                break
                            time.sleep(2)

            response = StreamingHttpResponse(streamer(self.get_log_path(request)), content_type="text/event-stream")
            #response.block_size = 128
            #response['Cache-Control'] = 'no-cache'
            #response['X-Accel-Buffering'] = 'no'
            return response
        except CalledProcessError as err:
            return HttpResponse(err.output)

    def get_log_path(self, request):
        raise NotImplementedError


class ViewBuildLog(ViewLog):
    def get_log_path(self, request):
        build = request.current_build
        return build.path.build_log


class ViewDeploymentLog(ViewLog):
    def get_log_path(self, request):
        build = request.current_build
        return build.path.deployment_log


class DeployBuild(View):

    def get(self, request, *args, **kwargs):
        repo = request.current_repo
        build = request.current_build
        build.deploy(kwargs['service'])
        return HttpResponseRedirect(reverse('build.view', args=[repo.name, build.number]))


class StartJob(View):

    def get(self, request, *args, **kwargs):
        repo = request.current_repo
        build = request.current_build
        job = Job.create(build)
        job.test()
        return HttpResponseRedirect(reverse('job.view', args=[repo.name, build.number, job.number]))


class ViewJob(TemplateView):

    template_name = "shipmaster/job.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        return context


class ViewJobLog(ViewLog):
    def get_log_path(self, request):
        job = request.current_job
        return job.path.log


class ViewSettings(TemplateView):

    template_name = "shipmaster/settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        return context
