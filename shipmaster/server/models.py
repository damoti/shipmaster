import os
import re
import json
import time
import shutil
import requests
import subprocess

from urllib.parse import urljoin
from collections import OrderedDict
from ruamel import yaml

from github3 import GitHub
from compose.cli.command import get_project as get_compose
from django.core.urlresolvers import reverse
from django.conf import settings

from shipmaster.base.builder import Project
from shipmaster.base.config import ProjectConf

from .user import User


class YamlPath:
    @property
    def yaml(self):
        raise NotImplementedError


class YamlModel:

    @classmethod
    def parent_class(cls, path):
        raise NotImplementedError

    def __init__(self, **kwargs):
        self.path = YamlPath()
        self.dict = OrderedDict(**kwargs)

    @classmethod
    def load(cls, *args):
        model = cls(*args)
        with open(model.path.yaml, 'r') as file:
            model.dict = yaml.load(file)
        return model

    @classmethod
    def from_path(cls, path):
        parent_path = os.path.dirname(os.path.dirname(path))
        parent = cls.parent_class.from_path(parent_path)
        return cls.load(parent, os.path.basename(path))

    def save(self):
        with open(self.path.yaml, 'w') as file:
            file.write(yaml.dump(self.dict))


class ShipmasterPath(YamlPath):

    def __init__(self, absolute):
        self.absolute = absolute

    @property
    def yaml(self):
        return os.path.join(self.absolute, 'config.yaml')

    @property
    def repos_dir(self):
        return os.path.join(self.absolute, 'repos')

    @property
    def ssh_dir(self):
        return os.path.join(self.absolute, 'ssh')

    @property
    def keys_dir(self):
        return os.path.join(self.ssh_dir, 'keys')

    @property
    def ssh_config(self):
        return os.path.join(self.ssh_dir, 'ssh_config')


class GitHubStatusUpdater:

    def __init__(self, oauth):
        self.oauth = oauth


class Shipmaster(YamlModel):

    def __init__(self, data_path, **kwargs):
        super().__init__(**kwargs)
        self.path = ShipmasterPath(data_path)
        if not os.path.exists(self.path.yaml):
            self.save()

    @classmethod
    def from_path(cls, path):
        return cls.load(path)

    def update_ssh_config(self):
        with open(self.path.ssh_config, 'w') as config:
            for repo in self.repositories:
                config.write('Host '+repo.git_project_host+'\n')
                config.write('  HostName '+repo.git_host+'\n')
                config.write('  User git\n')
                config.write('  IdentityFile '+repo.path.private_key+'\n')

    def set_token_if_empty(self, token):
        if not self.token:
            self.token = token
            self.save()

    def get_github(self):
        return GitHub(token=self.token)

    @property
    def token(self):
        """ Shipmaster's integration with GitHub is a bit complicated
            due to how the GitHub API works.

            First, you have to register your Shipmaster installation as a
            GitHub "OAuth application". This allows Shipmaster to fetch
            access tokens for GitHub users and nothing else.

            Second, to allow Shipmaster to actually perform any actions
            inside of your GitHub organisation, it needs to be granted access
            through an existing GitHub user. Therefore, the first user to
            login-in to Shipmaster becomes the designated proxy user by which
            Shipmaster will execute all future GitHub API calls.
        """
        return self.dict.get('token')

    @token.setter
    def token(self, token):
        self.dict['token'] = token

    @property
    def repositories(self):
        for repo_name in os.listdir(self.path.repos_dir):
            yield Repository.load(self, repo_name)

    @property
    def infrastructure(self):
        if Infrastructure(self).exists():
            return Infrastructure.load(self)


class RepositoryPath(YamlPath):

    def __init__(self, shipmaster, name):
        self.shipmaster = shipmaster
        self.name = name

    @property
    def absolute(self):
        return os.path.join(self.shipmaster.path.repos_dir, self.name)

    @property
    def yaml(self):
        return os.path.join(self.absolute, 'config.yaml')

    @property
    def last_build_number(self):
        return os.path.join(self.absolute, 'last_build_number')

    @property
    def builds(self):
        return os.path.join(self.absolute, 'builds')

    @property
    def public_key(self):
        return self.private_key+'.pub'

    @property
    def private_key(self):
        return os.path.join(self.shipmaster.path.keys_dir, self.name)


