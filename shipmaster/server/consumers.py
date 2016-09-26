from channels.generic.websockets import JsonWebsocketConsumer
from channels import Channel


class LogsServer(JsonWebsocketConsumer):

    strict_ordering = True

    def connect(self, message, **kwargs):
        print('connect {}'.format(message.reply_channel.name))
        Channel("logserver.subscribe").send({
            'subscriber': message.reply_channel.name,
            'log': kwargs['path']
        })
        #self.send({'status': 'subscribed'})
