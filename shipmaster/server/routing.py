from channels import route_class
from .consumers import LogsServer

channel_routing = [
    route_class(LogsServer, path=r"^/log/(?P<path>.+)"),
]