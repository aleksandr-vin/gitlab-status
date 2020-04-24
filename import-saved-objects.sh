#!/usr/bin/env bash

set -e

kibana=$(docker-compose ps kibana | grep -o -e '0.0.0.0:[^-]*')

curl "http://${kibana}/api/saved_objects/_import?overwrite=true" \
     -v \
     -XPOST \
     -H 'kbn-version: 7.6.2' \
     -F 'file=@./export.ndjson'
