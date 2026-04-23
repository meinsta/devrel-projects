---
name: qdrant-monitoring
description: "Qdrant provides monitoring and observability tools available for both self-hosted and cloud deployments. This document provides an overview of monitoring options and best practices for monitoring Qdrant performance and health."
allowed-tools:
  - Read
  - Grep
  - Glob
---



# Qdrant Monitoring

Qdrant monitoring allows to track the performance and health of your Qdrant deployment, and to identify and troubleshoot issues.
Monitoring is available for both self-hosted and cloud deployments of Qdrant, though Cloud deployment provides more advanced monitoring features out of the box.


## Prometheus Metrics

Qdrant exposes internal metrics in Prometheus format, which can be scraped by Prometheus server from `/metrics` endpoint.
In addition to Qdrant instance-level metrics, Qdrant cluster also provides cluster-level metrics, available on `/sys_metrics` endpoint.

Example of self-hosted monitoring of Qdrant Cloud cluster can be found in [repository](https://github.com/qdrant/prometheus-monitoring)


## Liveness and Readiness Probes

<!-- ToDo: Improve docs about `/readyz` -->

Read about liveness and readiness probes [here](https://qdrant.tech/documentation/guides/monitoring/#kubernetes-health-endpoints)

## Optimization process observability

<!-- ToDo -->

## Memory usage observability

<!-- ToDo -->

## Slow requests observability

<!-- ToDo -->

