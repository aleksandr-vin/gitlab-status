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

Import saved objects to Kibana if you want to play with the pre-created dashboards, visualisations and indices:

```
./import-saved-objects.sh
```

Check ES for missed intervals for last 10 days:

```
docker-compose run --rm ingest --no-pipelines --no-merge-requests --check-missing-intervals 10d
```


## Notes

1. Data is persisted in Docker volumes, check `docker volume` on how to prune.

2. Run `docker-compose build` after git pulls.

## Developing

Python hacking can be easy if you build a docker image with `docker-compose build` first, then bring elastic
and kibana services up `docker-compose up` and then run this command:

```
docker run -it --env-file .env --rm -v $(pwd)/ingest/:/src --network $(basename $(pwd))_elastic $(basename $(pwd))_ingest --es-hosts elasticsearch 6h
```
