FROM ubuntu:16.04

RUN apt-get -y update && \
    apt-get -y install libmysqlclient-dev python-virtualenv git gcc python-dev mercurial mysql-client python-pip && \
    apt-get -y build-dep python-ldap

RUN git clone https://github.com/mcuadros/pynats /pynats && \
    cd /pynats && \
    git checkout v0.1.0 && \
    python setup.py install

COPY /master/requirements-dev.txt requirements
RUN pip install -r requirements

EXPOSE 8001
EXPOSE 8010

ADD start-autobahn.sh /start-autobahn.sh
RUN chmod +x /start-autobahn.sh

VOLUME /katana
VOLUME /buildmaster
VOLUME /buildmaster_configuration

ENV PYTHONPATH /katana/master:/buildmaster_configuration:/buildmaster/src

CMD /katana/master/bin/buildbot create-master /buildmaster && \
    /katana/master/bin/buildbot upgrade-master /buildmaster && \
    rm -rf /buildmaster/templates && \
    ln -s /katana/www/templates /buildmaster/templates && \
    /katana/master/bin/buildbot start --nodaemon /buildmaster
