import os.path
from shipmaster.core.plugins import Plugin


class SSHPlugin(Plugin):

    @classmethod
    def contribute_to_argparse(cls, parser, commands):
        commands['run'].add_argument(
            "--debug-ssh-agent",
            help="Show some output related to ssh-agent forwarding.",
            action="store_true"
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.config = self.builder.config.plugins.get('ssh', {})

        ssh_config = None
        debug_ssh_agent = False
        if self.builder.args:
            debug_ssh_agent = getattr(self.builder.args, 'debug_ssh_agent', False),

        self.debug_ssh_agent = debug_ssh_agent
        self.ssh_agent = False

        if ssh_config:

            # ssh_config - Server side/django app, uses the ssh_config and deploy keys
            ssh_dir = os.path.dirname(ssh_config)

            self.environment = {
                "GIT_SSH_COMMAND": "ssh -F {}".format(ssh_config)
            }

            self.volumes = [
                "{0}:{0}".format(ssh_dir)
            ]

        else:

            # SSH Agent - Local use with shipmaster CLI
            self.ssh_agent = True

            self.ssh_auth_filename = os.path.basename(os.environ['SSH_AUTH_SOCK'])
            self.local_ssh_auth_dir = os.path.dirname(os.environ['SSH_AUTH_SOCK'])
            self.image_ssh_auth_dir = '/shipmaster/ssh-auth-sock'

            self.environment = {
                "SSH_AUTH_SOCK": os.path.join(
                    self.image_ssh_auth_dir,
                    self.ssh_auth_filename
                )
            }

            self.volumes = [
                "{}:{}".format(self.local_ssh_auth_dir, self.image_ssh_auth_dir)
            ]

    def add_to_build_script(self, image_builder):

        config = self.config.copy()
        config.update(image_builder.config.plugins.get('ssh', {}))

        if not config:
            return

        known_hosts = config.get('known_hosts', [])

        src = image_builder.script

        src.write('# SSH Setup')
        src.write('mkdir -p /root/.ssh')

        hide_error = '2> /dev/null'
        if self.debug_ssh_agent:
            hide_error = ''

        for host in known_hosts:
            src.write('ssh-keyscan {} >> /root/.ssh/known_hosts {}'.format(host, hide_error))
            src.write('echo "Host *{0}\n HostName {0}" >> /root/.ssh/config'.format(host))

        if self.debug_ssh_agent:
            src.write('cat /root/.ssh/config')
            src.write('cat /root/.ssh/known_hosts')
            src.write('ssh-add -L')
            for host in known_hosts:
                src.write('ssh -T git@{}.{}'.format(self.builder.config.name, host))
