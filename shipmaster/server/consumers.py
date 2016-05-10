import os
import subprocess
from .models import Build, Job
from ..base.utils import UnbufferedLineIO


def run(command, log=None, cwd=None, env=None):
    env = {**os.environ, **(env or {})}
    log.write("+ {}".format(' '.join(command)))
    subprocess.run(
        command, cwd=cwd, env=env, stderr=subprocess.STDOUT, stdout=log, check=True
    )


def build_app(message):

    build = Build.from_path(message.content['path'])

    with open(build.path.log, 'a') as buffered:

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


def deploy_app(message):
    build = Build.from_path(message.content['path'])
    with open(build.path.log, 'a') as buffered:
        log = UnbufferedLineIO(buffered)
        project = build.get_project(log)
        project.app.deploy()


def run_test(message):
    job = Job.from_path(message.content['path'])
    with open(job.path.log, 'a') as buffered:
        log = UnbufferedLineIO(buffered)
        project = job.get_project(log)
        job.job_started()
        project.test.build()
        job.job_finished()
