# rh-analyze-prototype

Proof of Concept for a cloud-native multi-agent AI platform on OpenShift.

## Overview

This repository demonstrates a production-ready architecture for deploying and orchestrating multi-agent AI systems using declarative configuration and enterprise-grade infrastructure.

The POC implements a hierarchical agent system that:
- Decomposes complex queries using an orchestrator agent
- Delegates to specialized agents (Jira, usage metrics, financial data)
- Aggregates results and generates outputs (graphs, reports)
- Provides complete observability of the entire execution tree

## Key Technologies

- **cagent** - Declarative agent definition (YAML-based)
- **Llama Stack** - Unified AI execution layer (inference, RAG, tools)
- **vLLM** - High-performance LLM inference engine
- **kagent** - Kubernetes-native agent deployment
- **Kagenti** - Production infrastructure (SPIRE, Keycloak, MCP Gateway)
- **MLflow** - End-to-end observability and tracing

## Cluster Access Setup

### Configuration

Create a `.env.local` file with your OpenShift cluster credentials:

```bash
# OpenShift Cluster Configuration
OCP_SERVER=https://api.your-cluster.openshiftapps.com:443
OCP_CONSOLE=https://console-openshift-console.apps.your-cluster.openshiftapps.com/
OCP_AUTH_TYPE=htpasswd-cluster-admin
OCP_USERNAME=your-username
OCP_PASSWORD=your-password

# GitHub MCP Token (for agent MCP integration)
GITHUB_MCP_TOKEN=your-github-token
```

**Note:** The `.env.local` file is git-ignored to prevent credential exposure.
```

### Usage

```bash
# Log into the cluster
make login
```

## Deployment

Deploy the complete multi-agent platform (vLLM + Llama Stack + Agent):

```bash
# Deploy to a namespace
make deploy NAMESPACE=my-namespace

# Check status
make status NAMESPACE=my-namespace
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment options and [cagent-helloworld/README.md](cagent-helloworld/README.md) for testing the agent.

## Documentation

- [Deployment Guide](DEPLOYMENT.md) - Step-by-step deployment instructions
- [Architecture Proposal](docs/architecture-proposal.md) - Complete design document
- [Technology Analysis](docs/) - Individual component documentation

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details.

## Contact

For questions or contributions, please open an issue in this repository.

