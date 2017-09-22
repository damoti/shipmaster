from .testcases import DockerClientTestCase

from shipmaster.core.builder import Builder
from shipmaster.core.config import BuildConfig


class ImageBuildTests(DockerClientTestCase):

    def test_simple_build(self):
        build_config = BuildConfig.from_kwargs(
            '', name='test-project', images={
                'build': {
                    'from': 'busybox:latest',
                    'build': 'echo "hello world" > hello_world',
                }
            }
        )

        builder = Builder(build_config)
        for step in builder.image_builders:
            step.execute()

        testing = self.get_test_plugin(builder)
        self.assertEqual(testing.builds, ['build'])

    def _test_common(self):
        build_config = BuildConfig.from_kwargs(
            '', name='test-project',
            stages=['build', 'test', 'deploy'],
            images={
                'app': {
                    'stage': 'build',
                    'from': 'busybox:latest',
                    'run': 'ls'
                },
                'test': {
                    'from': 'app',
                    'run': 'ls'
                },
                'sandbox': {
                    'stage': 'deploy',
                    'from': 'app',
                    'run': 'ls',
                    'deploy': 'automatic',
                },
                'production': {
                    'stage': 'deploy',
                    'from': 'app',
                    'run': 'ls',
                    'deploy': 'manual'
                }
            }
        )

        builder = Builder(build_config)
        for step in builder.image_builders:
            step.execute()

        testing = self.get_test_plugin(builder)
        self.assertEquals(testing.builds, ['app', 'test'])


class ImageBuildRunStartTests(DockerClientTestCase):

    def x_test_simple_workflow(self):
        build_config = BuildConfig.from_kwargs(
            '', name='test-project', stages=['build'], images={
                'app': {
                    'stage': 'build',
                    'from': 'busybox:latest',
                    'build': 'echo "hello world" > hello_world',
                    'run': 'cat hello_world',
                    'start': 'top'
                }
            }
        )

        builder = Builder(build_config)
        testing = self.get_test_plugin(builder)
        image_builder = next(iter(builder.image_builders))

        image_builder.execute(['build', 'run'])
        self.assertEquals(testing.builds, ['app'])
        self.assertEquals(testing.runs, ['app'])
        map(print, testing.log)
