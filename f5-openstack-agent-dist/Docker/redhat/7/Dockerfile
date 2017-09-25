FROM centos:7

RUN yum update -y && yum install rpm-build make python-setuptools git -y
RUN curl "https://bootstrap.pypa.io/get-pip.py" -o "get-pip.py"
RUN python get-pip.py

COPY ./build-rpms.sh /
