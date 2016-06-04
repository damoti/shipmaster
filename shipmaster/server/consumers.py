from channels.generic.base import BaseConsumer
from channels.generic.websockets import JsonWebsocketConsumer


class LogServer(JsonWebsocketConsumer):

    strict_ordering = True

    def connection_groups(self, **kwargs):
        """
        Called to return the list of groups to automatically add/remove
        this connection to/from.
        """
        return ["test"]

    def connect(self, message, **kwargs):
        """
        Perform things on connection start
        """
        message.reply_channel.myvar = 99
        print('connect {}'.format(message.reply_channel.name))
        self.send({'log': 'this'})

    def receive(self, content, **kwargs):
        """
        Called when a message is received with decoded JSON content
        """
        print('recieve {}'.format(self.message.reply_channel.name))
        print(self.message.reply_channel.myvar)
        self.send(content)

    def disconnect(self, message, **kwargs):
        """
        Perform things on connection close
        """
        pass


class LogConsumer(BaseConsumer):

    method_mapping = {
        "consume-log": "consume_log"
    }

    def consume_log(self, message):
        print(message)