# -*- coding: utf-8 -*-

import os
import pprint
import sys
from datetime import datetime, timedelta, timezone
import dateutil.parser
from time import sleep
import re
import gitlab
from elasticsearch import Elasticsearch

class Config:
  def __init__(self):
    self.gitlab_url = os.getenv('GITLAB_URL', 'https://gitlab.com')
    self.gitlab_token = os.getenv('GITLAB_TOKEN')
    self.project_id = os.getenv('GITLAB_PROJECT_ID')
    self.es_hosts = [x.strip() for x in os.getenv('ES_HOSTS').split()]

  def __str__(self):
    return "\n".join([
      f"GITLAB_URL={self.gitlab_url}",
      f"GITLAB_TOKEN={self.gitlab_token[:2]}.....{self.gitlab_token[-2:]}",
      f"GITLAB_PROJECT_ID={self.project_id}",
      f"ES_HOSTS={self.es_hosts}",
    ])
    
config = Config()
print(config, file=sys.stderr)

pp = pprint.PrettyPrinter(indent=2)
pe = pprint.PrettyPrinter(indent=2, stream=sys.stderr)

es = Elasticsearch(config.es_hosts)

gl = gitlab.Gitlab(config.gitlab_url, private_token=config.gitlab_token)

def ingest(index, ts, id, doc):
  doc['ingested_at'] = ts
  res = es.index(index=index, id=id, body=doc)
  print(f"{res['result']} as doc {id} in '{index}' index", file=sys.stderr)
  return res

def ingest_job(ts, id, doc):
  return ingest('jobs', ts, id, doc)

def ingest_pipeline(ts, id, doc):
  return ingest('pipelines', ts, id, doc)

def process_jobs(jobs):
  ts = datetime.now(timezone.utc)
  for j in jobs:
    print(f"Job {j.id} created at {j.created_at} finished at {j.finished_at}", file=sys.stderr, end =" ")
    j_a = j._attrs
    # print(f"{j_a}", file=sys.stderr)
    ingest_job(ts, j_a['id'], j_a)

def process_pipelines(pipelines, time_delta):
  ts = datetime.now(timezone.utc)
  start = ts - time_delta
  for p in pipelines:
    updated = dateutil.parser.parse(p.updated_at)
    if updated < start:
      break
    print(f"Pipeline {p.id} created at {p.created_at} updated at {p.updated_at}", file=sys.stderr, end =" ")
    p_a = p._attrs
    # print(f"{p_a}", file=sys.stderr)
    ingest_pipeline(ts, p_a['id'], p_a)
    print(f"Fetching jobs for {p.id} pipeline...", file=sys.stderr)
    process_jobs(p.jobs.list(as_list=False))

##
## credits: https://stackoverflow.com/a/4628148/468942
##
parse_time_regex = re.compile(r'((?P<days>\d+?)d)?\s*((?P<hours>\d+?)h)?\s*((?P<minutes>\d+?)m)?')

def parse_time_delta(time_str):
  parts = parse_time_regex.match(time_str)
  if not parts:
    return
  parts = parts.groupdict()
  time_params = {}
  for (name, param) in parts.items():
    if param:
      time_params[name] = int(param)
  return timedelta(**time_params)

def main():
  delta = timedelta(days=1)
  print(f"Arguments: {sys.argv}", file=sys.stderr)
  if len(sys.argv) > 1:
    delta = parse_time_delta(sys.argv[1].strip())
    if not delta:
      print("Provide time delta in format 1d2h30m")
      exit(1)
  else:
    print("To ingest gitlab stats for pipelines updated up to 2 days old from now, run 'ingest 2d'")
    exit(0)

  while not es.ping():
    print("Waiting for elasticsearch...", file=sys.stderr)
    sleep(1)

  print(f"Ingesting updates up to {delta} old...", file=sys.stderr)

  print("Fetching project...", file=sys.stderr)
  project = gl.projects.get(config.project_id)
  print("Fetching pipelines...", file=sys.stderr)
  pipelines = project.pipelines.list(as_list=False, order_by='updated_at', sort='desc')
  process_pipelines(pipelines, delta)
