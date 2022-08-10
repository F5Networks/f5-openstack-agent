"""
Command-line interface to the f5-openstack-agent APIs
"""

import sys

from cliff.app import App
from cliff.commandmanager import CommandManager
from oslo_log import log as logging
from osc_lib import shell

LOG = logging.getLogger(__name__)


class AgentShell(App):

    def __init__(self):
        super(AgentShell, self).__init__(
            description=__doc__.strip(),
            version="1.0",
            command_manager=CommandManager(namespace="f5agent.cli"),
            deferred_help=True
        )

    def initialize_app(self, argv):
        # todo: init commandmanager
        LOG.info("initialize app")

    def prepare_to_run_command(self, cmd):
        LOG.debug("prepare_to_run_command %s", cmd.__class__.__name__)

    def clean_up(self, cmd, result, err):
        LOG.debug("clean_up %s", cmd.__class__.__name__)
        if err:
            LOG.error("got an error: %s", err)

# class AgentShell(shell.OpenStackShell):
#     def __init__(self):
#         super(AgentShell, self).__init__(
#             description=__doc__.strip(),
#             version="1.0",
#             command_manager=CommandManager(namespace="f5agent.cli"),
#             deferred_help=True
#         )


def main(argv=None):
    app = AgentShell()
    return app.run(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
