import logging
from typing import Dict
from channels import Channel
from channels.generic.websockets import JsonWebsocketConsumer
from twisted.internet.epollreactor import EPollReactor
from twisted.internet import reactor as _reactor; reactor = _reactor  # type: EPollReactor

logger = logging.getLogger('logservice')


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

    CHANNEL = "logservice.subscribe"

    def __init__(self, channel_layer):
        self.channel_layer = channel_layer
        self.logs = {}  # type: Dict[str, LogFileState]

    def start(self):
        logger.info("Starting Shipmaster Log Interface Service")
        self.loop()

    def loop(self):

        # First handle any log updates.
        for file in self.logs.values():
            if file.read():
                for subscriber in file.subscribers:
                    self.channel_layer.send(subscriber, {'text': file.something})

        # Now check if there are any new subscribers.
        while True:

            _, message = self.channel_layer.receive_many([self.CHANNEL])

            if not message:
                break

            file = self.logs.get(message['log'])
            if file is None:
                self.logs[message['log']] = file = LogFileState(message['log'])
                file.read()

            file.subscribers.append(message['subscriber'])
            self.channel_layer.send(message['subscriber'], {'text': file.everything})

        reactor.callLater(0.1, self.loop)


class LogSubscriptionConsumer(JsonWebsocketConsumer):

    strict_ordering = True

    def connect(self, message, **kwargs):
        Channel(LogStreamingService.CHANNEL).send({
            'subscriber': message.reply_channel.name,
            'log': kwargs['path']
        })


def setup(channels):
    reactor.callLater(3, LogStreamingService(channels).start)
