#!/usr/bin/env bash
#
# Script for cron job
#
# Crontab schedule line example:
# 10 * * * *       $PATH/ingest-gitlab-stats.sh 2>&1
#

set -e
set -x

cd ~/Developer/gitlab-pipeline-stats

# Save initial ES running status
set +e
/usr/local/bin/docker-compose ps elasticsearch | grep elasticsearch | grep ' Up '
es_status=$?
set -e

# Ingest Gitlab pipelines status
/usr/local/bin/docker-compose run --rm ingest now

# Stop ES if it was not running and Kibana is not running now
set +e
/usr/local/bin/docker-compose ps kibana | grep kibana | grep ' Up '
kibana_status=$?
set -e

if [ $es_status == 0 ] || [ $kibana_status == 0 ]
then
    echo "ES was running before or Kibana is running now, leaving ES running"
else
    echo "ES was not running before and Kibana is not running now, stopping ES..."
    /usr/local/bin/docker-compose stop
fi
