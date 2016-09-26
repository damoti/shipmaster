import os
import logging
from typing import Dict
from twisted.internet.epollreactor import EPollReactor
from twisted.internet import reactor as _reactor; reactor = _reactor  # type: EPollReactor

logger = logging.getLogger(__name__)


class LogFileState:
    """
    Keeps all users at the same seek location. Whenever a new user subscribes
    send everything up to the last seek location.
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


class LogServer:

    def __init__(self, channel_layer):
        self.channel_layer = channel_layer
        self.logs = {}  # type: Dict[str, LogFileState]

    def start(self):
        print("Starting Shipmaster Log Interface Server")
        self.loop()

    def loop(self):

        # First handle any log updates.
        for file in self.logs.values():
            if file.read():
                for subscriber in file.subscribers:
                    self.channel_layer.send(subscriber, {'text': file.something})

        # Now check if there are any new subscribers.
        while True:

            _, message = self.channel_layer.receive_many(["logserver.subscribe"])

            if not message:
                break

            file = self.logs.get(message['log'])
            if file is None:
                self.logs[message['log']] = file = LogFileState(message['log'])
                file.read()

            file.subscribers.append(message['subscriber'])
            self.channel_layer.send(message['subscriber'], {'text': file.everything})

        reactor.callLater(0.1, self.loop)


def setup(channels):
    reactor.callLater(3, LogServer(channels).start)
