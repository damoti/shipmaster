import os
import select
import logging
import subprocess
from logging import FileHandler, INFO, ERROR
from .models import Build, Deployment, Test, Infrastructure
from celery import shared_task

logger = logging.getLogger('shipmaster')
_LOG_HANDLER = None


def _replace_handler(handler):
    logger.setLevel(logging.INFO)
    global _LOG_HANDLER
    if _LOG_HANDLER:
        _LOG_HANDLER.close()
        logger.removeHandler(_LOG_HANDLER)
    _LOG_HANDLER = handler
    logger.addHandler(handler)


def run(command, cwd=None, env=None):
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
            logger.log(log_level[io], line.rstrip())

    while child.poll() is None:
        check_io()

    return child.wait()


@shared_task
def build_app(path):
    build = Build.from_path(path)
    _replace_handler(FileHandler(build.path.log))
    git_ssh_command = {"GIT_SSH_COMMAND": "ssh -F {}".format(build.shipmaster.path.ssh_config)}

    build.cloning_started()
    try:
        result = run(
            ["git", "clone",
             "--depth=1",
             "--branch={}".format(build.branch),
             build.repo.project_git,
             build.path.workspace],
            env=git_ssh_command
        )
        if result != 0:
            return build.failed()
        build.succeeded()
    except:
        logger.exception("Git clone process threw an exception:")
        return build.failed()
    finally:
        build.cloning_finished()

    build.build_started()
    try:
        project = build.get_project()
        result = project.app.build()
        if result != 0:
            return build.failed()
        build.succeeded()
    except:
        logger.exception("Build process threw an exception:")
        build.failed()
    finally:
        build.build_finished()


@shared_task
def deploy_app(path):
    deployment = Deployment.from_path(path)
    _replace_handler(FileHandler(deployment.path.log))
    project = deployment.get_project()
    deployment.started()
    try:
        result = project.app.deploy(
            deployment.shipmaster.infrastructure.compose,
            deployment.destination
        )
        deployment.failed() if result != 0 else deployment.succeeded()
    except:
        logger.exception("Deployment process threw an exception:")
        deployment.failed()
    finally:
        deployment.finished()


@shared_task
def test_app(path):
    test = Test.from_path(path)
    _replace_handler(FileHandler(test.path.log))
    compose = test.get_compose()
    project = test.get_project()
    test.started()
    try:
        result = project.test.build()
        if result != 0:
            return test.failed()
        result = project.test.run(compose)
        if result != 0:
            return test.failed()
        test.succeeded()
    except:
        logger.exception("Test process threw an exception:")
        test.failed()
    finally:
        test.finished()


@shared_task
def sync_infrastructure(path):
    infra = Infrastructure.from_path(path)
    if infra.is_checkout_running: return
    _replace_handler(FileHandler(infra.path.git_log, 'w'))
    git_ssh_command = {"GIT_SSH_COMMAND": "ssh -F {}".format(infra.shipmaster.path.ssh_config)}
    infra.checkout_started()
    try:
        if os.path.exists(infra.path.src):
            result = run(["git", "pull"], cwd=infra.path.src, env=git_ssh_command)
        else:
            result = run(["git", "clone", infra.project_git, infra.path.src], env=git_ssh_command)
        infra.failed() if result != 0 else infra.succeeded()
    except:
        logger.exception("Failed to update infrastructure sources:")
        infra.failed()
    finally:
        infra.checkout_finished()
