# Gitlab Pipelines Stats

Create _.env_ file with appropriate values:

```
GITLAB_TOKEN=....................
GITLAB_PROJECT_ID=...............
```

Spin up Elasticsearch & Kibana:

```
docker-compose up
```

Ingest 1 days of pipelines' updates from Gitlab:

```
docker-compose run --rm ingest 1d
```

Wait until execution ends and go to http://localhost:5600


## Notes

Data is persisted in Docker volumes, check `docker volume` on how to prune.
