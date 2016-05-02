import os
from ruamel import yaml
from compose.config import config as compose_config


class ShipmasterConf:

    def __init__(self, filename, conf):
        self.filename = filename
        self.name = conf['name']
        for layer in ('base', 'app', 'test', 'dev'):
            image_name = '{}/{}:latest'.format(self.name, layer)
            setattr(self, layer, LayerConf(layer, image_name, conf['layers'][layer]))
        self.services = ServicesConf(conf)
        self.ssh = SSHConf(conf)

    @classmethod
    def from_filename(cls, filename):
        with open(filename, 'r') as file:
            return cls(filename, yaml.load(file))


class LayerConf:
    def __init__(self, name, image_name, conf):
        self.name = name
        self.image_name = image_name
        self.from_image = conf.get('from')
        self.apt_get = conf.get('apt-get', [])
        self.context = conf.get('context', [])
        self.script = conf.get('script', [])
        self.volumes = conf.get('volumes', [])
        self.environment = conf.get('environment', [])


class SSHConf:
    def __init__(self, conf):
        self.conf = conf
        self.ssh_conf = conf.get('ssh', {})
        self.known_hosts = self.ssh_conf.get('known_hosts', [])


class ServicesConf:

    def __init__(self, conf):
        self.names = list(conf['services'].keys())

        conf['services']['app'].update({
            'image': conf['name']+'/dev',
            'working_dir': '/app',
        })
        volumes = conf['services']['app'].setdefault('volumes', [])
        volumes.append(os.getcwd()+':/app')

        config_file = compose_config.ConfigFile('.shipmaster.yaml', {
            'version': '2',
            'services': conf['services']
        })

        env = compose_config.Environment()
        env.update(os.environ)

        config_details = compose_config.ConfigDetails(os.getcwd(), [config_file], env)

        self.compose = compose_config.load(config_details)
