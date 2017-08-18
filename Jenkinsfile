#!/usr/bin/env groovy

pipeline {
    agent {
        docker {
            label "docker"
            registryUrl "https://docker-registry.pdbld.f5net.com"
            image "bdo/jenkins-worker-ubuntu-16.04:master"
            args "-v /etc/localtime:/etc/localtime:ro" \
                + " -v /srv/mesos/trtl/results:/home/jenkins/results" \
                + " -v /srv/nfs:/testlab" \
                + " --env-file /srv/kubernetes/infra/jenkins-worker/config/openstack-test.env"
        }
    }
    options {
        ansiColor('xterm')
        timestamps()
        timeout(time: 2, unit: "HOURS")
    }
    stages {
        stage("systest") {
            steps {
                sh '''
                    # - initialize env vars
                    . systest/scripts/init_env.sh

                    # - record start of build
                    systest/scripts/record_build_start.sh

                    # - setup ssh agent
                    eval $(ssh-agent -s)
                    ssh-add

                    # - run tests
                    make -C systest $JOB_BASE_NAME

                    # - record results only if it's not a smoke test
                    if [ -n "${JOB_BASE_NAME##*smoke*}" ]; then
                        systest/scripts/record_results.sh
                    fi
                '''
            }
        }
    }
    post {
        always {
            // cleanup workspace
            dir("${env.WORKSPACE}") { deleteDir() }
        }
    }
}
