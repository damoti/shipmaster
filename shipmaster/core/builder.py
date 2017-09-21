import os
import time
import struct
from collections import OrderedDict
from docker import DockerClient
from docker import constants as docker_constants
from compose.service import Service, VolumeSpec
from compose.service import Container
from compose.project import Project as ComposeProject
from requests.packages.urllib3.exceptions import ReadTimeoutError
from .config import BuildConfig, ImageConfig
from .script import Archive, Script, SCRIPT_PATH, APP_PATH
from .plugins import Event, PluginManager


class Builder:

    def __init__(self, build_config: BuildConfig, args=None, build_num='0', job_num='0', commit_info=None):
        self.config = build_config
        self.build_num = build_num
        self.commit_info = commit_info
        self.job_num = job_num
        self.client = DockerClient('unix://var/run/docker.sock')
        self.args = args
        self.images = self._stage_to_image_builders_mapping()
        self.plugins = PluginManager(self)

    def _stage_to_image_builders_mapping(self):
        ordered = OrderedDict()
        for stage_name in self.config.stages:
            stage = ordered[stage_name] = OrderedDict()
            for image_name, image_config in self.config.image_configs.items():
                if image_config.stage == stage_name:
                    stage[image_name] = ImageBuilder(self, image_config)
        return ordered

    @property
    def image_builders(self):
        for image_builders in self.images.values():
            for image_builder in image_builders.values():
                yield image_builder

    @property
    def test_tag(self):
        return "{}b{}t".format(self.build_num, self.job_num)

    @property
    def test_name(self):
        return "{}{}".format(self.conf.name, self.test_tag)


class ImageBuilder:

    def __init__(self, builder: Builder, image_config: ImageConfig):
        self.builder = builder
        self.client = builder.client
        self.config = image_config

        self.environment = {
            **builder.config.environment,
            **image_config.environment
        }

        self.volumes = image_config.volumes.copy()

        self.script = None
        self.archive = None

        self.exception = None

    def ensure_from_image(self):
        image = self.config.from_image

        if not image:
            return

        if image in self.builder.config.image_configs:
            # image is built by shipmaster
            return

        if not self.client.images.list(image):
            self.client.images.pull(image, stream=False)

    def start_and_commit(self, container, cmd, e):
        client = self.client

        self.notify(e.before().action('archive_upload'))
        container.put_archive('/', self.archive.getfile())
        self.notify(e.after().action('archive_upload'))

        self.notify(e.before().action('container_start'))
        container.start()
        output = e.after().action('output')
        for line in container.logs(stream=True):
            self.notify(output, line.decode().rstrip())
        self.notify(e.after().action('container_start'))

        #result = client.wait(container)
        result = 1
        if result == 0:
            # Only tag image if container was built successfully.
            repository, tag = self.image_name, None
            if ':' in repository:
                repository, tag = repository.split(':')
            conf = client.create_container_config(self.image_name, cmd, working_dir=APP_PATH)
            self.notify(e.before().action('container_commit'))
            client.commit(container, repository=repository, tag=tag, conf=conf)
            self.notify(e.after().action('container_commit'))

        self.notify(e.before().action('container_remove'))
        container.remove()
        self.notify(e.after().action('container_remove'))

        return result

    def create(self, script, labels=None):
        return self.client.containers.create(
            self.config.from_image, command=['/bin/sh', '-c', str(script.path)],
            volumes=[v.split(':')[1] for v in self.volumes],
            environment=self.environment,
            labels=labels or {}
        )

    def notify(self, event, extra=None):
        self.builder.plugins.notify(event, self, extra)

    def execute(self, modes=None):
        for mode in (modes or ['build', 'run', 'start']):
            if not getattr(self.config, mode):
                continue
            step = getattr(self, mode)
            e = Event.mode(mode)
            self.notify(e.before())
            try:
                step(e)
                self.notify(e.after())
            except Exception as exc:
                self.exception = exc
                self.notify(e.failed())
            finally:
                self.notify(e.cleanup())

    def build(self, e):
        self.ensure_from_image()

        self.script = Script('build.sh')
        self.notify(e.before().action('script'))
        self.script.write_all(self.config.build)
        self.notify(e.after().action('script'))

        self.archive = Archive(self.builder.config.workspace)
        self.notify(e.before().action('archive'))
        self.archive.add_script(self.script)
        for file in self.config.context:
            self.archive.add_project_file(file)
        self.notify(e.after().action('archive'))

        build_command = self.builder.plugins.contribute('build_command', self, self.config.build)
        if not build_command:
            build_command = "echo 'Image does not do anything.'"

        labels = {}
        if self.builder.commit_info:
            labels = {'git-'+k: v for k, v in self.builder.commit_info.items()}
            labels['shipmaster-build'] = self.builder.build_num

        return self.start_and_commit(self.create(self.script, labels), ['/bin/sh', '-c', build_command], e)

    def run(self, e):
        self.script = Script('run.sh')
        self.notify(e.before().action('script'))
        self.script.write_all(self.config.build)
        self.notify(e.after().action('script'))
        #, compose: ComposeProject, reports=None
        logger.info('Running tests in {}...'.format(self.image_name))
        service = compose.get_service('test')  # type: Service
        compose.up(service.get_dependency_names())
        try:
            return self._run_test_container(service, reports)
        finally:
            # Stop and delete containers but don't remove any images
            compose.down(None, include_volumes=True)
            # Finally remove just the test image
            service.remove_image(service.image_name)

    def _run_test_container(self, service, reports):

        if reports:
            self.volumes.append(
                "{}:{}".format(reports, os.path.join(APP_PATH, 'reports'))
            )

        container = service.create_container(
            one_off=True,
            volumes=map(VolumeSpec.parse, self.volumes),
            environment=self.environment,
        )

        service.start_container(container)
        for line in container.logs(stream=True):
            logger.info(line.decode().rstrip())

        result = service.client.wait(container.id)
        if result != 0:
            logger.error("Test run failed.")

        return result

    def start(self, e):
        #, compose: ComposeProject, service_name

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
