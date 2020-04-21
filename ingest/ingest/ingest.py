# -*- coding: utf-8 -*-

import os
import pprint
import sys
from datetime import datetime
from time import sleep
import gitlab
from elasticsearch import Elasticsearch

class Config:
  def __init__(self):
    self.gitlab_url = os.getenv('GITLAB_URL')
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

while not es.ping():
  print("Waiting for elasticsearch...", file=sys.stderr)
  sleep(1)

gl = gitlab.Gitlab(config.gitlab_url, private_token=config.gitlab_token)

def ingest(index, ts, id, doc):
  doc['ingested_at'] = ts
  res = es.index(index=index, id=id, body=doc)
  print(f"{res['result']} {id} in {index}", file=sys.stderr)
  return res

def ingest_job(ts, id, doc):
  return ingest('jobs', ts, id, doc)

def ingest_pipeline(ts, id, doc):
  return ingest('pipelines', ts, id, doc)

def main():
  print(f"Arguments: {sys.argv}", file=sys.stderr)
  if len(sys.argv) > 1 and sys.argv[1].strip() == "now":
    print("Ingesting now...", file=sys.stderr)
  else:
    print("To ingest gitlab pipelines stats run 'ingest now'")
    exit(0)

  print("Fetching project...", file=sys.stderr)
  project = gl.projects.get(config.project_id)
  ts_p = datetime.now()
  print("Fetching pipelines...", file=sys.stderr)
  pipelines = project.pipelines.list()
  for p in pipelines:
    p_a = p._attrs
    # print(f"{p_a}", file=sys.stderr)
    ingest_pipeline(ts_p, p_a['id'], p_a)

    ts_j = datetime.now()
    print(f"Fetching jobs for {p.id} pipeline...", file=sys.stderr)
    jobs = p.jobs.list()
    for j in jobs:
      j_a = j._attrs
      # print(f"{j_a}", file=sys.stderr)
      ingest_job(ts_j, j_a['id'], j_a)
