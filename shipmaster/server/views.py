from subprocess import CalledProcessError
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.views.generic import View, TemplateView, FormView
from django.core.urlresolvers import reverse

from docker import Client

from .models import Repository, Build, Test, Deployment
from .forms import RepositoryForm


class Dashboard(TemplateView):
    template_name = "shipmaster/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        client = Client('unix://var/run/docker.sock')
        context['containers'] = client.containers()
        return context


class ProjectRepositoryView(TemplateView):
    template_name = "shipmaster/repository.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        return context


class InfrastructureRepositoryView(TemplateView):
    template_name = "shipmaster/infrastructure.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        return context


class RepositoryView(View):
    def dispatch(self, request, *args, **kwargs):
        if self.request.current_repo.is_infrastructure:
            view = InfrastructureRepositoryView.as_view()
        else:
            view = ProjectRepositoryView.as_view()
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


class StartBuild(View):

    def pull(self, repo):
        if repo.is_infrastructure:
            repo.sync()
            return HttpResponseRedirect(reverse('repository', args=[repo.name]))
        else:
            build = Build.create(repo, 'dev').build()
            return HttpResponseRedirect(reverse('build', args=[repo.name, build.number]))

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


class BuildView(TemplateView):
    template_name = "shipmaster/build.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        return context


class StartDeployment(View):

    def get(self, request, *args, **kwargs):
        repo = request.current_repo
        build = request.current_build
        job = Deployment.create(build, kwargs['destination']).deploy()
        return HttpResponseRedirect(reverse('deployment', args=[repo.name, build.number, job.number]))


class DeploymentView(TemplateView):
    template_name = "shipmaster/deployment.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        return context


class StartTest(View):

    def get(self, request, *args, **kwargs):
        repo = request.current_repo
        build = request.current_build
        job = Test.create(build).test()
        return HttpResponseRedirect(reverse('test', args=[repo.name, build.number, job.number]))


class TestView(TemplateView):
    template_name = "shipmaster/job.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        return context


class SettingsView(TemplateView):
    template_name = "shipmaster/settings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        return context
