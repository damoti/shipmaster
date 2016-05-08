from channels.routing import route

channel_routing = [
    route("build-app", "shipmaster.server.consumers.build_app"),
    route("run-test", "shipmaster.server.consumers.run_test")
]
