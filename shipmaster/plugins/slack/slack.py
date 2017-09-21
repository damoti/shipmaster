from shipmaster.core.plugins import Plugin


class SlackPlugin(Plugin):
    pass


class SlackConf:
    def __init__(self, conf, slack):
        self.conf = conf
        self.api = slack.get('api')
        self.events = slack.get('events', [])

    @property
    def is_enabled(self):
        return self.api is not None
