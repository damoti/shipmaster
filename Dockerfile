FROM damoti/base:latest

RUN apt-get install -y rabbitmq-server supervisor

COPY conf/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN mkdir -p /root/.ssh && \
    ssh-keyscan github.com >> /root/.ssh/known_hosts && \
    ssh-keyscan bitbucket.org >> /root/.ssh/known_hosts

COPY shipmaster /usr/lib/shipmaster/shipmaster
COPY manage.py setup.py requirements.pip /usr/lib/shipmaster/
RUN mkdir -p /var/lib/shipmaster/repos

WORKDIR /usr/lib/shipmaster
RUN pip3 install -r requirements.pip
RUN python3 manage.py migrate

EXPOSE 8000
CMD ["/usr/bin/supervisord"]