class Repository(YamlModel):

    parent_class = Shipmaster

    #                 host      account     repo
    GIT_REGEX = "git@([\w\.]+):([\w\.\-]+)/([\w\.\-]+)\.git"

    def __init__(self, shipmaster, name, **kwargs):
        super().__init__(**kwargs)
        self.shipmaster = shipmaster  # type: Shipmaster
        self.name = name
        self.path = RepositoryPath(shipmaster, name)
        self.git_host = self.git_account = self.git_repo = ''

    def _parse_git(self):
        m = re.search(Repository.GIT_REGEX, self.git)
        if m:
            self.git_host = m.group(1)
            self.git_account = m.group(2)
            self.git_repo = m.group(3)

    def get_github(self):
        github = self.shipmaster.get_github()
        return github.repository(self.git_account, self.git_repo)

    @classmethod
    def load(cls, parent, name):
        self = super().load(parent, name)  # type: Repository
        self._parse_git()
        return self

    def increment_build_number(self):
        return increment_number_file(self.path.last_build_number)

    @property
    def git(self):
        return self.dict['git']

    @git.setter
    def git(self, git):
        self.dict['git'] = git

    @property
    def git_project_host(self):
        return "{}.{}".format(self.name, self.git_host)

    @property
    def project_git(self):
        return "git@{}:{}/{}.git".format(self.git_project_host, self.git_account, self.git_repo)

    @property
    def public_key(self):
        return open(self.path.public_key, 'r').read()

    def exists(self):
        return os.path.exists(self.path.absolute)

    @property
    def is_infrastructure(self):
        return False

    @classmethod
    def create(cls, shipmaster, name, git):
        repo = cls(shipmaster, name, git=git)
        repo._parse_git()

        if not os.path.exists(shipmaster.path.repos_dir):
            os.mkdir(shipmaster.path.repos_dir)

        os.mkdir(repo.path.absolute)
        if not repo.is_infrastructure:
            os.mkdir(repo.path.builds)
        try:
            keygen = "ssh-keygen -q -b 4096 -t rsa -N '' -f {}".format(repo.path.private_key)
            subprocess.check_output(keygen, shell=True, stderr=subprocess.STDOUT)
            repo.save()
        except:
            shutil.rmtree(repo.path.absolute, ignore_errors=True)
            raise

        shipmaster.update_ssh_config()

        return repo

    @property
    def builds(self):
        for build in os.listdir(self.path.builds):
            yield Build.load(self, build)

    @property
    def sorted_builds(self):
        return sorted(self.builds, key=lambda build: int(build.number), reverse=True)

    def __eq__(self, other):
        assert isinstance(other, Repository)
        return self.name == other.name


class InfrastructurePath(RepositoryPath):

    @property
    def src(self):
        return os.path.join(self.absolute, 'src')

    @property
    def checkout_running(self):
        return os.path.join(self.absolute, 'checkout.running')

    @property
    def git_log(self):
        return os.path.join(self.absolute, 'git.log')


class Infrastructure(Repository):

    parent_class = Shipmaster

    def __init__(self, shipmaster, name=None, **kwargs):
        super().__init__(shipmaster, 'infrastructure', **kwargs)
        self.path = InfrastructurePath(shipmaster, self.name)
        self.compose = None
        if os.path.exists(self.path.src):
            self.compose = get_compose(self.path.src, host='unix://var/run/docker.sock')

    @classmethod
    def load(cls, parent, name=None):
        return super().load(parent, 'infrastructure')  # type: Infrastructure

    @property
    def is_infrastructure(self):
        return True

    def sync(self):
        from .tasks import sync_infrastructure
        sync_infrastructure.delay(self.path.absolute)
        return self

    def checkout_started(self):
        assert not self.is_checkout_running
        record_time(self.path.checkout_running)

    def checkout_finished(self):
        assert self.is_checkout_running
        os.remove(self.path.checkout_running)

    @property
    def is_checkout_running(self):
        return os.path.exists(self.path.checkout_running)

    @property
    def has_log(self):
        return os.path.exists(self.path.git_log)

    @property
    def is_log_finished(self):
        if self.has_log and not self.is_checkout_running:
            return True
        return False

    @property
    def formatted_checkout_log(self):
        assert self.is_log_finished
        with open(self.path.git_log, 'r') as log_file:
            return log_file.read()

    # Compose

    def formatted_compose_config(self):
        return ''

    def get_deploy_destinations(self):
        if not self.compose:
            return []
        return [
            service.name
            for service in self.compose.services
            if 'io.shipmaster.deploy' in service.options.get('labels', {})
        ]


