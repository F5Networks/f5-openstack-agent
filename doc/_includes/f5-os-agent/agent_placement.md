The F5 LBaaS Agent can run on any host that has the Neutron python libraries installed. We recommend using a Neutron Controller or Gateway node, as they contain the appropriate libraries by default. You can also run the agent on a dedicated node. 

We also recommend running multiple F5 LBaaS agents for the same environment simultaneously on different hosts. Doing so provides some redundancy in LBaaS provisioning for that environment. 

**Note:** If you choose to deploy multiple agents for the same environment, they *must* run on different hosts. 

You can run multiple F5 LBaaS agents simultaneously on the same host, but they must be orchestrating different environments \(in other words, different TMOS clusters with unique environment prefixes\).  