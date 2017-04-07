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