class BuildPath(YamlPath):

    def __init__(self, repo, number):
        self.repo = repo
        self.number = number

    @property
    def absolute(self):
        return os.path.join(self.repo.path.builds, self.number)

    @property
    def clone_begin(self):
        return os.path.join(self.absolute, 'clone.begin')

    @property
    def clone_end(self):
        return os.path.join(self.absolute, 'clone.end')

    @property
    def build_begin(self):
        return os.path.join(self.absolute, 'build.begin')

    @property
    def build_end(self):
        return os.path.join(self.absolute, 'build.end')

    @property
    def log(self):
        return os.path.join(self.absolute, 'build.log')

    @property
    def yaml(self):
        return os.path.join(self.absolute, 'build.yaml')

    @property
    def workspace(self):
        return os.path.join(self.absolute, 'workspace')

    @property
    def conf(self):
        return os.path.join(self.workspace, '.shipmaster.yaml')

    @property
    def docker_compose(self):
        return os.path.join(self.workspace, 'docker-compose.yaml')

    @property
    def deployments(self):
        return os.path.join(self.absolute, 'deployments')

    @property
    def last_deployment_number(self):
        return os.path.join(self.absolute, 'last_deployment_number')

    @property
    def tests(self):
        return os.path.join(self.absolute, 'tests')

    @property
    def last_test_number(self):
        return os.path.join(self.absolute, 'last_test_number')


