import os
import logging
import subprocess
from docker.errors import APIError
from .models import Build, Job, Infrastructure
from ..base.utils import UnbufferedLineIO
from celery import shared_task


def run(command, log=None, cwd=None, env=None):
    env = {**os.environ, **(env or {})}
    log.write("+ {}".format(' '.join(command)))
    subprocess.run(
        command, cwd=cwd, env=env, stderr=subprocess.STDOUT, stdout=log, check=True
    )


@shared_task
def build_app(path):

    build = Build.from_path(path)

    assert not build.has_cloning_started

    with open(build.path.build_log, 'a') as buffered:

        log = UnbufferedLineIO(buffered)

        git_ssh_command = {"GIT_SSH_COMMAND": "ssh -F {}".format(build.shipmaster.path.ssh_config)}

        build.cloning_started()
        run(["git", "clone",
             "--depth=1",
             "--branch={}".format(build.branch),
             build.repo.project_git,
             build.path.workspace],
            log=log, env=git_ssh_command)
        build.cloning_finished()

        # project doesn't exist until after checkout finishes
        project = build.get_project(log)

        build.build_started()
        project.app.build()
        build.build_finished()


@shared_task
def deploy_app(path, service):

    build = Build.from_path(path)

    assert not build.has_deployment_started

    with open(build.path.deployment_log, 'a') as buffered:

        log = UnbufferedLineIO(buffered)

        project = build.get_project(log)

        build.deployment_started()
        try:
            project.app.deploy(build.shipmaster.infrastructure.compose, service)
        except APIError as e:
            print(e.explanation)
            log.write(e.explanation.decode())
            raise
        finally:
            build.deployment_finished()


@shared_task
def test_app(path):
    job = Job.from_path(path)
    with open(job.path.log, 'a') as buffered:
        log = UnbufferedLineIO(buffered)
        project = job.get_project(log)
        job.job_started()
        project.test.build()
        job.job_finished()


@shared_task
def sync_infrastructure(path):

    infra = Infrastructure.from_path(path)

    assert not infra.is_checkout_running

    with open(infra.path.git_log, 'w') as buffered:

        log = UnbufferedLineIO(buffered)

        git_ssh_command = {"GIT_SSH_COMMAND": "ssh -F {}".format(infra.shipmaster.path.ssh_config)}

        infra.checkout_started()
        try:
            if os.path.exists(infra.path.src):
                run(["git", "pull"], cwd=infra.path.src, log=log, env=git_ssh_command)
            else:
                run(["git", "clone", infra.project_git, infra.path.src],
                    log=log, env=git_ssh_command)
        finally:
            infra.checkout_finished()
