FROM damoti/base:latest

RUN mkdir -p /root/.ssh && \
    ssh-keyscan github.com >> /root/.ssh/known_hosts && \
    ssh-keyscan bitbucket.org >> /root/.ssh/known_hosts

COPY shipmaster /usr/lib/shipmaster/shipmaster
COPY manage.py setup.py requirements.pip /usr/lib/shipmaster/

WORKDIR /usr/lib/shipmaster/shipmaster/dart
RUN pub get
RUN pub build

WORKDIR /usr/lib/shipmaster
RUN pip3 install -r requirements.pip
RUN python3 manage.py migrate
RUN python3 manage.py collectstatic --noinput

EXPOSE 8000
ENTRYPOINT ["uwsgi", "--module=shipmaster.server.wsgi", "--socket=0.0.0.0:8000", "--static-map", "/static=/usr/lib/shipmaster/static", "--attach-daemon=celery -A shipmaster.server worker -B"]
