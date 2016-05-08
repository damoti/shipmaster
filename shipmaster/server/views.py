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


class ViewRepository(TemplateView):
    template_name = "shipmaster/repository.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        return context


class CreateRepository(FormView):
    template_name = "shipmaster/repository_form.html"
    form_class = RepositoryForm

    def form_valid(self, form):
        try:
            repo = Repository.create(**form.cleaned_data)
        except CalledProcessError as err:
            form.add_error(None, err.output)
            return super().form_invalid(form)
        else:
            return HttpResponseRedirect(reverse('repository', args=[repo.name]))


class PullRequest(View):

    def post(self, request, *args, **kwargs):
        repo = request.current_repo
        try:
            build = Build.create(repo, 'docker')
            build.build()
        except:
            return HttpResponse('FAILED')
        else:
            return HttpResponse('OK')

    def get(self, request, *args, **kwargs):
        repo = request.current_repo
        try:
            build = Build.create(repo, 'docker')
            build.build()
        except CalledProcessError as err:
            return HttpResponse(err.output)
        else:
            return HttpResponseRedirect(reverse('build.view', args=[repo.name, build.number]))


class ViewBuild(TemplateView):

    template_name = "shipmaster/build.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        return context


class ViewBuildOutput(View):

    def get(self, request, *args, **kwargs):
        build = request.current_build  # type: Build
        try:
            response = FileResponse(open(build.path.log, 'r'), content_type="text/event-stream")
            response.block_size = 128
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            return response
        except CalledProcessError as err:
            return HttpResponse(err.output)


class StartJob(View):

    def get(self, request, *args, **kwargs):
        repo = request.current_repo
        build = request.current_build
        try:
            job = Job.create(build)
            job.start()
        except CalledProcessError as err:
            return HttpResponse(err.output)
        else:
            return HttpResponseRedirect(reverse('job.view', args=[repo.name, build.number, job.number]))


class ViewJob(TemplateView):

    template_name = "shipmaster/job.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        return context


class ViewJobOutput(View):

    def get(self, request, *args, **kwargs):
        try:
            response = StreamingHttpResponse(request.current_job.log(), content_type="text/event-stream")
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            return response
        except CalledProcessError as err:
            return HttpResponse(err.output)


class DeployJob(View):

    def get(self, request, *args, **kwargs):
        repo = request.current_repo
        build = request.current_build
        job = request.current_job
        try:
            job.deploy()
        except CalledProcessError as err:
            return HttpResponse(err.output)
        else:
            return HttpResponseRedirect(reverse('job.view', args=[repo.name, build.number, job.number]))


class ViewSettings(TemplateView):

    template_name = "shipmaster/settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        return context
