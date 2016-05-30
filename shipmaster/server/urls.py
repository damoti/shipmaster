from django.conf.urls import url
from django.views.decorators.csrf import csrf_exempt
from . import views

urlpatterns = [

    url(r"^$", views.Dashboard.as_view(), name="dashboard"),
    url(r"^settings$", views.ViewSettings.as_view(), name="settings"),

    url(r"^create-repository$", views.CreateRepository.as_view(), name="repository.create"),

    url(r"^repository/(?P<repo>[\w\.\-]+)/view$", views.ViewRepository.as_view(), name="repository"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/pull$", csrf_exempt(views.PullRequest.as_view()), name="repository.pull"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/view$", views.ViewBuild.as_view(), name="build.view"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/log$", views.ViewBuildLog.as_view(), name="build.log"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/deploy/(?P<service>[\w\.\-]+)$", views.DeployBuild.as_view(), name="build.deploy"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/deployment/log$", views.ViewDeploymentLog.as_view(), name="build.deployment.log"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/start$", views.StartJob.as_view(), name="job.start"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/job/(?P<job>\d+)/view$", views.ViewJob.as_view(), name="job.view"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/job/(?P<job>\d+)/output$", views.ViewJobLog.as_view(), name="job.output"),

]
