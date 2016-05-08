from queue import Queue
from compose.project import Project
from compose.cli.main import log_printer_from_project, filter_containers_to_service_names
from compose.cli.log_printer import build_thread_map, start_producer_thread, consume_queue, remove_stopped_threads


class LogPrinter(object):
    """Print logs from many containers to a single output stream."""

    def __init__(self,
                 containers,
                 presenters,
                 event_stream,
                 cascade_stop=False,
                 log_args=None):
        self.containers = containers
        self.presenters = presenters
        self.event_stream = event_stream
        self.cascade_stop = cascade_stop
        self.log_args = log_args or {}

    def run(self):
        if not self.containers:
            return

        queue = Queue()
        thread_args = queue, self.log_args
        thread_map = build_thread_map(self.containers, self.presenters, thread_args)
        start_producer_thread((
            thread_map,
            self.event_stream,
            self.presenters,
            thread_args))

        for line in consume_queue(queue, self.cascade_stop):
            remove_stopped_threads(thread_map)

            if not line:
                if not thread_map:
                    # There are no running containers left to tail, so exit
                    return
                # We got an empty line because of a timeout, but there are still
                # active containers to tail, so continue
                continue

            yield line


def get_project(conf, client):
    return Project.from_config(conf.name, conf.services.compose, client)


def up(conf, client, log=True):
    project = get_project(conf, client)
    to_attach = project.up(conf.services.names)
    if log:
        log_printer = log_printer_from_project(
            project,
            filter_containers_to_service_names(to_attach, ['app']),
            False,
            {'follow': True},
            True,
            event_stream=project.events(service_names=conf.services.names))
        log_printer.run()
    return to_attach
