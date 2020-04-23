#!/usr/bin/env bash
#
# Script for cron job
#
# Crontab schedule line example:
## at 15 min of 2am, 4am, 6am, 8am..., everyday
# 15 0-23/2 * * *       $HOME/bin/ingest-gitlab-stats.sh ~/Developer/gitlab-pipeline-stats 1d 2>&1
## at 45 min of 10, 14 and 16 hour of Monday
# 45 10,14,16 * * 1     $HOME/bin/ingest-gitlab-stats.sh ~/Developer/gitlab-pipeline-stats 3d 2>&1
#

export PATH="/usr/local/bin:$PATH"

DOCKER_COMPOSE="/usr/local/bin/docker-compose --no-ansi"

set -e

cd "${1:-.}"

# Save initial ES running status
set +e
${DOCKER_COMPOSE} ps elasticsearch | grep elasticsearch | grep ' Up '
es_status=$?
set -e

# Ingest Gitlab pipelines status
${DOCKER_COMPOSE} run --rm ingest --dump-config ${2:-6h}

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
