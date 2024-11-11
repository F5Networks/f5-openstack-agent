FROM centos:7
RUN sed -i 's|^mirrorlist=|#mirrorlist=|' /etc/yum.repos.d/CentOS-Base.repo
RUN sed -i 's|^#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|' /etc/yum.repos.d/CentOS-Base.repo
RUN yum update -y && yum install rpm-build make python-setuptools git -y

COPY ./build-rpms.sh /
