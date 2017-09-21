import unittest

from compose.cli.docker_client import docker_client
from compose.config.config import resolve_environment
from compose.config.environment import Environment
from compose.progress_stream import stream_output
from compose.service import Service

from shipmaster.core.plugins import Plugin, PluginManager

LABEL_PROJECT = "shipmaster.test"


def pull_busybox(client):
    client.pull('busybox:latest', stream=False)


def get_links(container):
    links = container.get('HostConfig.Links') or []

    def format_link(link):
        _, alias = link.split(':')
        return alias.split('/')[-1]

    return [format_link(link) for link in links]


class TestingPlugin(Plugin):

    def __init__(self, builder):
        super().__init__(builder)
        self.builds = []
        self.runs = []
        self.starts = []
        self.log = []

    def handle_log_output(self, b, line):
        self.log.append(line)

    def after_build(self, image_builder):
        self.builds.append(image_builder.config.name)

    def after_run(self, image_builder):
        self.runs.append(image_builder.config.name)

    def after_start(self, image_builder):
        self.starts.append(image_builder.config.name)

    def _failed(self, image_builder):
        raise image_builder.exception
    failed_build = _failed
    failed_run = _failed
    failed_start = _failed


class DockerClientTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = docker_client(Environment(), '3.0')
        PluginManager.plugin_classes.append(TestingPlugin)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        PluginManager.plugin_classes.remove(TestingPlugin)

    def tearDown(self):
        for c in self.client.containers(
                all=True,
                filters={'label': '%s=composetest' % LABEL_PROJECT}):
            self.client.remove_container(c['Id'], force=True)

        for i in self.client.images(
                filters={'label': 'com.docker.compose.test_image'}):
            self.client.remove_image(i)

        volumes = self.client.volumes().get('Volumes') or []
        for v in volumes:
            if 'composetest_' in v['Name']:
                self.client.remove_volume(v['Name'])

        networks = self.client.networks()
        for n in networks:
            if 'composetest_' in n['Name']:
                self.client.remove_network(n['Name'])

    def get_test_plugin(self, builder):
        for plugin in builder.plugins:
            if isinstance(plugin, TestingPlugin):
                return plugin

    def create_service(self, name, **kwargs):
        if 'image' not in kwargs and 'build' not in kwargs:
            kwargs['image'] = 'busybox:latest'

        if 'command' not in kwargs:
            kwargs['command'] = ["top"]

        kwargs['environment'] = resolve_environment(
            kwargs, Environment.from_env_file(None)
        )
        labels = dict(kwargs.setdefault('labels', {}))
        labels['com.docker.compose.test-name'] = self.id()

        return Service(name, client=self.client, project='composetest', **kwargs)

    def check_build(self, *args, **kwargs):
        kwargs.setdefault('rm', True)
        build_output = self.client.build(*args, **kwargs)
        stream_output(build_output, open('/dev/null', 'w'))
