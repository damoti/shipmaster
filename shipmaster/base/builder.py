import os
from docker import Client
from compose.service import Service
from compose.service import Container
from compose.project import Project as ComposeProject
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

    def deploy(self, compose: ComposeProject, service_name):
        log = self.log

        # Make sure the custom network is up
        compose.initialize()

        service = compose.get_service(service_name)  # type: Service

        # 1. Tag the new image with what docker-compose is expecting.
        image_name, tag = service.image_name.split(':')
        log.write("Tagging: {} -> {}:{}".format(self.image_name, image_name, tag))
        service.client.tag(self.image_name, image_name, tag)

        # 2. Stop and remove the existing container(s).
        for c in service.containers():  # type: Container
            log.write("Stopping: {}".format(c.name))
            c.stop(timeout=30)
            c.remove()

        # 3. Run upgrade/migration scripts to prep environment for this deployment.
        log.write("Running Pre-Deploy Script / Migrations")

        #   a. Create upgrade script.
        archive = Archive(self.project.conf.workspace, log)
        script = Script('pre_deploy_script.sh')
        script.write("cd /app")
        archive.add_script(script)

        #   b. Create one-off container to run upgrade script.
        container = service.create_container(one_off=True, command=['/bin/sh', '-c', script.path])
        service.client.put_archive(container.id, '/', archive.getfile())

        #   c. Run upgrade script.
        service.start_container(container)
        log.write("Waiting.")
        service.client.wait(container.id, 60*15)  # Timeout if not finished after 15 minutes
        log.write(container.logs().decode(), newline=False)
        container.remove()

        # 4. Deploy

        container = service.create_container()
        log.write("Starting: {}".format(container.id))
        service.start_container(container)
        try:
            service.client.wait(container.id, 10)
        except ReadTimeout:
            # timeout exception expected since the process is not
            # supposed to finish under normal conditions
            # we wait 10 secs for the purpose of collecting some log output
            pass
        finally:
            log.write(container.logs().decode(), newline=False)


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
