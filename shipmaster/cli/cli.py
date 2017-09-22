import argparse
import logging
import os
import sys

from shipmaster.core.plugins import Platform, PluginManager
from shipmaster.core.builder import Builder
from shipmaster.core.config import BuildConfig

logger = logging.getLogger('shipmaster')


def run_command(args):
    config = BuildConfig.from_workspace(os.getcwd())
    builder = Builder(config, args, commit_info={})


def run_parser(parsers):
    p = parsers.add_parser("run", help="Run build stages.")
    p.add_argument('stage', help="Stage to build.")
    p.add_argument('--editable', help="Mount local sources instead of uploading a copy to container.", action='store_true')
    p.add_argument("--script", help="Output run script and exit.", action="store_true")
    p.add_argument("--run-all", help="Build parent layers if they don't exist.", action="store_true")
    p.add_argument("--rerun", help="Rerun this layer.", action="store_true")
    p.add_argument("--rerun-all", help="Rerun this layer and all parent layers.", action="store_true")
    p.set_defaults(command=run_command)
    return p


def argument_parser():

    parser = argparse.ArgumentParser(
        prog="shipmaster"
    )

    subparsers = parser.add_subparsers(dest='command')
    subparsers.required = True

    commands = {
        'run': run_parser(subparsers)
    }

    for plugin in PluginManager.plugin_classes:
        plugin.contribute_to_argparse(subparsers, commands)

    return parser


def parse_args(args):
    return argument_parser().parse_args(args)


def main():
    PluginManager.load(Platform.cli)
    parser = argument_parser()
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if hasattr(args, 'command'):
        config = BuildConfig.from_workspace(os.getcwd())
        args.command(args, config)
    else:
        parser.print_help()
