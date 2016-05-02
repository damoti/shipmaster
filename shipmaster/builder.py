import os
import shutil


class LayerBuilder:

    def __init__(self, name, conf, debug_ssh_agent=False):
        self.name = name
        self.conf = conf
        self.layer = getattr(conf, name)
        self.debug_ssh_agent = debug_ssh_agent

    def build(self, client):

        os.makedirs(self.conf.scripts_dir, exist_ok=True)
        with open(self.conf.script_path, 'w') as script:
            self.write_script(script)

        shipmaster_src = os.path.abspath(os.path.dirname(__file__))
        wait_for_it = os.path.join(shipmaster_src, 'wait-for-it', 'wait-for-it.sh')
        shutil.copy(wait_for_it, self.conf.scripts_dir)

        result = client.create_container(
            self.layer.from_image, command=['/bin/sh', self.conf.script_path],
            volumes=[v.split(':')[1] for v in self.layer.volumes],
            environment=self.layer.environment,
            host_config=client.create_host_config(binds=self.layer.volumes)
        )
        container = result.get('Id')

        client.start(container)
        for line in client.logs(container, stream=True):
            print(line.decode(), end='')

        client.stop(container)
        client.commit(container, repository=self.layer.repository, tag=self.layer.tag)
        client.remove_container(container)

    def write_script(self, script):

        script.write('# FROM {}\n'.format(self.layer.from_image))

        script.write('\n# SSH Setup\n')

        if self.debug_ssh_agent:
            script.write('set -x\n')

        script.write('mkdir -p /root/.ssh\n')
        hide_error = '2> /dev/null'
        if self.debug_ssh_agent:
            hide_error = ''
        for host in self.conf.ssh.known_hosts:
            script.write('ssh-keyscan {} >> /root/.ssh/known_hosts {}\n'.format(host, hide_error))
            script.write('echo "Host *{0}\n HostName {0}" >> /root/.ssh/config\n'.format(host))
        if self.debug_ssh_agent:
            script.write('ssh-add -L\n')

        if self.debug_ssh_agent:
            for host in self.conf.ssh.known_hosts:
                script.write('ssh -T git@{}.{}\n'.format(self.conf.name, host))

        script.write('\n# Packages\n')
        if self.layer.apt_get:
            script.write('apt-get update && apt-get install -y ')
            for package in self.layer.apt_get:
                script.write('\\\n\t{} '.format(package))
            script.write('\n')

        script.write('\n# Build\n')
        script.write('set -x\n')
        script.write('cd /app\n')
        for command in self.layer.script:
            if command:
                script.write(command+'\n')
