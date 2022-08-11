"""
Command-line interface to the f5-openstack-agent APIs
"""

import sys

from cliff.commandmanager import CommandManager
from oslo_log import log as logging
from osc_lib import shell
from osc_lib import clientmanager

LOG = logging.getLogger(__name__)


class AgentShell(shell.OpenStackShell):
    def __init__(self):
        super(AgentShell, self).__init__(
            description=__doc__.strip(),
            version="1.0",
            command_manager=CommandManager(namespace="f5agent.cli"),
            deferred_help=True
        )

    def initialize_app(self, argv):
        super(AgentShell, self).initialize_app(argv)

        self.cloud = self.cloud_config.get_one_cloud(
            cloud=self.options.cloud,
            argparse=self.options,
            validate=False,
        )

        self.client_manager = clientmanager.ClientManager(
            cli_options=self.cloud,
            api_version=self.api_version,
            pw_func=shell.prompt_for_password,
        )


def main(argv=None):
    app = AgentShell()
    return app.run(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
