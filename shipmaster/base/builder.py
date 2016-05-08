import os
from docker import Client
from .config import ProjectConf, LayerConf
from .script import Archive, Script, APP_PATH


class Project:

    def __init__(self, conf: ProjectConf, log, build_num='latest', job_num='latest', verbose=False, debug_ssh_agent=False):
        self.conf = conf
        self.log = log
        self.build_num = build_num
        self.job_num = job_num
        self.verbose = verbose
        self.debug_ssh_agent = debug_ssh_agent
        self.client = Client('unix://var/run/docker.sock')

        self.base = BaseLayer(self, self.conf.base)
        self.app = AppLayer(self, self.conf.app)
        self.test = TestLayer(self, self.conf.test)
        self.dev = DevLayer(self, self.conf.dev)

        self.ssh_auth_filename = os.path.basename(os.environ['SSH_AUTH_SOCK'])
        self.local_ssh_auth_dir = os.path.dirname(os.environ['SSH_AUTH_SOCK'])
        self.image_ssh_auth_dir = '/shipmaster/ssh-auth-sock'

        self.environment = {
            'SSH_AUTH_SOCK': os.path.join(
                self.image_ssh_auth_dir,
                self.ssh_auth_filename
            )
        }


class LayerBase:

    def __init__(self, project: Project, layer: LayerConf):
        self.project = project
        self.layer = layer
        self.archive = Archive(project.conf.workspace)

    def start_and_commit(self, container, tag):
        client = self.project.client
        log = self.project.log
        log.write('put archive\n')
        log.flush()
        client.put_archive(container, '/', self.archive.getfile())
        log.write('starting container\n')
        log.flush()
        client.start(container)
        for line in client.logs(container, stream=True):
            log.write(line.decode())
            log.flush()
        client.stop(container)
        client.commit(container, repository=self.layer.repository, tag=tag)
        client.remove_container(container)

    def create(self, script, volumes):
        result = self.project.client.create_container(
            self.layer.from_image, command=['/bin/sh', '-c', script.path],
            volumes=[v.split(':')[1] for v in volumes],
            environment=self.layer.environment,
            host_config=self.project.client.create_host_config(binds=volumes)
        )
        return result.get('Id')

    def print_image(self):
        image = self.image_info
        if image:
            image_hash = image['Id'].split(':')[1]
            print("{} {}".format(image['RepoTags'][0], image_hash[:12]))

    @property
    def image_name(self):
        return "{}:b{}".format(self.layer.repository, self.project.build_num)

    @property
    def image_info(self):
        images = self.project.client.images(self.image_name)
        if images:
            return images[0]


class BaseLayer(LayerBase):

    def get_script(self):
        script = Script('build_base.sh')
        script.write_all(
            self.layer.script,
            self.layer.apt_get,
            self.project.conf.ssh.known_hosts,
            self.project.conf.name,
            self.project.debug_ssh_agent
        )
        return script

    def build(self):
        script = self.get_script()
        self.archive.add_script(script)
        self.archive.add_bundled_file('wait-for-it/wait-for-it.sh')
        for file in self.layer.context:
            self.archive.add_project_file(file)

        volumes = [
            '{}:{}'.format(self.project.local_ssh_auth_dir, self.project.image_ssh_auth_dir)
        ]

        container = self.create(script, volumes)

        self.start_and_commit(container, 'latest')


class AppLayer(LayerBase):

    def get_script(self):
        script = Script('build_app.sh')
        script.write_apt_get(self.layer.apt_get)
        script.write_build(self.layer.script)
        return script

    def build(self):

        script = self.get_script()
        self.archive.add_script(script)

        for file in self.layer.context:
            self.archive.add_project_file(file)

        volumes = [
            '{}:{}'.format(self.project.local_ssh_auth_dir, self.project.image_ssh_auth_dir)
        ]

        self.project.log.write('# Creating container...\n')
        self.project.log.flush()
        container = self.create(script, volumes)
        self.project.log.write('# Finished creating container...\n')
        self.project.log.flush()

        self.start_and_commit(container, 'b{}'.format(self.project.build_num))


class TestLayer(LayerBase):

    def get_script(self):
        script = Script('test_app.sh')
        script.write_apt_get(self.layer.apt_get)
        script.write_build(self.layer.script)
        return script

    def build(self):

        script = self.get_script()
        self.archive.add_script(script)

        for file in self.layer.context:
            self.archive.add_project_file(file)

        volumes = [
            '{}:{}'.format(self.project.local_ssh_auth_dir, self.project.image_ssh_auth_dir)
        ]

        container = self.create(script, volumes)

        self.start_and_commit(container, 'j{}'.format(self.project.job_num))


class DevLayer(LayerBase):

    def __init__(self, project: Project, layer: LayerConf):
        super().__init__(project, layer)
        self.app_layer = project.app.layer

    def get_script(self):
        script = Script('build_dev.sh')
        script.write('# App')
        script.write_apt_get(self.app_layer.apt_get)
        script.write('# Dev')
        script.write_apt_get(self.layer.apt_get)
        script.write()
        script.write('# App')
        script.write_build(self.app_layer.script)
        script.write('# Dev')
        script.write_build(self.layer.script)
        return script

    def build(self):
        script = self.get_script()
        self.archive.add_script(script)

        volumes = [
            '{}:{}'.format(self.project.conf.workspace, APP_PATH),
            '{}:{}'.format(self.project.local_ssh_auth_dir, self.project.image_ssh_auth_dir)
        ]

        container = self.create(script, volumes)

        self.start_and_commit(container, 'latest')
