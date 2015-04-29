FROM ubuntu:14.04
RUN apt-get update

RUN apt-get install curl -y
RUN apt-get install build-essential -y

RUN apt-get install uuid-dev -y
RUN curl http://download.zeromq.org/zeromq-2.1.11.tar.gz -o zeromq-2.1.11.tar.gz
RUN tar xf zeromq-2.1.11.tar.gz
RUN cd zeromq-2.1.11 && ./configure && make && make install
RUN apt-get install luarocks -y
RUN luarocks install lua-zmq
