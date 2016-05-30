import os
from docker import Client
from requests.exceptions import ReadTimeout
from .config import ProjectConf, LayerConf
from .script import Archive, Script, APP_PATH
from .utils import UnbufferedLineIO


class Project:

    def __init__(self, conf: ProjectConf, log, build_num='0', job_num='0', ssh_config=None, verbose=False, debug_ssh=False):
        self.conf = conf
        self.log = UnbufferedLineIO(log) if not isinstance(log, UnbufferedLineIO) else log
        self.build_num = build_num
        self.job_num = job_num
        self.verbose = verbose
        self.client = Client('unix://var/run/docker.sock')

        self.debug_ssh = debug_ssh
        self.ssh_agent = False

        if ssh_config:

            # ssh_config - Server side/django app, uses the ssh_config and deploy keys
            ssh_dir = os.path.dirname(ssh_config)

            self.environment = {
                "GIT_SSH_COMMAND": "ssh -F {}".format(ssh_config)
            }

            self.volumes = [
                "{0}:{0}".format(ssh_dir)
            ]

        else:

            # SSH Agent - Local use with shipmaster CLI
            self.ssh_agent = True

            self.ssh_auth_filename = os.path.basename(os.environ['SSH_AUTH_SOCK'])
            self.local_ssh_auth_dir = os.path.dirname(os.environ['SSH_AUTH_SOCK'])
            self.image_ssh_auth_dir = '/shipmaster/ssh-auth-sock'

            self.environment = {
                "SSH_AUTH_SOCK": os.path.join(
                    self.image_ssh_auth_dir,
                    self.ssh_auth_filename
                )
            }

            self.volumes = [
                "{}:{}".format(self.local_ssh_auth_dir, self.image_ssh_auth_dir)
            ]

        self.base = BaseLayer(self, self.conf.base)
        self.app = AppLayer(self, self.conf.app)
        self.test = TestLayer(self, self.conf.test)
        self.dev = DevLayer(self, self.conf.dev)


class LayerBase:

    def __init__(self, project: Project, layer: LayerConf):
        self.project = project
        self.layer = layer
        self.log = project.log
        self.archive = Archive(project.conf.workspace, project.log)
        self.environment = {**project.environment, **layer.environment}
        self.volumes = project.volumes.copy()

    def start_and_commit(self, container):
        client = self.project.client
        self.log.write('Uploading...')
        client.put_archive(container, '/', self.archive.getfile())
        self.log.write('Starting...')
        client.start(container)
        for line in client.logs(container, stream=True):
            self.log.write(line.decode(), newline=False)
        client.stop(container)
        repository, tag = self.image_name.split(':')
        client.commit(container, repository=repository, tag=tag)
        client.remove_container(container)

    def create(self, script):
        result = self.project.client.create_container(
            self.from_image, command=['/bin/sh', '-c', script.path],
            volumes=[v.split(':')[1] for v in self.volumes],
            environment=self.environment,
            host_config=self.project.client.create_host_config(binds=self.volumes)
        )
        return result.get('Id')

    def exists(self):
        return bool(self.image_info)

    @property
    def from_image(self):
        return self.layer.from_image

    @property
    def image_name(self):
        return "{}:latest".format(self.layer.repository)

    def print_image(self):
        image = self.image_info
        if image:
            image_hash = image['Id'].split(':')[1]
            print("{} {}".format(image['RepoTags'][0], image_hash[:12]))

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
            self.project.debug_ssh
        )
        return script

    def build(self):
        self.log.write('Building: {} FROM {}'.format(self.image_name, self.from_image))

        script = self.get_script()
        self.archive.add_script(script)
        self.archive.add_bundled_file('wait-for-it/wait-for-it.sh')
        for file in self.layer.context:
            self.archive.add_project_file(file)

        self.start_and_commit(self.create(script))


