from django.conf.urls import url, include
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from . import views, github

urlpatterns = [

    # GitHub
    url(r"^login$", github.GitHubLoginView.as_view(), name='login'),
    url(r"^authorized$", github.GitHubAuthorizedView.as_view()),
    url(r"^event$", csrf_exempt(github.GitHubEventView.as_view())),

    # General
    url(r"^$", login_required(views.Dashboard.as_view()), name="dashboard"),
    url(r"^settings$", login_required(views.SettingsView.as_view()), name="settings"),

    # Repositories
    url(r"^create-repository$", login_required(views.CreateRepository.as_view()), name="repository.create"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/$", login_required(views.RepositoryView.as_view()), name="repository"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/start-build$", login_required(views.StartBuild.as_view()), name="build.start"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/$", login_required(views.BuildView.as_view()), name="build"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/start-test$", login_required(views.StartTest.as_view()), name="test.start"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/test/(?P<test>\d+)/$", login_required(views.TestView.as_view()), name="test"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/test/(?P<test>\d+)/reports/(?P<report>.+)?$", login_required(views.TestReports.as_view()), name="test.reports"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/start-deployment/(?P<destination>[\w\.\-]+)$", login_required(views.StartDeployment.as_view()), name="deployment.start"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/deployment/(?P<deployment>\d+)/$", login_required(views.DeploymentView.as_view()), name="deployment"),

]
