from channels import route_class
from .consumers import LogServer, LogConsumer

channel_routing = [
    route_class(LogServer, path=r"^/logs"),#/(?P<repo>[\w\.\-]+)/(?P<build>\d+)/(?P<log>[\w\.\-]+)"),
    route_class(LogConsumer)
]