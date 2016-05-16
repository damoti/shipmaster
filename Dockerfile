FROM damoti/base:latest

RUN apt-get install -y rabbitmq-server

RUN mkdir -p /root/.ssh && \
    ssh-keyscan github.com >> /root/.ssh/known_hosts && \
    ssh-keyscan bitbucket.org >> /root/.ssh/known_hosts

COPY . /usr/lib/shipmaster
WORKDIR /usr/lib/shipmaster
RUN pip3 install -r requirements.pip
RUN python3 manage.py migrate

ENTRYPOINT ["python3", "manage.py"]
CMD ["runserver", "0.0.0.0:8000"]
