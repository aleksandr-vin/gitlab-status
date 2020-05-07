# -*- coding: utf-8 -*-

import os
import pprint
import sys
from datetime import datetime, timedelta, timezone
import dateutil.parser
from time import sleep
import re
import argparse
import gitlab
from elasticsearch import Elasticsearch
from contextlib import contextmanager

pp = pprint.PrettyPrinter(indent=2)
pe = pprint.PrettyPrinter(indent=2, stream=sys.stderr)

def ingest(index, ts, id, doc):
  doc['ingested_at'] = ts.isoformat()
  global args
  if args.dump_es_docs:
    print(f"as {doc}", file=sys.stderr, end =" ")
  if not args.fetch_only:
    res = es.index(index=index, id=id, body=doc)
  else:
    res = { 'result': 'skipped', '_id': id }
  print(f"{res['result']} as doc {res['_id']} in '{index}' index", file=sys.stderr)
  return res

def register_ingestion(ts, id, doc):
  return ingest('ingestions', ts, id, doc)

def ingest_job(ts, id, doc):
  return ingest('jobs', ts, id, doc)

def ingest_pipeline(ts, id, doc):
  return ingest('pipelines', ts, id, doc)

def ingest_merge_request(ts, id, doc):
  return ingest('merge_requests', ts, id, doc)

def ingest_merge_request_version(ts, id, doc):
  return ingest('merge_request_versions', ts, id, doc)

def process_jobs(jobs):
  ts = datetime.now(timezone.utc)
  for j in jobs:
    print(f"Job {j.id} created at {j.created_at} finished at {j.finished_at}", file=sys.stderr, end =" ")
    ingest_job(ts, j.id, j._attrs)

def process_pipelines(pipelines, start_from):
  ts = datetime.now(timezone.utc)
  for p in pipelines:
    updated = dateutil.parser.parse(p.updated_at)
    if updated < start_from:
      break
    print(f"Pipeline {p.id} created at {p.created_at} updated at {p.updated_at}", file=sys.stderr, end =" ")
    ingest_pipeline(ts, p.id, p._attrs)
    print(f"Fetching jobs for {p.id} pipeline...", file=sys.stderr)
    process_jobs(p.jobs.list(as_list=False))

def process_merge_request_versions(versions):
  ts = datetime.now(timezone.utc)
  for v in versions:
    print(f"Merge Request Version {v.id} created at {v.created_at}", file=sys.stderr, end =" ")
    ingest_merge_request_version(ts, v.id, v._attrs)

def process_merge_requests(merge_requests, start_from):
  ts = datetime.now(timezone.utc)
  for mr in merge_requests:
    updated = dateutil.parser.parse(mr.updated_at)
    if updated < start_from:
      break
    print(f"Merge Request {mr.id} created at {mr.created_at} updated at {mr.updated_at}", file=sys.stderr, end =" ")
    ingest_merge_request(ts, mr.id, mr._attrs)
    print(f"Fetching versions for {mr.id} merge request...", file=sys.stderr)
    process_merge_request_versions(mr.diffs.list(as_list=False))


@contextmanager
def ingestion(resource_name, delta, start_from, end_till):
  meta={
    'started_at': datetime.now(timezone.utc),
    'resource': resource_name,
    'delta': delta.total_seconds(),
    'start_from': start_from.isoformat(),
    'end_till': end_till.isoformat()
  }
  yield meta
  ts = meta['finished_at'] = datetime.now(timezone.utc)
  register_ingestion(ts, None, meta)

def check_missing_intervals(delta, start_from, end_till):
  for resource in ["pipelines"]:

    res = es.search(index="ingestions", size=1, body={
      "query": {
        "bool": {
          "must": {
            "match": { "resource.keyword": resource }
          },
          "filter": [
            {
              "range": {
                "start_from": {
                  "lt" : start_from.isoformat()
                }
              }
            },
            {
              "range": {
                "end_till": {
                  "gte" : start_from.isoformat()
                }
              }
            }
          ]
        }
      },
      "sort": [{"end_till": "desc"}]
    })
    global args
    if args.verbose:
      print("Got %d hits to start with:" % res['hits']['total']['value'], file=sys.stderr)

    intervals=[]
    for hit in res['hits']['hits']:
      if args.verbose:
        print("%(ingested_at)s > %(start_from)s - %(end_till)s (%(delta)d)" % hit["_source"], file=sys.stderr)
      s = hit["_source"]
      s_from = dateutil.parser.parse(s["start_from"])
      s_to = dateutil.parser.parse(s["end_till"])
      intervals.append({'from': s_from, 'to': s_to, 'source': s})

    intervals = intervals[:1] # keeping the first -- the most valuable by the end_till inclusion

    res = es.search(index="ingestions", size=10000, body={
      "query": {
        "bool": {
          "must": {
            "match": { "resource.keyword": resource }
          },
          "filter": [
            {"range": {
              "start_from": {
                "gte" : start_from.isoformat(),
                "lt" :  end_till.isoformat()
              }
            }}
          ]
        }
      },
      "sort": [{"start_from": "asc"}]
    })
    if args.verbose:
      print("Got %d hits:" % res['hits']['total']['value'], file=sys.stderr)

    missing = []
    if len(intervals) == 0:
      if len(res['hits']['hits']) == 0:
        missing.append({'from': start_from, 'to': end_till})
      else:
        missing.append({'from': start_from, 'to': dateutil.parser.parse(res['hits']['hits'][0]["_source"]["start_from"])})
    
    for hit in res['hits']['hits']:
      if args.verbose:
        print("%(ingested_at)s > %(start_from)s - %(end_till)s (%(delta)d)" % hit["_source"], file=sys.stderr)
      s = hit["_source"]
      s_from = dateutil.parser.parse(s["start_from"])
      s_to = dateutil.parser.parse(s["end_till"])
      if len(intervals) == 0:
        intervals.append({'from': s_from, 'to': s_to, 'source': s})
      elif s_from > intervals[-1]["to"]:
        missing.append({'from': intervals[-1]["to"], 'to':  s_from})
        intervals.append({'from': s_from, 'to': s_to, 'source': s})
      elif intervals[-1]["to"] < s_to:
        intervals.append({'from': s_from, 'to': s_to, 'source': s})

    if len(intervals) > 0 and intervals[-1]["to"] < end_till:
      missing.append({'from': intervals[-1]["to"], 'to':  end_till})

    if len(missing) > 0:
      print("Missing intervals:", file=sys.stderr)
      for i in missing:
        print(f"{i['from']} - {i['to']} ({i['to'] - i['from']})", file=sys.stderr)
    else:
      print("No missing intervals", file=sys.stderr)

    if len(intervals) > 0:
      print("Complete intervals:", file=sys.stderr)
      for i in intervals:
        print(f"{i['from']} - {i['to']} ({i['to'] - i['from']})", file=sys.stderr)
    else:
      print("No complete intervals", file=sys.stderr)

    return len(missing) == 0

