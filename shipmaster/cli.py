import os
import sys
import argparse
from docker import Client
from .config import ShipmasterConf
from .builder import LayerBuilder
from . import services


def parse_arguments():

    parser = argparse.ArgumentParser(
        prog="shipmaster"
    )

    parser.add_argument('layer', help='Layer to build, start and run.', choices=['base', 'app', 'test', 'dev'])

    parser.add_argument("--rebuild", help="Rebuild layer.", action="store_true")
    parser.add_argument("--script", help="Output build script and exit.", action="store_true")
    parser.add_argument("--debug-ssh-agent", help="Show some output related to ssh-agent forwarding.", action="store_true")

    return parser.parse_args()


def print_image_info(prefix, image):
    image_hash = image['Id'].split(':')[1]
    print("{}: {} {}".format(prefix, image['RepoTags'][0], image_hash[:12]))


def build_image_if_not_exists(args, layer, conf, client):
    layer_conf = getattr(conf, layer)
    image_details = client.images(layer_conf.image_name)
    if (args.layer == layer and args.rebuild) or not image_details:
        print("Building {}: {}".format(layer.capitalize(), layer_conf.image_name))
        builder = LayerBuilder(args.layer, conf, args.debug_ssh_agent)
        builder.build(client)
        image_details = client.images(layer_conf.image_name)
    print_image_info(layer.capitalize(), image_details[0])


def main():

    args = parse_arguments()
    client = Client('unix://var/run/docker.sock')
    conf = ShipmasterConf.from_filename(os.path.join(os.getcwd(), '.shipmaster.yaml'))

    if args.script:
        builder = LayerBuilder(args.layer, conf, args.debug_ssh_agent)
        builder.write_script(sys.stdout)
        return

    build_image_if_not_exists(args, 'base', conf, client)

    if args.layer != 'base':
        build_image_if_not_exists(args, args.layer, conf, client)
        services.up(conf, client)