class Build(YamlModel):
    """
        Builds in Shipmaster represent a ready to ship docker image. It is
        intended to be the authoritative immutable binary of a software release.

        A Job is an executing instance of this image usually to do things like deploy the
        image or run tests.

        For SaaS and generally for "service" based applications this setup makes sense and
        provides a very natural workflow.

        This is in contrast to most other continuous integration platforms where a "build"
        is usually just a checkout from version control and then a "job" is the combined building
        and testing of that checkout. This workflow makes a lot of sense for open source or other
        projects where the end product is intended to run and often compiled in heterogeneous environments,
        thus you need a "build matrix" where a job will be created for each element in the matrix
        building and testing the software under a specific environment.

        The way to reproduce the popular continuous integration workflow in Shipmaster would be to:

          1) Create a "base" image layer with all of the versions of interpreters or compilers and
             any other libraries needed (to the extent that multiple versions work in a single
             OS install).

          2) In the Shipmaster "app" image layer don't actually build anything but instead only do
             general pre-build preparations. Any steps that would be identical in each cell of the
             test matrix should be done here.

          3) Finally, when running the tests ("job") this is where you can do your building and testing
             as normally would be done in the standard continuous integration platforms.

        While this setup is a bit more complicated than traditional continuous integration platforms
        it allows for significant optimizations at various layers. By the time each cell in your test
        matrix is executed it should only have to do the minimum amount of work to satisfy the matrix
        constraints.

    """

    parent_class = Repository

    QUEUED = 'queued'
    CLONING = 'cloning'
    BUILDING = 'pending'
    SUCCEEDED = 'success'
    FAILED = 'failure'
    GITHUB_STATES = {
        BUILDING: "building...",
        SUCCEEDED: "container built",
        FAILED: "build failed"
    }
    SLACK_MESSAGES = GITHUB_STATES

    def __init__(self, repo, number, **kwargs):
        super().__init__(**kwargs)
        self.repo = repo  # type: Repository
        self.shipmaster = repo.shipmaster  # type: Shipmaster
        self.number = number
        self.path = BuildPath(repo, number)

    @classmethod
    def create(cls, repo, branch, **kwargs):
        build = cls(repo, repo.increment_build_number(), branch=branch, **kwargs)
        os.mkdir(build.path.absolute)
        os.mkdir(build.path.tests)
        os.mkdir(build.path.deployments)
        build.save()
        return build

    def increment_test_number(self):
        return increment_number_file(self.path.last_test_number)

    def increment_deployment_number(self):
        return increment_number_file(self.path.last_deployment_number)

    @property
    def url(self):
        return urljoin(
            settings.BASE_URL,
            reverse('build', args=[self.repo.name, self.number])
        )

    @property
    def result_display(self):
        return self.result.capitalize()

    @property
    def result(self):
        """ Optional mutable field, updated after the build completes. """
        return self.dict.get('result', '')

    @result.setter
    def result(self, result):
        self.dict['result'] = result
        self.save()

        try:
            if result in self.GITHUB_STATES:
                sha = self.commit_info['hash']
                repo = self.repo.get_github()
                repo.create_status(
                    sha, result, target_url=self.url,
                    description=self.GITHUB_STATES[result],
                    context='shipmaster/build',
                )
        except:
            pass

        try:
            if result in self.SLACK_MESSAGES:
                self.slack(self.SLACK_MESSAGES[result])
        except:
            pass

    @property
    def branch(self):
        """ Required immutable field, set when the build is created. """
        return self.dict['branch']

    @property
    def pull_request(self):
        """ Optional immutable field, set when the build is created. """
        return self.dict.get('pull_request', False)

    def get_conf(self):
        return ProjectConf.from_workspace(self.path.workspace)

    def get_project(self, **extra):
        return Project(
            self.get_conf(),
            build_num=self.number, ssh_config=self.shipmaster.path.ssh_config,
            commit_info=self.commit_info, **extra
        )

    def build(self):
        self.result = self.QUEUED
        from .tasks import build_app
        build_app.delay(self.path.absolute)
        return self

    def slack(self, message):
        conf = self.get_conf()
        if message and conf.slack.is_enabled:
            requests.post(conf.slack.api, json.dumps({'text': message}))

    @property
    def tests(self):
        for test in os.listdir(self.path.tests):
            yield Test.load(self, test)

    @property
    def sorted_tests(self):
        return sorted(self.tests, key=lambda item: int(item.number), reverse=True)

    @property
    def deployments(self):
        for deployment in os.listdir(self.path.deployments):
            yield Deployment.load(self, deployment)

    @property
    def sorted_deployments(self):
        return sorted(self.deployments, key=lambda item: int(item.number), reverse=True)

    # Timers & Progress

    @property
    def is_successful(self):
        return self.result == self.SUCCEEDED

    def succeeded(self):
        self.result = self.SUCCEEDED

    @property
    def has_failed(self):
        return self.result == self.FAILED

    def failed(self):
        self.result = self.FAILED

    @property
    def commit_info(self):
        details_cmnd = ["git", "log", '--format={"hash": "%H", "short-hash": "%h", "author": "%an", "email": "%ae"}', "-n", "1"]
        result = subprocess.run(details_cmnd, cwd=self.path.workspace, stdout=subprocess.PIPE)
        json_result = result.stdout.decode().strip()
        info = json.loads(json_result)
        subject_cmnd = ["git", "log", '--format=%s', "-n", "1"]
        result = subprocess.run(subject_cmnd, cwd=self.path.workspace, stdout=subprocess.PIPE)
        info['subject'] = result.stdout.decode().strip()
        info['branch'] = self.branch
        return info

    # Repository Cloning

    @property
    def has_cloning_started(self):
        return os.path.exists(self.path.clone_begin)

    @property
    def has_cloning_finished(self):
        return os.path.exists(self.path.clone_end)

    def cloning_started(self):
        assert not self.has_cloning_started
        record_time(self.path.clone_begin)
        self.result = self.CLONING

    def cloning_finished(self):
        assert not self.has_cloning_finished
        record_time(self.path.clone_end)

    # App Build

    @property
    def has_build_started(self):
        return os.path.exists(self.path.build_begin)

    @property
    def has_build_finished(self):
        return os.path.exists(self.path.build_end)

    @property
    def elapsed_time(self):
        assert self.has_build_finished
        return get_elapsed_time(self.path.build_begin, self.path.build_end)

    @property
    def log(self):
        assert self.has_build_finished
        with open(self.path.log, 'r') as log_file:
            return log_file.read()

    def build_started(self):
        assert not self.has_build_started
        record_time(self.path.build_begin)
        self.result = self.BUILDING

    def build_finished(self):
        assert not self.has_build_finished
        record_time(self.path.build_end)


