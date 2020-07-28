FROM centos:8

RUN dnf update -y && dnf install rpm-build make platform-python-setuptools python3 git -y

COPY ./build-rpms.sh /
