import os
from ruamel import yaml
from compose.config import config as compose_config


class ProjectConf:

    @classmethod
    def from_workspace(cls, path):
        filename = os.path.join(path, '.shipmaster.yaml')
        if not os.path.exists(filename):
            return None
        with open(filename, 'r') as file:
            return cls(filename, yaml.load(file))

    def __init__(self, path, conf_dict):
        self.path = path
        self.name = conf_dict['name']
        self.workspace = os.path.dirname(path)
        self.conf_dict = conf_dict

        layers = conf_dict.get('layers', {})
        self.base = LayerConf(self, 'base', layers.get('base', {}))
        self.app = LayerConf(self, 'app', layers.get('app', {}))
        self.test = LayerConf(self, 'test', layers.get('test', {}))

        self.ssh = SSHConf(self, conf_dict.get('ssh', {}))


class LayerConf:
    def __init__(self, project, name, layer):
        self.name = name
        self.repository = '{}/{}'.format(project.name, name)
        self.from_image = layer.get('from')
        if name == 'base' and not self.from_image:
            raise AttributeError("'base' layer must have 'from' attribute")
        self.build = layer.get('build', [])
        if type(self.build) is str:
            self.build = [self.build]
        self.prepare = layer.get('prepare', [])
        if type(self.prepare) is str:
            self.prepare = [self.prepare]
        self.start = layer.get('start')
        self.wait_for = layer.get('wait-for')
        self.apt_get = layer.get('apt-get', [])
        self.context = layer.get('context', [])
        self.volumes = layer.get('volumes', [])
        self.environment = layer.get('environment', {})


class SSHConf:
    def __init__(self, conf, ssh):
        self.conf = conf
        self.known_hosts = ssh.get('known_hosts', [])
