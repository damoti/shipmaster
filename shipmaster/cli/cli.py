import os
import sys
import argparse
import logging
from ..base.builder import Project
from ..base.config import ProjectConf


logger = logging.getLogger('shipmaster')

LAYERS = ['base', 'app', 'test']


def parse_arguments():

    parser = argparse.ArgumentParser(
        prog="shipmaster"
    )

    subparsers = parser.add_subparsers(dest='command')
    subparsers.required = True

    build = subparsers.add_parser('build', help="Builds a docker layer.")
    build.add_argument('layer', help="Layer to build.", choices=LAYERS)
    build.add_argument('--editable', help="Mount local sources instead of uploading a copy to container.", action='store_true')
    build.add_argument("--script", help="Output build script and exit.", action="store_true")
    build.add_argument("--build-all", help="Build parent layers if they don't exist.", action="store_true")
    build.add_argument("--rebuild", help="Rebuild this layer.", action="store_true")
    build.add_argument("--rebuild-all", help="Rebuild this layer and all parent layers.", action="store_true")
    build.add_argument("--debug-ssh-agent", help="Show some output related to ssh-agent forwarding.", action="store_true")
    build.set_defaults(command=build_command)

    test = subparsers.add_parser('test', help="Runs the test layer.")
    test.set_defaults(command=test_command)

    return parser.parse_args()


def build_command(args, project):

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
    """
    Notes:
        Things that should be possible via command line:
            - build/rebuild base image
            - build app image (with mounted (--editable) and copied default)
            - build and run a test image
            - deploy app image locally (local docker-compose.yml)
    """
    args = parse_arguments()
    logging.basicConfig(level=logging.INFO)  # TODO: set from args
    project = Project(
        ProjectConf.from_workspace(os.getcwd()),
        commit_info={},
        debug_ssh=getattr(args, 'debug_ssh_agent', False),
        editable=getattr(args, 'editable', False)
    )
    if hasattr(args, 'command'):
        args.command(args, project)
