import os
import sys
import argparse
import logging
from ..base.builder import Project
from ..base.config import ProjectConfig
from .graph import print_graph


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
    run.add_argument("--debug-ssh-agent", help="Show some output related to ssh-agent forwarding.", action="store_true")
    run.set_defaults(command=run_command)

    test = subparsers.add_parser('test', help="Runs the test layer.")
    test.set_defaults(command=test_command)

    config = subparsers.add_parser('config', help="Show the config.")
    config.set_defaults(command=lambda args, project: project.config.dump())

    graph = subparsers.add_parser('graph', help="Show the graph.")
    graph.set_defaults(command=print_graph)

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
    config = ProjectConfig.from_workspace(os.getcwd())
    args = parse_arguments(config)
    logging.basicConfig(level=logging.INFO)  # TODO: set from args
    project = Project(
        config,
        commit_info={},
        debug_ssh=getattr(args, 'debug_ssh_agent', False),
        editable=getattr(args, 'editable', False)
    )
    if hasattr(args, 'command'):
        args.command(args, project)
