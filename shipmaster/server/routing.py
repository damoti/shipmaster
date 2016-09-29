from channels import route, route_class
from channels.staticfiles import StaticFilesConsumer
from .logserver import LogSubscriptionConsumer

channel_routing = [
    route('http.request', StaticFilesConsumer()),
    route_class(LogSubscriptionConsumer, path=r"^/log(?P<path>.+)"),
]
