import os
from collections import OrderedDict, namedtuple
from ruamel import yaml


class ProjectConfig(namedtuple('_ProjectConfig', 'version name branches stages images plugins')):

    @classmethod
    def from_workspace(cls, path):
        filename = os.path.join(path, '.shipmaster.yaml')
        if not os.path.exists(filename):
            return None
        with open(filename, 'r') as file:
            return cls.from_kwargs(**yaml.load(file, yaml.RoundTripLoader))

    @classmethod
    def from_string(cls, src):
        return cls.from_kwargs(**yaml.safe_load(src, yaml.RoundTripLoader))

    @classmethod
    def from_kwargs(cls, **kwargs):
        version = kwargs.pop('version', 1)
        name = kwargs.pop('name')
        branches = kwargs.pop('branches', ['master']),
        stages = kwargs.pop('stages', ['build'])
        images = OrderedDict()
        plugins = OrderedDict()
        project = cls(version, name, branches, stages, images, plugins)
        for name, image in kwargs.pop('images', {}).items():
            images[name] = Image.from_kwargs(name=name, project=project, **image)
        # all keys still left in the configuration are plugins
        for name, plugin in kwargs.items():
            plugins[name] = Plugin(name, project, plugin)
        return project

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


class Image(namedtuple('_Image', 'name project stage from_image build prepare start plugins')):

    @classmethod
    def from_kwargs(cls, name, project, **kwargs):
        stage = kwargs.pop('stage', name)
        from_image = kwargs.pop('from')

        build = kwargs.pop('build', [])
        if type(build) is str:
            build = [build]

        prepare = kwargs.pop('prepare', [])
        if type(prepare) is str:
            prepare = [prepare]

        start = kwargs.pop('start', [])
        if type(start) is str:
            start = [start]

        # all key/values still left in the configuration are plugins
        plugins = {
            name: Plugin(name, project, plugin)
            for name, plugin in kwargs.items()
        }

        return cls(name, project, stage, from_image, build, prepare, start, plugins)

    @property
    def repository(self):
        return '{}/{}'.format(self.project.name, self.name)


class Plugin(namedtuple('_Plugin', 'name project config')):
    pass
