import os
import io
import logging
from fnmatch import fnmatch
from tarfile import TarFile, TarInfo
from tempfile import NamedTemporaryFile
from humanfriendly import format_size

SCRIPT_PATH = '/shipmaster/scripts/'
APP_PATH = '/app'


class Script:
    def __init__(self, name, set_dash_x=True):
        self.path = os.path.join(SCRIPT_PATH, name)
        self.src = io.BytesIO()
        self._closed = False
        self.info = None
        if set_dash_x:
            self.write('set -x')
            self.write()

    def close(self):
        assert not self._closed
        self.info = TarInfo(self.path)
        self.info.mode = 0o755
        self.info.size = self.src.tell()
        self.src.seek(0, 0)
        self._closed = True

    def open(self):
        assert self._closed
        self.info = None
        self.src.seek(0, 2)
        self._closed = False

    @property
    def tar(self):
        if not self._closed:
            self.close()
        return self.info, self.src

    @property
    def source(self):
        if not self._closed:
            self.close()
        return self.src.read().decode()

    def write(self, s='', newline=True):
        assert not self._closed
        self.src.write(s.encode('utf-8'))
        if newline:
            self.src.write(b'\n')

    def write_all(self, commands, apt_get, ssh_known_hosts, project_name, debug_ssh_agent):
        self.write_ssh(ssh_known_hosts, project_name, debug_ssh_agent)
        self.write()
        self.write_apt_get(apt_get)
        self.write()
        self.write_build(commands)

    def write_ssh(self, known_hosts, project_name, debug_ssh_agent=False):
        self.write('# SSH Setup')

        self.write('mkdir -p /root/.ssh')

        hide_error = '2> /dev/null'
        if debug_ssh_agent:
            hide_error = ''

        for host in known_hosts:
            self.write('ssh-keyscan {} >> /root/.ssh/known_hosts {}'.format(host, hide_error))
            self.write('echo "Host *{0}\n HostName {0}" >> /root/.ssh/config'.format(host))

        debug_ssh_agent and self.write_debug_ssh(project_name, known_hosts)

    def write_debug_ssh(self, project_name, known_hosts):
        self.write('cat /root/.ssh/config')
        self.write('cat /root/.ssh/known_hosts')
        self.write('ssh-add -L')
        for host in known_hosts:
            self.write('ssh -T git@{}.{}'.format(project_name, host))

    def write_apt_get(self, apt_get):
        self.write('# Packages')
        if apt_get:
            self.write('apt-get update && apt-get install -y ', newline=False)
            for package in apt_get:
                self.write('\\\n\t{} '.format(package), newline=False)
            self.write()

    def write_build(self, commands):
        self.write('# Build')
        self.write('cd /app')
        for command in commands:
            self.write(command)


class Archive:

    def __init__(self, workspace):
        self.workspace = workspace
        self.log = logging.getLogger('archive')
        self.base = os.path.abspath(os.path.dirname(__file__))
        self.archive_file = NamedTemporaryFile('wb+')
        self.archive = TarFile.open(mode='w', fileobj=self.archive_file)
        self._closed = False

        self.exclude = []
        exclude_patterns = os.path.join(workspace, '.dockerignore')
        if os.path.exists(exclude_patterns):
            with open(exclude_patterns, 'r') as patterns:
                for pattern in patterns.readlines():
                    if pattern:
                        self.exclude.append(pattern.strip())

    def add_script(self, script: Script):
        assert not self._closed
        self.archive.addfile(*script.tar)

    def add_bundled_file(self, path):
        assert not self._closed
        input_path = os.path.join(self.base, path)
        output_path = os.path.join(SCRIPT_PATH, path)
        self.archive.add(input_path, output_path)

    def _filter_git(self, info):
        abspath = os.path.join('/', info.name)
        relative = os.path.relpath(abspath, APP_PATH)
        for pattern in self.exclude:
            if fnmatch(relative, pattern):
                self.log.debug('excluding '+relative)
                return None
        return info

    def add_project_file(self, path):
        assert not self._closed
        input_path = os.path.normpath(os.path.join(self.workspace, path))
        output_path = os.path.normpath(os.path.join(APP_PATH, path))
        self.archive.add(input_path, output_path, filter=self._filter_git)

    def close(self):
        assert not self._closed
        self.archive.close()
        self.archive_file.seek(0)
        self._closed = True
        size = os.path.getsize(self.archive_file.name)
        self.log.info('Archive: {}'.format(format_size(size)))

    def getfile(self):
        if not self._closed:
            self.close()
        return self.archive_file
