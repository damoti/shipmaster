import re
import os
import sys
from io import StringIO
from dockermap.api import DockerContext, DockerFile


def write_apt_get(packages, script=None):
    out = script
    if not script: out = StringIO()
    out.write('apt-get update && apt-get install -y ')
    for package in packages:
        out.write('\\\n\t{} '.format(package))
    out.write('\n')
    if not script: return out.getvalue()


class Builder:

    @staticmethod
    def from_layer(args, layer, conf):
        if layer == 'base':
            return BaseBuilder(getattr(conf, layer))
        else:
            return LayerBuilder(args, layer, conf)


class BaseBuilder:

    def __init__(self, conf):
        self.layer_conf = conf

    @property
    def script(self):
        with DockerFile(self.layer_conf.base.from_image) as df:
            self._add_commands(df)
            df.finalize()
            return df.getvalue().decode()

    def build(self, client):
        with DockerFile(self.layer_conf.from_image) as df:
            self._add_commands(df)
            line = ''
            with DockerContext(df, finalize=True) as ctx:
                print("Step 0 : Uploading context")
                for response in client.build(tag=self.layer_conf.image_name, fileobj=ctx.fileobj, encoding=ctx.stream_encoding, custom_context=True, decode=True):
                    if 'stream' in response:
                        line = response['stream']
                        print(line, end='')
                    elif 'error' in response:
                        print(response['error'], end='')
            match = re.search(r'Successfully built ([0-9a-f]+)', line)
            if match:
                return match.group(1)
            else:
                print("Build Failed.")
                sys.exit(1)

    def _add_commands(self, df):

        if self.layer_conf.apt_get:
            df.run(write_apt_get(self.layer_conf.apt_get))

        for file in self.layer_conf.context:
            df.add_file(file, file, expandvars=True, expanduser=True, remove_final=True)

        for command in self.layer_conf.script:
            df.run(command)


class LayerBuilder:

    def __init__(self, args, name, conf):
        self.name = name
        self.conf = conf
        self.layer_conf = getattr(conf, name)
        self.args = args

        self.script_name = name+'.sh'
        self.script_dir = os.path.join('/tmp', conf.name, 'docker', 'build')
        self.script_path = os.path.join(self.script_dir, self.script_name)
        os.makedirs(self.script_dir, exist_ok=True)
        with open(self.script_path, 'w') as script:
            self.write_script(script)

        self.volumes = [
            os.getcwd()+':/app',
            '{0}:{0}'.format(self.script_dir)
        ] + self.layer_conf.volumes

        if args.use_ssh_agent:
            self.volumes.append('{0}:/tmp{0}'.format(os.path.dirname(os.environ['SSH_AUTH_SOCK'])))
            self.layer_conf.environment['SSH_AUTH_SOCK'] = '/tmp'+os.environ['SSH_AUTH_SOCK']

    def build(self, client):
        base_image_name = self.conf.base.image_name
        if self.name == 'test':
            base_image_name = self.conf.app.image_name

        result = client.create_container(
            base_image_name, command=['/bin/sh', self.script_path],
            volumes=[v.split(':')[1] for v in self.volumes],
            environment=self.layer_conf.environment,
            host_config=client.create_host_config(binds=self.volumes)
        )
        container = result.get('Id')

        client.start(container)
        for line in client.logs(container, stream=True):
            print(line.decode(), end='')

        client.stop(container)
        client.commit(container, repository=self.conf.name+'/'+self.name, tag='latest')
        client.remove_container(container)

    @property
    def script(self):
        out = StringIO()
        self.write_script(out)
        return out.getvalue()

    def write_script(self, script):

        script.write('\n# SSH Setup\n')

        if self.args.debug_ssh_agent:
            script.write('set -x\n')

        if self.args.use_ssh_agent:
            script.write('mkdir -p /root/.ssh\n')
            hide_error = '2> /dev/null'
            if self.args.debug_ssh_agent:
                hide_error = ''
            for host in self.conf.ssh.known_hosts:
                script.write('ssh-keyscan {} >> /root/.ssh/known_hosts {}\n'.format(host, hide_error))
                script.write('echo "Host *{0}\n HostName {0}" >> /root/.ssh/config\n'.format(host))
            if self.args.debug_ssh_agent:
                script.write('ssh-add -L\n')

        if self.args.debug_ssh_agent:
            for host in self.conf.ssh.known_hosts:
                script.write('ssh -T git@{}.{}\n'.format(self.conf.name, host))

        if self.layer_conf.apt_get:
            script.write('\n# Packages\n')
            write_apt_get(self.layer_conf.apt_get, script)

        script.write('\n# Build\n')
        script.write('set -x\n')
        script.write('cd /app\n')
        for command in self.layer_conf.script:
            if command:
                script.write(command+'\n')


