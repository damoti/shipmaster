from django.conf.urls import url
from django.views.decorators.csrf import csrf_exempt
from . import views

urlpatterns = [

    url(r"^$", views.Dashboard.as_view(), name="dashboard"),
    url(r"^settings$", views.SettingsView.as_view(), name="settings"),

    url(r"^create-repository$", views.CreateRepository.as_view(), name="repository.create"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/$", views.RepositoryView.as_view(), name="repository"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/pull$", csrf_exempt(views.StartBuild.as_view()), name="build.start"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/$", views.BuildView.as_view(), name="build"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/start-test$", views.StartTest.as_view(), name="test.start"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/test/(?P<test>\d+)/$", views.TestView.as_view(), name="test"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/start-deployment/(?P<destination>[\w\.\-]+)$", views.StartDeployment.as_view(), name="deployment.start"),
    url(r"^repository/(?P<repo>[\w\.\-]+)/build/(?P<build>\d+)/deployment/(?P<deployment>\d+)/$", views.DeploymentView.as_view(), name="deployment"),

]
