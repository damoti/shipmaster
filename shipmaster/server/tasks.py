import os
import select
import logging
import subprocess
from logging import FileHandler, INFO, ERROR
from docker.errors import APIError
from .models import Build, Job, Infrastructure
from ..base.utils import UnbufferedLineIO
from celery import shared_task


_LOG_HANDLERS = None


def _replace_handlers(channel, file):
    global _LOG_HANDLERS

    if _LOG_HANDLERS:
        old_file, old_channel = _LOG_HANDLERS
        old_file.close()
        logging.root.removeHandler(old_file)
        logging.root.removeHandler(old_channel)

    _LOG_HANDLERS = (file, channel)
    logging.root.addHandler(file)
    logging.root.addHandler(channel)


class ChannelHandler(logging.Handler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel = None

    def emit(self, record):
        pass


def run(command, logger, cwd=None, env=None):

    logger.log(INFO, "+ {}".format(' '.join(command)))

    env = {**os.environ, **(env or {})}
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, env=env)

    log_level = {child.stdout: INFO,
                 child.stderr: ERROR}

    def check_io():
        ready_to_read = select.select([child.stdout, child.stderr], [], [], 1000)[0]
        for io in ready_to_read:
            line = io.readline()
            logger.log(log_level[io], line[:-1])

    # keep checking stdout/stderr until the child exits
    while child.poll() is None:
        check_io()

    check_io()  # check again to catch anything after the process exits

    return child.wait()


@shared_task
def build_app(path):

    build = Build.from_path(path)

    _replace_handlers(ChannelHandler(build), FileHandler(build.path.build_log))

    assert not build.has_cloning_started

    git_ssh_command = {"GIT_SSH_COMMAND": "ssh -F {}".format(build.shipmaster.path.ssh_config)}

    build.cloning_started()
    run(["git", "clone",
         "--depth=1",
         "--branch={}".format(build.branch),
         build.repo.project_git,
         build.path.workspace],
        logging.getLogger('git'),
        env=git_ssh_command)
    build.cloning_finished()

    # project doesn't exist until after checkout finishes
    project = build.get_project()

    build.build_started()
    project.app.build()
    build.build_finished()


@shared_task
def deploy_app(path, service):

    build = Build.from_path(path)

    _replace_handlers(ChannelHandler(build), FileHandler(build.path.deployment_log))

    assert not build.has_deployment_started

    project = build.get_project()

    build.deployment_started()
    try:
        project.app.deploy(build.shipmaster.infrastructure.compose, service)
    except APIError as e:
        logging.root.exception(e.explanation.decode())
    finally:
        build.deployment_finished()


@shared_task
def test_app(path):
    job = Job.from_path(path)
    _replace_handlers(ChannelHandler(job), FileHandler(job.path.log))
    project = job.get_project()
    job.job_started()
    project.test.build()
    job.job_finished()


@shared_task
def sync_infrastructure(path):

    infra = Infrastructure.from_path(path)

    _replace_handlers(ChannelHandler(infra), FileHandler(infra.path.git_log, 'w'))

    assert not infra.is_checkout_running

    git_ssh_command = {"GIT_SSH_COMMAND": "ssh -F {}".format(infra.shipmaster.path.ssh_config)}

    infra.checkout_started()
    try:
        git_log = logging.getLogger('git')
        if os.path.exists(infra.path.src):
            run(["git", "pull"], git_log, cwd=infra.path.src, env=git_ssh_command)
        else:
            run(["git", "clone", infra.project_git, infra.path.src], git_log, env=git_ssh_command)
    except:
        logging.root.exception("failed to update infrastructure sources")
    finally:
        infra.checkout_finished()
