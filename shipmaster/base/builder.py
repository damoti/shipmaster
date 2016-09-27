import os
import time
import struct
import logging
from docker import Client
from docker import constants as docker_constants
from compose.service import Service, VolumeSpec
from compose.service import Container
from compose.project import Project as ComposeProject
from requests.packages.urllib3.exceptions import ReadTimeoutError
from .config import ProjectConf, LayerConf
from .script import Archive, Script, SCRIPT_PATH, APP_PATH

logger = logging.getLogger('shipmaster')


class Project:

    def __init__(self, conf: ProjectConf, build_num='0', job_num='0', commit_info=None, ssh_config=None, debug_ssh=False, editable=False):
        self.conf = conf
        self.build_num = build_num
        self.commit_info = commit_info
        self.job_num = job_num
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
        self.app = AppLayer(self, self.conf.app, editable)
        self.test = TestLayer(self, self.conf.test)

    @property
    def test_tag(self):
        return "{}b{}t".format(self.build_num, self.job_num)

    @property
    def test_name(self):
        return "{}{}".format(self.conf.name, self.test_tag)


class LayerBase:

    def __init__(self, project: Project, layer: LayerConf):
        self.project = project
        self.layer = layer
        self.archive = Archive(project.conf.workspace)
        self.environment = {**project.environment, **layer.environment}
        self.volumes = project.volumes.copy()

    def start_and_commit(self, container, cmd):
        client = self.project.client
        logger.info('Uploading...')
        client.put_archive(container, '/', self.archive.getfile())
        logger.info('Starting...')
        client.start(container)
        for line in client.logs(container, stream=True):
            logger.info(line.decode().rstrip())
        result = client.wait(container)
        if result == 0:
            # Only tag image if container was built successfully.
            repository, tag = self.image_name, None
            if ':' in repository:
                repository, tag = tag.split(':')
            conf = client.create_container_config(self.image_name, cmd, working_dir=APP_PATH)
            client.commit(container, repository=repository, tag=tag, conf=conf)
        client.remove_container(container)
        return result

    def create(self, script, labels=None):
        result = self.project.client.create_container(
            self.from_image, command=['/bin/sh', '-c', script.path],
            volumes=[v.split(':')[1] for v in self.volumes],
            environment=self.environment,
            host_config=self.project.client.create_host_config(binds=self.volumes),
            labels=labels or {}
        )
        return result.get('Id')

    def exists(self):
        return bool(self.image_info)

    def remove(self):
        self.project.client.remove_image(self.image_name)

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
            self.layer.build,
            self.layer.apt_get,
            self.project.conf.ssh.known_hosts,
            self.project.conf.name,
            self.project.debug_ssh
        )
        return script

    def build(self):
        logger.info('Building: {} FROM {}'.format(self.image_name, self.from_image))

        script = self.get_script()
        self.archive.add_script(script)
        self.archive.add_bundled_file('wait-for-it/wait-for-it.sh')
        for file in self.layer.context:
            self.archive.add_project_file(file)

        return self.start_and_commit(self.create(script), cmd="echo 'Base image does not do anything.'")