class BaseJobPath(YamlPath):

    job_type = None

    def __init__(self, build, number):
        self.build = build
        self.number = number

    @property
    def absolute(self):
        raise NotImplemented

    @property
    def yaml(self):
        return os.path.join(self.absolute, self.job_type+'.yaml')

    @property
    def log(self):
        return os.path.join(self.absolute, self.job_type+'.log')

    @property
    def begin(self):
        return os.path.join(self.absolute, self.job_type+'.begin')

    @property
    def end(self):
        return os.path.join(self.absolute, self.job_type+'.end')


class BaseJob(YamlModel):

    QUEUED = 'queued'
    RUNNING = 'pending'
    SUCCEEDED = 'success'
    FAILED = 'failure'
    GITHUB_STATES = {}
    SLACK_MESSAGES = {}

    parent_class = Build

    def __init__(self, build, number, **kwargs):
        super().__init__(**kwargs)
        self.build = build  # type: Build
        self.repo = build.repo  # type: Repository
        self.shipmaster = build.repo.shipmaster  # type: Shipmaster
        self.number = str(number)

    def get_project(self):
        return self.build.get_project(job_num=self.number)

    @property
    def url(self):
        raise NotImplemented

    @property
    def result_display(self):
        return self.result.capitalize()

    @property
    def result(self):
        return self.dict.get('result', '')

    @result.setter
    def result(self, result):
        self.dict['result'] = result
        self.save()

        try:
            if result in self.GITHUB_STATES:
                sha = self.build.commit_info['hash']
                repo = self.repo.get_github()
                description = self.GITHUB_STATES[result].format(o=self)
                repo.create_status(
                    sha, result, target_url=self.url,
                    description=description,
                    context='shipmaster/{}'.format(self.path.job_type),
                )
        except:
            pass

        try:
            if result in self.SLACK_MESSAGES:
                message = self.SLACK_MESSAGES[result].format(o=self)
                self.build.slack(message)
        except:
            pass

    @property
    def is_successful(self):
        return self.result == self.SUCCEEDED

    def succeeded(self):
        self.result = self.SUCCEEDED

    @property
    def has_failed(self):
        return self.result == self.FAILED

    def failed(self):
        self.result = self.FAILED

    @property
    def has_started(self):
        return os.path.exists(self.path.begin)

    @property
    def has_finished(self):
        return os.path.exists(self.path.end)

    def started(self):
        assert not self.has_started
        record_time(self.path.begin)
        self.result = self.RUNNING

    def finished(self):
        assert not self.has_finished
        record_time(self.path.end)

    @property
    def elapsed_time(self):
        assert self.has_finished
        return get_elapsed_time(self.path.begin, self.path.end)

    @property
    def log(self):
        assert self.has_finished
        with open(self.path.log, 'r') as log_file:
            return log_file.read()

    @property
    def type_name(self):
        return self.__class__.__name__.lower()

    @property
    def is_deployment(self):
        return self.__class__ == Deployment

    @property
    def is_test(self):
        return self.__class__ == Test


class TestPath(BaseJobPath):
    job_type = 'test'

    @property
    def absolute(self):
        return os.path.join(self.build.path.tests, self.number)

    @property
    def reports(self):
        return os.path.join(self.absolute, 'reports')


