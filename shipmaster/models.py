import os
import re
import shutil
import subprocess
from collections import OrderedDict
from .config import ShipmasterConf
from . import services
from docker import Client
from compose.cli.main import filter_containers_to_service_names
from compose.container import Container
from compose.cli.log_printer import LogPrinter, build_log_presenters
from ruamel import yaml


class ShipmasterPath:

    def __init__(self, data_path):
        self.data_path = data_path

    @property
    def repos_dir(self):
        return os.path.join(self.data_path, 'repos')

    @property
    def ssh_dir(self):
        return os.path.join(self.data_path, 'ssh')

    @property
    def keys_dir(self):
        return os.path.join(self.ssh_dir, 'keys')

    @property
    def ssh_config(self):
        return os.path.join(self.ssh_dir, 'ssh_config')


class Shipmaster:

    def __init__(self, data_path):
        self.path = ShipmasterPath(data_path)

    def run(self, command, cwd=None):
        env = {**os.environ, "GIT_SSH_COMMAND": "ssh -F {}".format(self.path.ssh_config)}
        out = subprocess.check_output(command, shell=True, cwd=cwd, env=env, stderr=subprocess.STDOUT)
        print(out)
        return out

    def update_ssh_config(self):
        with open(self.path.ssh_config, 'w') as config:
            for repo in self.repositories:
                config.write('Host '+repo.git_modified_host+'\n')
                config.write('  HostName '+repo.git_host+'\n')
                config.write('  User git\n')
                config.write('  IdentityFile '+repo.path.private_key+'\n')

    @property
    def repositories(self):
        for repo_name in os.listdir(self.path.repos_dir):
            yield Repository.load(self, repo_name)


class RepositoryPath:

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

    def exists(self):
        return os.path.exists(self.absolute)


class Repository:

    def __init__(self, shipmaster, name, git=""):
        self.shipmaster = shipmaster
        self.dict = OrderedDict()
        self.dict['name'] = name
        self.dict['git'] = git
        self._setup()

    #                 host      account     repo
    GIT_REGEX = "git@([\w\.]+):([\w\.\-]+)/([\w\.\-]+)\.git"

    def _setup(self):
        self.path = RepositoryPath(self.shipmaster, self.name)
        self.git_host = self.git_account = self.git_repo = ''

        m = re.search(Repository.GIT_REGEX, self.git)
        if m:
            self.git_host = m.group(1)
            self.git_account = m.group(2)
            self.git_repo = m.group(3)

    def increment_build_number(self):
        return increment_number_file(self.path.last_build_number)

    @property
    def name(self):  # readonly
        return self.dict['name']

    @property
    def git_modified_host(self):
        return "{}.{}".format(self.name, self.git_host)

    @property
    def git(self):
        return self.dict['git']

    @git.setter
    def git(self, git):
        self.dict['git'] = git

    @property
    def modified_git(self):
        return "git@{}:{}/{}.git".format(self.git_modified_host, self.git_account, self.git_repo)

    @classmethod
    def load(cls, shipmaster, name):
        repo = cls(shipmaster, name)
        repo._load()
        return repo

    def _load(self):
        with open(self.path.yaml, 'r') as file:
            self.dict = yaml.load(file)
            self._setup()

    def save(self):
        with open(self.path.yaml, 'w') as file:
            file.write(yaml.dump(self.dict))

    @property
    def public_key(self):
        return open(self.path.public_key, 'r').read()

    def exists(self):
        return self.path.exists()

    @classmethod
    def create(cls, shipmaster, name, git):
        repo = cls(shipmaster, name, git)

        if not os.path.exists(shipmaster.path.repos_dir):
            os.mkdir(shipmaster.path.repos_dir)

        os.mkdir(repo.path.absolute)
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

    def builds(self):
        for build in os.listdir(self.path.builds):
            yield Build.load(self, build.split('/')[-1])

    def __eq__(self, other):
        assert isinstance(other, Repository)
        return self.name == other.name


class BuildPath:

    def __init__(self, repo, number):
        self.repo = repo
        self.number = number

    @property
    def absolute(self):
        return os.path.join(self.repo.path.builds, self.number)

    @property
    def yaml(self):
        return os.path.join(self.absolute, 'info.yaml')

    @property
    def pull(self):
        return os.path.join(self.absolute, 'pull')

    @property
    def conf(self):
        return os.path.join(self.pull, '.shipmaster.yaml')

    @property
    def jobs(self):
        return os.path.join(self.absolute, 'jobs')

    @property
    def last_job_number(self):
        return os.path.join(self.absolute, 'last_job_number')


