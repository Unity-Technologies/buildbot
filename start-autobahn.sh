#!/bin/bash
virtualenv /katana-venv && \
cd /katana/www && \
/katana-venv/bin/python setup.py install && \
cd /katana/master && \
/katana-venv/bin/python setup.py develop && \
#/katana-venv/bin/pip install 'autobahn==0.18.2' 'autobahn[twisted]==0.18.2' && \
cd /katana/autobahn && \
/katana-venv/bin/python autobahnServer.py debug