class Test(BaseJob):

    GITHUB_STATES = {
        BaseJob.RUNNING: "running tests...",
        BaseJob.SUCCEEDED: "tests passed",
        BaseJob.FAILED: "tests failed"
    }
    SLACK_MESSAGES = GITHUB_STATES

    def __init__(self, build, number, **kwargs):
        super().__init__(build, number, **kwargs)
        self.path = TestPath(build, number)

    def get_compose(self, project):
        return get_compose(
            self.build.path.workspace,
            project_name=project.test_name,
            host='unix://var/run/docker.sock'
        )

    def is_valid_report_file(self, path):
        for file in os.listdir(self.path.reports):
            if file == path:
                return True
        return False

    def get_report_file(self, path, mode='r'):
        absolute_path = os.path.join(self.path.reports, path)
        return open(absolute_path, mode)

    @property
    def url(self):
        return urljoin(
            settings.BASE_URL,
            reverse('test', args=[self.repo.name, self.build.number, self.number])
        )

    @property
    def coverage_display(self):
        if self.coverage:
            return "{}% covered".format(self.coverage)
        return ""

    def calculate_coverage(self):
        FILE = 'status.json'
        if self.is_valid_report_file(FILE):
            from coverage.results import Numbers
            data = json.load(self.get_report_file(FILE))
            stats = sum([Numbers(*file['index']['nums']) for file in data['files'].values()])
            stats.set_precision(2)
            return stats.pc_covered_str
        return ''

    def update_coverage(self):
        self.coverage = self.calculate_coverage()
        self.save()

    @property
    def coverage(self):
        return self.dict.get('coverage', '')

    @coverage.setter
    def coverage(self, coverage):
        self.dict['coverage'] = coverage

    @classmethod
    def create(cls, build):
        job = cls(build, build.increment_test_number())
        os.mkdir(job.path.absolute)
        os.mkdir(job.path.reports)
        job.save()
        return job

    def test(self):
        self.result = self.QUEUED
        from .tasks import test_app
        test_app.delay(self.path.absolute)
        return self

    def succeeded(self):
        self.update_coverage()
        super().succeeded()


class DeploymentPath(BaseJobPath):
    job_type = 'deployment'

    @property
    def absolute(self):
        return os.path.join(self.build.path.deployments, self.number)


class Deployment(BaseJob):

    GITHUB_STATES = {
        BaseJob.RUNNING: "'{o.destination}' deploying...",
        BaseJob.SUCCEEDED: "'{o.destination}' deployment done",
        BaseJob.FAILED: "'{o.destination}' deployment failed"
    }
    SLACK_MESSAGES = GITHUB_STATES

    def __init__(self, build, number, **kwargs):
        super().__init__(build, number, **kwargs)
        self.path = DeploymentPath(build, number)

    @classmethod
    def create(cls, build, destination):
        job = cls(build, build.increment_deployment_number())
        os.mkdir(job.path.absolute)
        job.destination = destination
        job.save()
        return job

    @property
    def url(self):
        return urljoin(
            settings.BASE_URL,
            reverse('deployment', args=[self.repo.name, self.build.number, self.number])
        )

    @property
    def destination(self):
        return self.dict['destination']

    @destination.setter
    def destination(self, destination):
        self.dict['destination'] = destination

    def deploy(self):
        self.result = self.QUEUED
        from .tasks import deploy_app
        deploy_app.delay(self.path.absolute)
        return self


def record_time(path):
    with open(path, 'w') as stamp:
        stamp.write(str(time.time()))


def get_elapsed_time(start_path, end_path):
    with open(start_path, 'r') as start_file:
        start = float(start_file.read())
    with open(end_path, 'r') as end_file:
        end = float(end_file.read())
    return end - start


def increment_number_file(path):
    number = 1
    if os.path.exists(path):
        with open(path, 'r') as file:
            number = int(file.read().strip())
            number += 1
    number = str(number)
    with open(path, 'w') as file:
        file.write(number)
    return number
