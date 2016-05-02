import os
import sys
import argparse
from docker import Client
from compose.project import Project
from compose.cli.main import log_printer_from_project, filter_containers_to_service_names
from .config import ShipmasterConf
from .builder import Builder, BaseBuilder, LayerBuilder


def parse_arguments():

    parser = argparse.ArgumentParser(
        prog="shipmaster"
    )

    parser.add_argument('layer', help='Layer to build, start and run.', choices=['base', 'app', 'test', 'dev'])

    parser.add_argument("--rebuild", help="Rebuild layer.", action="store_true")
    parser.add_argument("--script", help="Output build script and exit.", action="store_true")

    auth = parser.add_argument_group('Authenticating with remote repositories:')
    auth.add_argument("--ssh-agent", dest="use_ssh_agent", help="Use ssh-agent forwarding.", action="store_true")
    auth.add_argument("--no-ssh-agent", dest="use_ssh_agent", help="Don't use ssh-agent forwarding.", action="store_false")
    auth.set_defaults(use_ssh_agent=True)
    auth.add_argument("--debug-ssh-agent", help="Show some output related to ssh-agent forwarding.", action="store_true")

    return parser.parse_args()


def print_image_info(prefix, image):
    image_hash = image['Id'].split(':')[1]
    print("{} {} {}".format(prefix, image['RepoTags'][0], image_hash[:12]))


def main():

    args = parse_arguments()
    client = Client('unix://var/run/docker.sock')
    conf = ShipmasterConf.from_filename(os.path.join(os.getcwd(), '.shipmaster.yaml'))
    builder = Builder.from_layer(args, args.layer, conf)

    if args.script:
        print(builder.script)
        return

    base_image = client.images(conf.base.image_name)
    if (args.layer == 'base' and args.rebuild) or not base_image:
        print("Building Base: "+conf.base.image_name)
        BaseBuilder(conf.base).build(client)
        base_image = client.images(conf.base.image_name)
    print_image_info("Base:", base_image[0])

    if args.layer == 'dev':

        dev_image = client.images(conf.dev.image_name)
        if args.rebuild or not dev_image:
            builder.build(client)
            dev_image = client.images(conf.dev.image_name)
        print_image_info("Base:", dev_image[0])

        project = Project.from_config(conf.name, conf.services.compose, client)
        to_attach = project.up(conf.services.names)

        log_printer = log_printer_from_project(
            project,
            filter_containers_to_service_names(to_attach, ['app']),
            False,
            {'follow': True},
            True,
            event_stream=project.events(service_names=conf.services.names))
        log_printer.run()

    elif args.layer == 'app':

        app_image = client.images(conf.app.image_name)
        if args.rebuild or not app_image:
            builder.build(client)
            app_image = client.images(conf.app.image_name)
        print_image_info("App:", app_image[0])

        project = Project.from_config(conf.name, conf.services.compose, client)
        to_attach = project.up(conf.services.names)

        log_printer = log_printer_from_project(
            project,
            filter_containers_to_service_names(to_attach, ['app']),
            False,
            {'follow': True},
            True,
            event_stream=project.events(service_names=conf.services.names))
        log_printer.run()
