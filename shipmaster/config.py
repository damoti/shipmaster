import os
from ruamel import yaml
from compose.config import config as compose_config


class ShipmasterConf:

    TEMP_PATH = '/tmp/shipmaster'

    def __init__(self, active_layer, filename, conf):
        self.filename = filename
        self.name = conf['name']
        self.workspace = os.path.dirname(filename)

        self.scripts_dir = os.path.join(self.TEMP_PATH, 'scripts')
        self.script_name = 'build.sh'
        self.script_path = os.path.join(self.scripts_dir, self.script_name)

        self.ssh_auth_filename = os.path.basename(os.environ['SSH_AUTH_SOCK'])
        self.local_ssh_auth_dir = os.path.dirname(os.environ['SSH_AUTH_SOCK'])
        self.image_ssh_auth_dir = os.path.join(self.TEMP_PATH, 'ssh-auth')

        self.volumes = [
            self.workspace+':/app',
            '{0}:{0}'.format(self.scripts_dir),
            '{}:{}'.format(self.local_ssh_auth_dir,
                           self.image_ssh_auth_dir)
        ]

        self.environment = {
            'SSH_AUTH_SOCK': os.path.join(
                self.image_ssh_auth_dir,
                self.ssh_auth_filename
            )
        }

        for layer_name in ('base', 'app', 'test', 'dev'):
            layer = conf['layers'].setdefault(layer_name, {})
            layer['name'] = layer_name
            layer['repository'] = '{}/{}'.format(self.name, layer_name)
            layer['tag'] = 'latest'
            if 'from' not in layer:
                if layer_name == 'base':
                    raise AttributeError("'base' layer must have 'from' attribute")
                if layer_name == 'test':
                    layer['from'] = self.name+'/app:latest'
                else:
                    layer['from'] = self.name+'/base:latest'
            setattr(self, layer_name, LayerConf(self, layer))

        self.active_layer = getattr(self, active_layer)
        self.ssh = SSHConf(self, conf.get('ssh', {}))
        self.services = ServicesConf(self, conf.get('services', {}))

    @classmethod
    def from_filename(cls, active_layer, filename):
        with open(filename, 'r') as file:
            return cls(active_layer, filename, yaml.load(file))


class LayerConf:
    def __init__(self, conf, layer):
        self.conf = conf
        self.name = layer['name']
        self.repository = layer['repository']
        self.tag = layer['tag']
        self.image_name = self.repository+':'+self.tag
        self.from_image = layer['from']
        self.command = layer.get('command')
        self.apt_get = layer.get('apt-get', [])
        self.context = layer.get('context', [])
        self.script = layer.get('script', [])
        self.volumes = layer.get('volumes', [])
        self.volumes += conf.volumes
        self.environment = layer.get('environment', {})
        self.environment.update(conf.environment)


class SSHConf:
    def __init__(self, conf, ssh):
        self.conf = conf
        self.known_hosts = ssh.get('known_hosts', [])


class ServicesConf:

    def __init__(self, conf, services):
        self.conf = conf
        self.services = services

        services['app'].update({
            'image': conf.active_layer.repository,
            'working_dir': '/app',
            'command': conf.active_layer.command
        })
        if conf.active_layer.name == 'test':
            services['app'].pop('ports', None)
        self.volumes = services['app'].setdefault('volumes', [])
        self.volumes += conf.volumes
        self.environment = services['app'].setdefault('environment', {})
        self.environment.update(conf.environment)

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
