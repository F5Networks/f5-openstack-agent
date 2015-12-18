### Tenant Scheduler
The F5 LBaaS Plug-in uses a scheduler which, by default, associates all LBaaS pools on the same cluster with the same tenant. This association is maintained in the OpenStack database. To view the associations: 
    
1. Run `neutron agent-list`. 
2. Run `neutron lb-pool-list-on-agent <agent-id>` for each LBaaS agent.

If you add more agent-cluster groups, the LBaaS plug-in will automatically identify which agent it should talk to in order to service a given tenant. 

**NOTE:** If you delete all pools for a tenant, the record of how to map the tenant pool to an agent is also deleted. In such cases, the BIG-IP may choose a new agent for that tenant.