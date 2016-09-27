from channels import route_class
from .logserver import LogSubscriptionConsumer

channel_routing = [
    route_class(LogSubscriptionConsumer, path=r"^/log/(?P<path>.+)"),
]
