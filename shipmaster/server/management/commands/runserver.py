from channels import DEFAULT_CHANNEL_LAYER, channel_layers
from channels.management.commands.runserver import Command as RunserverCommand
from shipmaster.server.logserver import setup


class Command(RunserverCommand):

    def add_arguments(self, parser):
        super().add_arguments(parser)
        #parser.add_argument('--noworker', action='store_false', dest='run_worker', default=True,
        #    help='Tells Django not to run a worker thread; you\'ll need to run one separately.')
        #parser.add_argument('--noasgi', action='store_false', dest='use_asgi', default=True,
        #    help='Run the old WSGI-based runserver rather than the ASGI-based one')

    def handle(self, *args, **options):
        super().handle(*args, **options)

    def inner_run(self, *args, **options):
        setup(channel_layers[DEFAULT_CHANNEL_LAYER])
        super().inner_run(*args, **options)
