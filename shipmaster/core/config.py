import os
from collections import namedtuple
from ruamel import yaml


class BuildConfig(namedtuple(
        '_BuildConfig',
        'version name workspace environment branches stages image_configs plugin_configs')):

    @classmethod
    def from_kwargs(cls, workspace, **kwargs):

        attrs = {
            'workspace': workspace,
            'version': kwargs.pop('version', 1),
            'name': kwargs.pop('name'),
            'branches': kwargs.pop('branches', ['master']),
            'stages': kwargs.pop('stages', ['build']),
            'image_configs': kwargs.pop('images', {}),
            'environment': kwargs.pop('environment', {}),
        }

        for name in attrs['image_configs']:
            image_config = ImageConfig.from_kwargs(name=name, **attrs['image_configs'][name])
            attrs['image_configs'][name] = image_config

        # all key/values still left in the configuration are plugins
        attrs['plugin_configs'] = kwargs

        return cls(**attrs)

    @classmethod
    def from_workspace(cls, path):
        filename = os.path.join(path, '.shipmaster.yaml')
        if not os.path.exists(filename):
            return None
        with open(filename, 'r') as file:
            return cls.from_kwargs(path, **yaml.load(file, yaml.RoundTripLoader))

    @classmethod
    def from_string(cls, src):
        return cls.from_kwargs(None, **yaml.safe_load(src, yaml.RoundTripLoader))

    def check(self):
        for image in self.images.values():
            if image.stage and image.stage not in self.stages:
                raise ValueError(
                    "Stage '{}' for image '{}' is not one of the available stages: {}"
                    .format(image.stage, image.name, ', '.join(self.stages))
                )

    def dump(self):
        for image in self.images:
            print(image)


class ImageConfig(namedtuple(
        '_ImageConfig',
        'name stage from_image environment volumes context build run start plugin_configs')):

    @classmethod
    def from_kwargs(cls, name, **kwargs):

        attrs = {
            'name': name,
            'stage': kwargs.pop('stage', name),
            'from_image': kwargs.pop('from'),
            'environment': kwargs.pop('environment', {}),
        }

        for command in ['volumes', 'context', 'build', 'run', 'start']:
            value = kwargs.pop(command, [])
            if type(value) is str:
                value = [value]
            attrs[command] = value

        # all key/values still left in the configuration are plugins
        attrs['plugin_configs'] = kwargs

        return cls(**attrs)