class AppLayer(LayerBase):

    def __init__(self, project: Project, layer: LayerConf, editable=False):
        super().__init__(project, layer)
        self.editable = editable
        if self.editable:
            self.volumes.append(
                "{}:{}".format(os.getcwd(), APP_PATH)
            )

    @property
    def image_name(self):
        return "{}:b{}".format(self.layer.repository, self.project.build_num)

    @property
    def from_image(self):
        return self.project.base.image_name

    def get_script(self):
        script = Script('build_app.sh')
        if self.project.debug_ssh:
            script.write_debug_ssh(
                self.project.conf.name,
                self.project.conf.ssh.known_hosts
            )
        script.write_apt_get(self.layer.apt_get)
        script.write_build(self.layer.build)
        return script

    def build(self):

        logger.info('Building: {} FROM {}'.format(self.image_name, self.from_image))

        script = self.get_script()
        self.archive.add_script(script)

        if not self.editable:
            for file in self.layer.context:
                self.archive.add_project_file(file)

        labels = {'git-'+k: v for k, v in self.project.commit_info.items()}
        labels['shipmaster-build'] = self.project.build_num
        if self.editable:
            labels['editable'] = 'yes'

        start_command = self.layer.start
        if self.layer.wait_for:
            start_command = "{} {} -- {}".format(
                os.path.join(SCRIPT_PATH, "wait-for-it/wait-for-it.sh"),
                self.layer.wait_for,
                start_command
            )

        return self.start_and_commit(self.create(script, labels), cmd=['/bin/sh', '-c', start_command])

    def deploy(self, compose: ComposeProject, service_name):

        # Make sure the custom network is up
        compose.initialize()

        service = compose.get_service(service_name)  # type: Service

        # 1. Tag the new image with what docker-compose is expecting.
        image_name, tag = service.image_name.split(':')
        logger.info("Tagging: {} -> {}:{}".format(self.image_name, image_name, tag))
        service.client.tag(self.image_name, image_name, tag)

        # 2. Stop and remove the existing container(s).
        for c in service.containers():  # type: Container
            logger.info("Stopping: {}".format(c.name))
            c.stop(timeout=30)
            c.remove()

        if self.layer.prepare:

            # 3. Run upgrade/migration scripts to prepare environment for this deployment.
            logger.info("Running Migrations...")

            labels = service.client.images(self.image_name)[0].get('Labels', {})

            #   a. Create upgrade script.
            archive = Archive(self.project.conf.workspace)
            script = Script('pre_deploy_script.sh')
            script.write("cd /app")
            for command in self.layer.prepare:
                script.write(command.format(service=service_name, **labels))
            archive.add_script(script)

            #   b. Create one-off container to run upgrade script.
            container = service.create_container(one_off=True, command=['/bin/sh', '-c', script.path])
            service.client.put_archive(container.id, '/', archive.getfile())

            #   c. Run upgrade script.
            service.start_container(container)
            for line in container.logs(stream=True):
                logger.info(line.decode().rstrip())
            result = service.client.wait(container.id)
            container.remove()
            if result != 0:
                logger.error("Migration failed.")
                return result

        # 4. Deploy

        # here create_container() must work without arguments
        # this way if someone recreates the containers via
        # command line `docker-compose` it should work identical
        # to when shipmaster starts the container
        container = service.create_container()
        logger.info("Starting: {}".format(container.id))
        service.start_container(container)
        return read_container_log_for_seconds(container, 10)


def read_container_log_for_seconds(container, secs):

    client = container.client

    url = client._url("/containers/{0}/logs", container.id)
    params = {'stderr': True, 'stdout': True, 'timestamps': False, 'follow': True, 'tail': 'all'}
    response = client._get(url, params=params, stream=True)

    socket = client._get_raw_response_socket(response)
    socket._sock.settimeout(secs)

    try:
        start = time.time()
        while True:
            header = response.raw.read(docker_constants.STREAM_HEADER_SIZE_BYTES)
            if not header:
                break
            _, length = struct.unpack('>BxxxL', header)
            if not length:
                continue
            data = response.raw.read(length)
            if not data:
                break
            logger.info(data.decode().rstrip())
            if (time.time() - start) >= secs:
                break
    except ReadTimeoutError:
        pass

    if container.is_running:
        return 0  # if it's running then all is good, that's all we can know
    else:
        # logically a deployed container shouldn't exit but
        # we'll let it speak for itself about what happened
        return container.exit_code


class TestLayer(LayerBase):

    @property
    def image_name(self):
        return "{}_test".format(self.project.test_name)

    @property
    def from_image(self):
        return self.project.app.image_name

    @property
    def app_image_info(self):
        images = self.project.client.images(self.from_image)
        if images:
            return images[0]

    @property
    def is_editable(self):
        app_info = self.app_image_info or {}
        return 'editable' in app_info.get('Labels', [])

    def get_script(self):
        script = Script('test_app.sh')
        script.write_apt_get(self.layer.apt_get)
        script.write_build(self.layer.build)
        return script

    def build(self):

        logger.info('Building: {} FROM {}'.format(self.image_name, self.from_image))

        script = self.get_script()
        self.archive.add_script(script)

        if self.is_editable:
            self.volumes.append(
                "{}:{}".format(os.getcwd(), APP_PATH)
            )
        else:
            for file in self.layer.context:
                self.archive.add_project_file(file)

        return self.start_and_commit(self.create(script), cmd=self.layer.start)

    def run(self, compose: ComposeProject):

        logger.info('Running tests in {}...'.format(self.image_name))

        # Make sure the custom network is up
        compose.initialize()

        service = compose.get_service('test')  # type: Service

        if self.is_editable:
            self.volumes.append(
                "{}:{}".format(os.getcwd(), APP_PATH)
            )

        container = service.create_container(
            one_off=True,
            command=['/bin/sh', '-c', self.layer.start],
            volumes=map(VolumeSpec.parse, self.volumes),
            environment=self.environment,
        )

        compose.up(service.get_dependency_names())

        # TODO: Need a more intelligent way to wait for dependencies to come up.
        time.sleep(10)

        service.start_container(container)
        for line in container.logs(stream=True):
            logger.info(line.decode().rstrip())

        result = service.client.wait(container.id)
        container.remove()
        if result != 0:
            logger.error("Test run failed.")
        return result
