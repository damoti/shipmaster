from typing import List, Type, Iterator
from importlib import import_module
from pathlib import Path


class Event:
    phases = ["before", "after", "failed", "cleanup"]
    modes = ["build", "run", "start"]
    actions = [
        "script", "archive", "archive_upload",
        "container_start", "container_commit", "container_remove",
        "output"
    ]

    def __init__(self, phase, mode, action=None):
        assert phase in self.phases
        assert mode in self.modes
        assert action is None or action in self.actions
        self._mode, self._phase, self._action = mode, phase, action

    @classmethod
    def mode(cls, mode):
        return cls("before", mode)

    def before(self):
        return self.replace(phase="before")

    def after(self):
        return self.replace(phase="after")

    def failed(self):
        return self.replace(phase="failed")

    def cleanup(self):
        return self.replace(phase="cleanup")

    def action(self, action):
        return self.replace(action=action)

    @property
    def names(self):
        if self._action:
            yield "{}_{}".format(self._phase, self._action)
            yield "{}_{}_{}".format(self._phase, self._mode, self._action)
        else:
            yield "{}_{}".format(self._phase, self._mode)

    def replace(self, **kwargs):
        new = {
            'phase': self._phase,
            'mode': self._mode,
            'action': self._action
        }
        new.update(kwargs)
        return Event(**new)


class Platform:
    cli = 'cli'
    server = 'server'


class Plugin:

    @classmethod
    def should_load(cls, platform) -> bool:
        """ Whether the plugin should be loaded, depending on platform. """
        return True

    @classmethod
    def should_enable(cls, builder, args):
        """ Whether the plugin should be enabled for the specific build. """
        return True

    @classmethod
    def contribute_to_argparse(cls, parser, commands):
        pass

    def __init__(self, builder):
        self.builder = builder

    def contribute_to_build_command(self, image_builder, command: str):
        return command

    def contribute_to_run_command(self, image_builder, command: str):
        return command

    def contribute_to_start_command(self, image_builder, command: str):
        return command

    def on_event(self, event, data, extra):
        for name in event.names:
            method = getattr(self, name, None)
            if method:
                if extra is not None:
                    method(data, extra)
                else:
                    method(data)


class PluginManager:

    plugin_classes = []  # type: List[Type[Plugin]]

    @classmethod
    def load(cls, platform):
        contrib = (Path(__file__).parent / Path('../plugins')).resolve()
        for plugin_path in contrib.iterdir():
            if plugin_path.is_dir() and (plugin_path/'__init__.py').is_file():
                plugin_module = import_module('shipmaster.plugins.'+plugin_path.name)
                mod_path, _, cls_name = plugin_module.plugin_class.rpartition('.')
                class_module = import_module(mod_path)
                plugin_class = getattr(class_module, cls_name)  # type: Type[Plugin]
                assert issubclass(plugin_class, Plugin)
                if plugin_class.should_load(platform):
                    cls.plugin_classes += [plugin_class]

    def __init__(self, builder):
        self.plugins = [
            plugin_class(builder) for plugin_class in self.plugin_classes
        ]

    def notify(self, event: str, image_builder, extra=None):
        for plugin in self:
            plugin.on_event(event, image_builder, extra)

    def contribute(self, what: str, image_builder, data):
        method = "contribute_to_"+what
        for plugin in self:
            data = getattr(plugin, method)(image_builder, data)
        return data

    def __iter__(self) -> Iterator[Plugin]:
        return iter(self.plugins)
