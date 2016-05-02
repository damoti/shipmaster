from compose.project import Project
from compose.cli.main import log_printer_from_project, filter_containers_to_service_names


def up(conf, client):
    project = Project.from_config(conf.name, conf.services.compose, client)
    to_attach = project.up(conf.services.names)
    print(conf.services.compose)

    log_printer = log_printer_from_project(
        project,
        filter_containers_to_service_names(to_attach, ['app']),
        False,
        {'follow': True},
        True,
        event_stream=project.events(service_names=conf.services.names))
    log_printer.run()

