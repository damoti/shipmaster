import logging
from twisted.internet.epollreactor import EPollReactor
from twisted.internet import reactor as _reactor; reactor = _reactor  # type: EPollReactor

logger = logging.getLogger(__name__)


class LogServer:

    def __init__(self, channel_layer):
        self.channel_layer = channel_layer
        self.subscribers = {}

    def start(self):
        print("Starting Shipmaster Log Interface Server")
        self.handle_subscriptions()
        self.handle_reads()

    def handle_subscriptions(self):
        subscriber, message = self.channel_layer.receive_many(["logserver.subscribe"], block=False)
        if subscriber:
            # Deal with the message
            reply_channel = message['reply_channel']
            self.subscribers[reply_channel] = {
                'filename': '',
                'fileobj': None
            }
            # do initial read of a good chunk of the file
        reactor.callLater(0.05, self.handle_subscriptions)

    def handle_reads(self):
        for reply, sub in self.subscribers.items():
            log = sub['fileobj'].read()
        files = self.factory.reply_channels()
        delay = 0.05
        if files:
            delay = 0.01
            channel, message = self.channel_layer.receive_many(["logserver.subscribe"]+files, block=False)
            if channel:
                delay = 0
                # Deal with the message
                self.factory.dispatch_reply(channel, message)

        reactor.callLater(delay, self.handle_reads)


def setup(channels):
    reactor.callLater(3, LogServer(channels).start)