class Build:

    def __init__(self, repo, number, branch='', commit=''):
        self.repo = repo
        self.shipmaster = repo.shipmaster
        self.number = str(number)
        self.path = BuildPath(self.repo, self.number)
        self.dict = OrderedDict()
        self.dict['branch'] = branch
        self.dict['commit'] = commit

    def increment_job_number(self):
        return increment_number_file(self.path.last_job_number)

    @classmethod
    def load(cls, repo, number):
        repo = cls(repo, number)
        repo._load()
        return repo

    def _load(self):
        with open(self.path.yaml, 'r') as file:
            self.dict = yaml.load(file)

    def save(self):
        with open(self.path.yaml, 'w') as file:
            file.write(yaml.dump(self.dict))

    def jobs(self):
        for job in os.listdir(self.path.jobs):
            yield Job.load(self, job.split('/')[-1])

    def pull(self):
        self.shipmaster.run("git clone --depth=1 --branch=docker {0} {1}".format(self.repo.modified_git, self.path.pull))

    @classmethod
    def create(cls, repo, branch):
        build = cls(repo, repo.increment_build_number(), branch)
        os.mkdir(build.path.absolute)
        os.mkdir(build.path.jobs)
        build.save()
        return build


class JobPath:

    def __init__(self, build, number):
        self.build = build
        self.number = number

    @property
    def absolute(self):
        return os.path.join(self.build.path.jobs, self.number)

    @property
    def yaml(self):
        return os.path.join(self.absolute, 'info.yaml')

    @property
    def log(self):
        return os.path.join(self.absolute, 'build.log')

    @property
    def containers(self):
        return os.path.join(self.absolute, 'containers')

    @property
    def pull(self):
        return self.build.path.pull

    @property
    def workspace(self):
        return os.path.join(self.absolute, 'workspace')


class Job:

    def __init__(self, build, number):
        self.build = build
        self.repo = build.repo
        self.shipmaster = build.repo.shipmaster
        self.number = str(number)
        self.path = JobPath(self.build, self.number)
        self.dict = OrderedDict()

    @property
    def containers(self):
        with open(self.path.containers, 'r') as cid:
            return yaml.load(cid)

    @classmethod
    def load(cls, build, number):
        repo = cls(build, number)
        repo._load()
        return repo

    def _load(self):
        with open(self.path.yaml, 'r') as file:
            self.dict = yaml.load(file)

    def save(self):
        with open(self.path.yaml, 'w') as file:
            file.write(yaml.dump(self.dict))

    @classmethod
    def create(cls, build):
        job = cls(build, build.increment_job_number())
        os.mkdir(job.path.absolute)
        shutil.copytree(job.path.pull, job.path.workspace)
        job.save()
        return job

    def start(self):
        client = Client('unix://var/run/docker.sock')
        shipmaster_yaml = os.path.join(self.path.workspace, '.shipmaster.yaml')
        conf = ShipmasterConf.from_filename('test', shipmaster_yaml)
        conf.services.environment['GIT_SSH_COMMAND'] = "ssh -F {}".format(self.shipmaster.path.ssh_config)
        conf.services.volumes += ['{0}:{0}'.format(self.shipmaster.path.ssh_dir)]
        containers = services.up(conf, client, log=False)
        with open(self.path.containers, 'w') as cf:
            yaml.dump([c.id for c in containers], cf)

    def log(self):
        client = Client('unix://var/run/docker.sock')
        shipmaster_yaml = os.path.join(self.path.workspace, '.shipmaster.yaml')
        conf = ShipmasterConf.from_filename('test', shipmaster_yaml)
        project = services.get_project(conf, client)
        containers = [Container.from_id(client, cid) for cid in self.containers]
        return services.LogPrinter(
            filter_containers_to_service_names(containers, ['app']),
            build_log_presenters(['app'], False),
            project.events(service_names=['app']),
            cascade_stop=True).run()


def increment_number_file(path):
    number = 1
    if os.path.exists(path):
        with open(path, 'r') as file:
            number = int(file.read().strip())
            number += 1
    with open(path, 'w') as file:
        file.write(str(number))
    return number
