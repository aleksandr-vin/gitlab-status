#!/usr/bin/env bash
#
# Script for cron job
#
# Crontab schedule line example:
# 10 * * * *       $PATH/ingest-gitlab-stats.sh ~/Developer/gitlab-pipeline-stats 2>&1
#

export PATH="/usr/local/bin:$PATH"

DOCKER_COMPOSE="/usr/local/bin/docker-compose --no-ansi"

set -e
set -x

cd "$1"

# Save initial ES running status
set +e
${DOCKER_COMPOSE} ps elasticsearch | grep elasticsearch | grep ' Up '
es_status=$?
set -e

# Ingest Gitlab pipelines status
${DOCKER_COMPOSE} run --rm ingest now

# Stop ES if it was not running and Kibana is not running now
set +e
${DOCKER_COMPOSE} ps kibana | grep kibana | grep ' Up '
kibana_status=$?
set -e

if [ $es_status == 0 ] || [ $kibana_status == 0 ]
then
    echo "ES was running before or Kibana is running now, leaving ES running"
else
    echo "ES was not running before and Kibana is not running now, stopping ES..."
    ${DOCKER_COMPOSE} stop
fi
