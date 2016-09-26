import os
import select
import logging
import subprocess
from logging import FileHandler, INFO, ERROR
from docker.errors import APIError
from .models import Build, Deployment, Test, Infrastructure
from celery import shared_task


_FILE_LOG_HANDLERS = None


def _replace_handler(handler):
    logging.basicConfig(level=logging.INFO)
    global _FILE_LOG_HANDLERS
    if _FILE_LOG_HANDLERS:
        _FILE_LOG_HANDLERS.close()
        logging.root.removeHandler(_FILE_LOG_HANDLERS)
    _FILE_LOG_HANDLERS = handler
    logging.root.addHandler(handler)


def run(command, cwd=None, env=None):
    logger = logging.getLogger(command[0])
    logger.info("+ {}".format(' '.join(command)))

    env = {**os.environ, **(env or {})}
    child = subprocess.Popen(
        command,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=cwd, env=env, universal_newlines=True
    )

    log_level = {child.stdout: INFO,
                 child.stderr: ERROR}

    def check_io():
        ready_to_read = select.select([child.stdout, child.stderr], [], [], 1000)[0]
        for io in ready_to_read:
            line = io.readline()
            logger.log(log_level[io], line)

    while child.poll() is None:
        check_io()

    return child.wait()


@shared_task
def build_app(path):

    build = Build.from_path(path)

    _replace_handler(FileHandler(build.path.log))

    assert not build.has_cloning_started

    git_ssh_command = {"GIT_SSH_COMMAND": "ssh -F {}".format(build.shipmaster.path.ssh_config)}

    build.cloning_started()
    run(["git", "clone",
         "--progress",
         "--depth=1",
         "--branch={}".format(build.branch),
         build.repo.project_git,
         build.path.workspace],
        env=git_ssh_command)
    build.cloning_finished()

    # project doesn't exist until after checkout finishes
    project = build.get_project()

    build.build_started()
    project.app.build()
    build.build_finished()


@shared_task
def deploy_app(path):

    deployment = Deployment.from_path(path)

    _replace_handler(FileHandler(deployment.path.log))

    project = deployment.get_project()

    deployment.started()
    try:
        project.app.deploy(deployment.shipmaster.infrastructure.compose, deployment.destination)
    except APIError as e:
        logging.root.exception(e.explanation.decode())
    finally:
        deployment.finished()


@shared_task
def test_app(path):
    job = Test.from_path(path)
    _replace_handler(FileHandler(job.path.log))
    project = job.get_project()
    job.job_started()
    project.test.build()
    job.job_finished()


@shared_task
def sync_infrastructure(path):

    infra = Infrastructure.from_path(path)

    _replace_handler(FileHandler(infra.path.git_log, 'w'))

    assert not infra.is_checkout_running

    git_ssh_command = {"GIT_SSH_COMMAND": "ssh -F {}".format(infra.shipmaster.path.ssh_config)}

    infra.checkout_started()
    try:
        if os.path.exists(infra.path.src):
            run(["git", "pull"], cwd=infra.path.src, env=git_ssh_command)
        else:
            run(["git", "clone", infra.project_git, infra.path.src], env=git_ssh_command)
    except:
        logging.root.exception("failed to update infrastructure sources")
    finally:
        infra.checkout_finished()