class AppLayer(LayerBase):

    @property
    def image_name(self):
        return "{}:b{}".format(self.layer.repository, self.project.build_num)

    @property
    def from_image(self):
        return self.project.base.image_name

    def get_script(self):
        script = Script('build_app.sh')
        script.write_apt_get(self.layer.apt_get)
        script.write_build(self.layer.script)
        return script

    def build(self):

        if not self.project.base.exists():
            self.project.base.build()

        self.log.write('Building: {} FROM {}'.format(self.image_name, self.from_image))

        script = self.get_script()
        self.archive.add_script(script)

        for file in self.layer.context:
            self.archive.add_project_file(file)

        self.start_and_commit(self.create(script))

    def deploy(self):

        environment = "sandbox"

        client = self.project.client
        log = self.log

        deployed_container_name = "{}_{}".format(self.layer.repository.replace('/', '_'), environment)

        log.write("Deploying: {} as {}".format(self.image_name, deployed_container_name))

        # Remove existing container
        if client.containers(all=True, filters={'name': deployed_container_name}):
            log.write("Stopping existing container.")
            client.stop(deployed_container_name)
            log.write("Removing existing container.")
            client.remove_container(deployed_container_name)

        # Run migrations/scripts to prep environment for this deployment
        archive = Archive(self.project.conf.workspace, log)
        script = Script('pre_deploy_script.sh')
        script.write("cd /app")
        archive.add_script(script)
        log.write("Running pre-deployment script.")
        container = self.project.client.create_container(
            self.image_name, command=['/bin/sh', '-c', script.path],
            volumes=[v.split(':')[1] for v in self.volumes],
            environment=self.environment,
            host_config=self.project.client.create_host_config(
                binds=self.volumes,
                network_mode='{}_default'.format(self.project.conf.name)
            )
        )
        client.put_archive(container, '/', archive.getfile())
        client.start(container)
        log.write("Waiting.")
        client.wait(container, 60*15)  # Timeout if not finished after 15 minutes
        log.write(client.logs(container).decode(), newline=False)
        client.remove_container(container)

        # Deploy App container
        self.log.write("Starting new container.")
        container = self.project.client.create_container(
            self.image_name, command=['/bin/sh', '-c', 'python3 manage.py runserver 0.0.0.0:8000'],
            name=deployed_container_name, working_dir='/app', detach=True,
            volumes=[v.split(':')[1] for v in self.volumes],
            environment=self.environment,
            host_config=self.project.client.create_host_config(
                binds=self.volumes,
                network_mode='{}_default'.format(self.project.conf.name)
            )
        )
        client.start(container)
        try:
            client.wait(container, 5)
        except ReadTimeout:
            # timeout exception expected since the process is not
            # supposed to finish under normal conditions
            # we wait 5 secs for the purpose of collecting some log output
            pass
        finally:
            log.write(client.logs(container).decode(), newline=False)


class TestLayer(LayerBase):

    @property
    def image_name(self):
        return "{}:j{}".format(self.layer.repository, self.project.job_num)

    @property
    def from_image(self):
        return self.project.app.image_name

    def get_script(self):
        script = Script('test_app.sh')
        script.write_apt_get(self.layer.apt_get)
        script.write_build(self.layer.script)
        return script

    def build(self):

        if not self.project.app.exists():
            self.project.app.build()

        self.log.write('Building: {} FROM {}'.format(self.image_name, self.from_image))

        script = self.get_script()
        self.archive.add_script(script)

        for file in self.layer.context:
            self.archive.add_project_file(file)

        self.start_and_commit(self.create(script))


class DevLayer(LayerBase):

    @property
    def from_image(self):
        return self.project.base.image_name

    def get_script(self):
        app_layer = self.project.app.layer
        script = Script('build_dev.sh')
        script.write('# App')
        script.write_apt_get(app_layer.apt_get)
        script.write('# Dev')
        script.write_apt_get(self.layer.apt_get)
        script.write()
        script.write('# App')
        script.write_build(app_layer.script)
        script.write('# Dev')
        script.write_build(self.layer.script)
        return script

    def build(self):

        if not self.project.base.exists():
            self.project.base.build()

        self.log.write('Building: {} FROM {}'.format(self.image_name, self.from_image))

        script = self.get_script()
        self.archive.add_script(script)

        self.volumes += [
            '{}:{}'.format(self.project.conf.workspace, APP_PATH),
        ]

        self.start_and_commit(self.create(script))