##
## credits: https://stackoverflow.com/a/4628148/468942
##
parse_time_regex = re.compile(r'^((?P<days>\d+?)d)?\s*((?P<hours>\d+?)h)?\s*((?P<minutes>\d+?)m)?$')

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
  parser = argparse.ArgumentParser(description='Ingest stats from gitlab project.',
                                   epilog="To ingest gitlab stats for pipelines and merge requests updated up to 2 days old from now, run 'ingest 2d'")
  parser.add_argument('delta', metavar='delta', type=str,
                      help='delta in [NNd][NNh][NNm] format, to define the max age of updates to fetch')
  parser.add_argument('--verbose', action='store_true', help="verbose output")
  parser.add_argument('--fetch-only', action='store_true', help="do not ingest in Elasticsearch")
  parser.add_argument('--no-pipelines', action='store_true', help="do not fetch pipelines")
  parser.add_argument('--no-merge-requests', action='store_true', help="do not fetch merge requests")
  parser.add_argument('--dump-es-docs', action='store_true', help="dump documets before sending to Elasticsearch")
  parser.add_argument('--dump-config', action='store_true', help="dump config before starting")
  parser.add_argument('--gitlab-url', default=os.getenv('GITLAB_URL', 'https://gitlab.com'),
                      help="gitlab site url")
  parser.add_argument('--gitlab-token', default=os.getenv('GITLAB_TOKEN'),
                      help="gitlab private token")
  parser.add_argument('--gitlab-project-id', default=os.getenv('GITLAB_PROJECT_ID'),
                      help="gitlab project id")
  parser.add_argument('--es-hosts', default=os.getenv('ES_HOSTS', 'localhost'),
                      help="Elasticsearch hosts")
  parser.add_argument('--check-missing-intervals', action='store_true', help="check for non-ingested intervals")

  global args
  args = parser.parse_args()

  gitlab_token = args.gitlab_token
  args.gitlab_token = f"{gitlab_token[:2]}...{gitlab_token[-2:]}"
  if args.dump_config:
    print(f"Config: {vars(args)}", file=sys.stderr)

  delta = parse_time_delta(args.delta)
  if not delta:
    print("Wrong delta format.", file=sys.stderr)
    exit(1)
  else:
    print(f"Ingesting updates up to {delta} old...", file=sys.stderr)

  if not args.fetch_only:
    es_hosts = [x.strip() for x in args.es_hosts.split()]
    global es
    es = Elasticsearch(es_hosts)
    while not es.ping():
      print("Waiting for elasticsearch...", file=sys.stderr)
      sleep(1)

  print(f"Fetching project {args.gitlab_project_id} ...", file=sys.stderr)
  gl = gitlab.Gitlab(args.gitlab_url, private_token=gitlab_token)
  project = gl.projects.get(args.gitlab_project_id)

  ts = datetime.now(timezone.utc)
  start_from = ts - delta
  end_till = ts
  print(f"Ingestion interval: {start_from.isoformat()} - {end_till.isoformat()}", file=sys.stderr)

  if not args.no_pipelines:
    with ingestion('pipelines', delta, start_from, end_till) as i:
      print("Fetching pipelines...", file=sys.stderr)
      pipelines = project.pipelines.list(as_list=False, order_by='updated_at', sort='desc')
      process_pipelines(pipelines, start_from)

  if not args.no_merge_requests:
    with ingestion('mergerequests', delta, start_from, end_till) as i:
      print("Fetching merge requests...", file=sys.stderr)
      merge_requests = project.mergerequests.list(as_list=False, order_by='updated_at', sort='desc')
      process_merge_requests(merge_requests, start_from)

  if args.check_missing_intervals:
    print("Checking for missing intervals...", file=sys.stderr)
    if check_missing_intervals(delta, start_from, end_till):
      exit(1)
    else:
      exit(0)
