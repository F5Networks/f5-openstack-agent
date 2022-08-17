"""
Command-line interface to the f5-openstack-agent APIs
"""
import sys

from cliff import app
from cliff.commandmanager import CommandManager
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class AgentShell(app.App):
    def __init__(self):
        super(AgentShell, self).__init__(
            description=__doc__.strip(),
            version="1.0",
            command_manager=CommandManager(namespace="f5agent.cli"),
            deferred_help=True
        )

    def initialize_app(self, argv):
        LOG.debug('initialize agent cli')


def main(argv=None):
    app = AgentShell()
    return app.run(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
