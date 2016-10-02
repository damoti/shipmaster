import logging
from typing import Dict
from channels import Channel
from channels.log import handler
from channels.generic.websockets import JsonWebsocketConsumer
from twisted.internet.epollreactor import EPollReactor
from twisted.internet import reactor as _reactor; reactor = _reactor  # type: EPollReactor
from django.conf import settings

logger = logging.getLogger('shipmaster.logserver')
logger.setLevel(logging.INFO)
logger.addHandler(handler)


class LogFileState:
    """

    - Keeps all users at the same seek location. Whenever a new user subscribes,
      send everything up to the last seek location.

    - We need to be able to listen to files that don't exist yet
      and start streaming as soon as the file is available.
      This is because the user may have navigated to a build/job
      page even before the build/job has started.

    """

    def __init__(self, path):
        self.path = path
        self.file = None
        self.position = 0
        self.something = ""
        self.subscribers = []

    def open(self):
        if not self.file:
            try:
                self.file = open(self.path, 'r')
            except FileNotFoundError:
                return False
        return True

    def close(self):
        if self.file:
            self.file.close()

    def read(self):
        if not self.open():
            return False
        self.something = self.file.read()
        if self.something:
            self.position = self.file.tell()
            return True
        return False

    @property
    def everything(self):
        if not self.open():
            return ''
        self.file.seek(0)
        return self.file.read(self.position)


class LogStreamingService:

    SUBSCRIBE = "logservice.subscribe"
    UNSUBSCRIBE = "logservice.unsubscribe"

    def __init__(self, channel_layer, verbosity):
        self.channel_layer = channel_layer
        self.logs = {}  # type: Dict[str, LogFileState]
        self.counter = 0
        if verbosity > 1:
            logger.setLevel(logging.DEBUG)

    def start(self):
        logger.info(
            "Shipmaster log service running, listening to channels: {}".format(
                ', '.join([self.SUBSCRIBE, self.UNSUBSCRIBE])
            ))
        self.loop()

    def loop(self):

        # First check unsubscribes so we don't send logs to closed connections.
        while True:

            _, message = self.channel_layer.receive_many([self.UNSUBSCRIBE])

            if not message:
                break

            file = self.logs.get(message['log'])
            if file and message['subscriber'] in file.subscribers:
                logger.debug("Unsubscribing {} from {}.".format(
                    message['subscriber'], message['log']
                ))
                file.subscribers.remove(message['subscriber'])
                if len(file.subscribers) == 0:
                    logger.debug("Closing {}.".format(file.path))
                    file.close()
                    del self.logs[file.path]

        # Send log updates.
        for file in self.logs.values():
            if file.read():
                logger.debug("File {} moved {} to position {}...".format(file.path, len(file.something), file.position))
                for subscriber in file.subscribers:
                    self.channel_layer.send(subscriber, {'text': file.something})

        # Now check if there are any new subscribers.
        while True:

            _, message = self.channel_layer.receive_many([self.SUBSCRIBE])

            if not message:
                break

            logger.debug("New subscriber {} for {}.".format(
                message['subscriber'], message['log']
            ))

            file = self.logs.get(message['log'])
            if file is None:
                self.logs[message['log']] = file = LogFileState(message['log'])
                logger.debug("Opened log {}.".format(file.path))
                file.read()

            file.subscribers.append(message['subscriber'])
            self.channel_layer.send(message['subscriber'], {'text': file.everything})

        reactor.callLater(0.1, self.loop)


class LogSubscriptionConsumer(JsonWebsocketConsumer):

    http_user = True
    strict_ordering = True

    def connect(self, message, **kwargs):
        if message.user.is_authenticated:
            Channel(LogStreamingService.SUBSCRIBE).send({
                'subscriber': message.reply_channel.name,
                'log': kwargs['path']
            })

    def disconnect(self, message, **kwargs):
        Channel(LogStreamingService.UNSUBSCRIBE).send({
            'subscriber': message.reply_channel.name,
            'log': kwargs['path']
        })


def setup(channels, verbosity):
    reactor.callLater(3, LogStreamingService(channels, verbosity).start)


def run():
    import os
    from shipmaster.server.asgi import channel_layer
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)-15s %(levelname)-8s %(message)s",
    )
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "shipmaster.server.settings")
    LogStreamingService(channel_layer).start()
    reactor.run()


if __name__ == "__main__":
    run()
