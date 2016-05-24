import os
import sys
import argparse
from ..base.builder import Project
from ..base.config import ProjectConf


def parse_arguments():

    parser = argparse.ArgumentParser(
        prog="shipmaster"
    )

    parser.add_argument('layer', help='Layer to build, start and run.', choices=['base', 'app', 'test', 'dev'])

    parser.add_argument("--rebuild", help="Rebuild layer.", action="store_true")
    parser.add_argument("--script", help="Output build script and exit.", action="store_true")
    parser.add_argument("--debug-ssh-agent", help="Show some output related to ssh-agent forwarding.", action="store_true")

    return parser.parse_args()


def main():

    args = parse_arguments()
    proj = Project(
        ProjectConf.from_workspace(os.getcwd()),
        debug_ssh=args.debug_ssh_agent,
        verbose=True,
        log=sys.stdout
    )

    if args.script:
        layer = getattr(proj, args.layer)
        print(layer.get_script().source)
        return

    if args.layer == 'base':
        proj.base.build()

    elif args.layer == 'app':
        if not proj.app.exists():
            proj.app.build()
        print("Deploying App")
        proj.app.deploy()

    elif args.layer == 'test':
        proj.test.build()
        proj.dev.test()

    elif args.layer == 'dev':
        if proj.dev.exists():
            args.rebuild and proj.dev.remove()
        if not proj.dev.exists():
            proj.dev.build()
        proj.dev.start()
