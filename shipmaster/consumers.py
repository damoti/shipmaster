import os
import subprocess
from docker import Client
from .config import ShipmasterConf
from .models import Build
from .builder import LayerBuilder


def run(command, log, cwd=None, env=None):
    env = {**os.environ, **(env or {})}
    with open(log, 'a') as logfile:
        subprocess.run(
            command, cwd=cwd, env=env, stderr=subprocess.STDOUT, stdout=logfile, check=True
        )


def build_app(message):
    build = Build.from_path(message.content['path'])
    repo = build.repo
    shipmaster = repo.shipmaster

    git_ssh_command = {"GIT_SSH_COMMAND": "ssh -F {}".format(build.path.ssh_config)}

    run(["git", "clone", "--depth=1", "--branch=docker", repo.project_git, build.path.workspace],
        build.path.log, env=git_ssh_command)

    conf = ShipmasterConf.from_filename('app', build.path.conf)
    conf.services.environment.update(git_ssh_command)
    conf.services.volumes += ['{0}:{0}'.format(shipmaster.path.ssh_dir)]

    client = Client('unix://var/run/docker.sock')

    builder = LayerBuilder('app', conf)
    builder.build(client)
