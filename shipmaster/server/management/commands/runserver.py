from channels import DEFAULT_CHANNEL_LAYER, channel_layers
from channels.management.commands.runserver import Command as RunserverCommand
from shipmaster.server.logserver import setup


class Command(RunserverCommand):

    def inner_run(self, *args, **options):
        setup(channel_layers[DEFAULT_CHANNEL_LAYER])
        super().inner_run(*args, **options)
