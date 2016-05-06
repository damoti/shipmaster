from django.conf.urls import url
from django.views.decorators.csrf import csrf_exempt
from . import views

urlpatterns = [

    url(r"^$", views.Dashboard.as_view(), name="dashboard"),
    url(r"^settings$", views.ViewSettings.as_view(), name="settings"),

    url(r"^create-repository$", views.CreateRepository.as_view(), name="repository.create"),

    url(r"^repository/(?P<repo>[\w\.\-]+)/$", views.ViewRepository.as_view(), name="repository"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/pull$", csrf_exempt(views.PullRequest.as_view()), name="repository.pull"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/$", views.ViewBuild.as_view(), name="build.view"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/start$", views.StartJob.as_view(), name="job.start"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/job/(?P<job>\d+)/$", views.ViewJob.as_view(), name="job.view"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/job/(?P<job>\d+)/deploy$", views.DeployJob.as_view(), name="job.deploy"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/job/(?P<job>\d+)/output$", views.ViewJobOutput.as_view(), name="job.output"),

]
