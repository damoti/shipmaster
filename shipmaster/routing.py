from channels.channel import Channel
from channels.routing import route

build_app = Channel("build_app")
deploy_app = Channel("deploy_app")

channel_routing = [
    route(c.name, "shipmaster.consumers."+c.name) for c in [
        build_app,
        deploy_app
    ]
]
