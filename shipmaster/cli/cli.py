import argparse
import logging
import os
import sys

from shipmaster.core.plugins import Platform, PluginManager
from shipmaster.core.builder import Builder
from shipmaster.core.config import BuildConfig

logger = logging.getLogger('shipmaster')


def parse_arguments(project):

    parser = argparse.ArgumentParser(
        prog="shipmaster"
    )

    subparsers = parser.add_subparsers(dest='command')
    subparsers.required = True

    run = subparsers.add_parser('run', help="Run build stages.")
    run.add_argument('image', help="Image to run.", choices=project.images.keys())
    run.add_argument('--editable', help="Mount local sources instead of uploading a copy to container.", action='store_true')
    run.add_argument("--script", help="Output run script and exit.", action="store_true")
    run.add_argument("--run-all", help="Build parent layers if they don't exist.", action="store_true")
    run.add_argument("--rerun", help="Rerun this layer.", action="store_true")
    run.add_argument("--rerun-all", help="Rerun this layer and all parent layers.", action="store_true")
    run.set_defaults(command=run_command)

    config = subparsers.add_parser('config', help="Show the config.")
    config.set_defaults(command=lambda args, project: project.config.dump())

    for plugin in PluginManager.plugin_classes:
        plugin.contribute_to_argparse(subparsers, {
            'run': run,
            'config': config,
        })

    return parser.parse_args()


def run_command(args, project):

    if args.script:
        layer = getattr(project, args.layer)
        print(layer.get_script().source)
        return

    built = []
    for layer_name in LAYERS:

        layer = getattr(project, layer_name)

        logger.info("Checking for existing {} image.".format(layer_name))

        if layer_name == args.layer:

            if layer.exists():
                if args.rebuild or args.rebuild_all:
                    layer.remove()
                else:
                    logger.info("{} image already exists, run with '--rebuild' to rebuild.".format(layer_name.capitalize()))
                    sys.exit(1)
            layer.build()
            logger.info("Done.")
            break

        else:

            if not layer.exists():
                if not args.build_all:
                    logger.info("Parent image {} doesn't exist, run with '--build-all' to build it.".format(layer_name.capitalize()))
                    sys.exit(1)
                layer.build()
            elif args.rebuild_all:
                layer.remove()
                layer.build()


def test_command(args, project):
    from compose.cli.command import get_project as get_compose
    project.test.run(
        get_compose(
            os.getcwd(),
            project_name=project.test_name,
            host='unix://var/run/docker.sock'
        )
    )


def main():
    PluginManager.load(Platform.cli)
    config = BuildConfig.from_workspace(os.getcwd())
    args = parse_arguments(config)
    logging.basicConfig(level=logging.INFO)  # TODO: set from args
    builder = Builder(config, args, commit_info={})
    if hasattr(args, 'command'):
        args.command(args, builder)
