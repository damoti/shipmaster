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
        self.dev = LayerConf(self, 'dev', layers.get('dev', {}))

        self.ssh = SSHConf(self, conf_dict.get('ssh', {}))
        self.services = ServicesConf(self, conf_dict.get('services', {}))


class LayerConf:
    def __init__(self, project, name, layer):
        self.name = name
        self.repository = '{}/{}'.format(project.name, name)
        if 'from' in layer:
            self.from_image = layer['from']
        else:
            if name == 'base':
                raise AttributeError("'base' layer must have 'from' attribute")
            if name == 'test':
                self.from_image = project.name+'/app:latest'
            else:
                self.from_image = project.name+'/base:latest'
        self.command = layer.get('command')
        self.apt_get = layer.get('apt-get', [])
        self.context = layer.get('context', [])
        self.script = layer.get('script', [])
        self.volumes = layer.get('volumes', [])
        self.environment = layer.get('environment', {})


class SSHConf:
    def __init__(self, conf, ssh):
        self.conf = conf
        self.known_hosts = ssh.get('known_hosts', [])


class ServicesConf:

    def __init__(self, conf, services):
        self.conf = conf
        self.services = services

        #services['app'].update({
        #    'image': conf.active_layer.repository,
        #    'working_dir': '/app',
        #    'command': conf.active_layer.command
        #})
        #if conf.active_layer.name == 'test':
        #    services['app'].pop('ports', None)
        self.volumes = services['app'].setdefault('volumes', [])
        self.environment = services['app'].setdefault('environment', {})

    @property
    def names(self):
        return list(self.services.keys())

    @property
    def compose(self):
        config_file = compose_config.ConfigFile('.shipmaster.yaml', {
            'version': '2',
            'services': self.services
        })
        env = compose_config.Environment()
        env.update(os.environ.copy())
        config_details = compose_config.ConfigDetails(os.getcwd(), [config_file], env)
        return compose_config.load(config_details)
