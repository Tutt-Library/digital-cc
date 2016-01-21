"""Module wraps Elastic Search functionality"""

__author__ = "Jeremy Nelson"

import click
import os
import requests
import sys

from flask import abort
from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, Q
import xml.etree.ElementTree as etree

etree.register_namespace("mods", "http://www.loc.gov/mods/v3")

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
REPO_SEARCH = None
AGGS_DSL = {
    "size": 0,
    "aggs": {
        "Format": {
             "terms": {
                 "field": "typeOfResource"
            }
        },
        "Geographic": {
            "terms": {
                "field": "geographic"
            }
        },
        "Genres": {
            "terms": {
                "field": "genre"
            }
        },
        "Languages": {
	        "terms": {
                "field": "language"
			}
        },
        "Publication Year": {
            "terms": {
                "field": "dateCreated"
			}
        },
        "Temporal (Time)": {
            "terms": {
                "field": "temporal"
            }
        },
        "Topic": {
            "terms": {
                "field": "topic"
            }
        }
    }
}

try:
    sys.path.append(BASE_DIR)
    from instance import conf as CONF
    if hasattr(CONF, "ELASTIC_SEARCH"):
        REPO_SEARCH = Elasticsearch([CONF.ELASTIC_SEARCH])
except ImportError:
    CONF = dict()
    print("Failed to import config from instance")

if not REPO_SEARCH:
    # Sets default using Elasticsearch defaults of localhost and ports
    # 9200 and 9300
    REPO_SEARCH = Elasticsearch()

def browse(pid):
    """Function takes a pid and runs query to retrieve all of it's children
    pids

    Args:
        pid -- PID of Fedora Object
    """
    search = Search(using=REPO_SEARCH, index="repository") \
             .filter("term", inCollection=pid) \
             .sort("titlePrincipal")
               
    results = search.execute()
 #return {"hits": results}
    return results.to_dict()

def filter_query(facet, facet_value, query=None):
    """Function takes a facet, facet_value, and query string, and constructs
    filter for Elastic search.

    Args:
        facet -- Facet name
        facet_value -- Facet value
        query -- Query, if blank searches entire index
    """
    dsl = {
        "size": 25,
        "query": {
            "filtered":  {
                "filter": {
                    "term": {
							AGGS_DSL["aggs"][facet]["terms"]["field"]: facet_value
                    }
                }
            }
        }
    }
    if query is not None:
        dsl["query"]["match"] = {"_all": query}
    results = REPO_SEARCH.search(body=dsl, index="repository")
    return results

def get_aggregations(pid=None):
    """Function takes an optional pid and returns the aggregations
    scoped by the pid, if pid is None, runs aggregation on full ES
    index.

    Args:
        pid -- PID of Fedora Object, default is None

    Returns:
        dictionary of the results
    """
    #search = Search(using=REPO_SEARCH, index="repository) \
    if pid is not None:
        AGGS_DSL["query"] = {"match":{"inCollection": pid } }
    return REPO_SEARCH.search(index="repository", body=AGGS_DSL)['aggregations']
        

def get_detail(pid):
    """Function takes a pid and returns the detailed dictionary from 
    the search results.

    Args:
        pid -- PID of Fedora Object
    """
    search = Search(using=REPO_SEARCH, index="repository") \
             .filter("term", pid=pid)
    result = search.execute()
    if len(result) < 1:
        # Raise 404 error because PID not found
        abort(404)
    return result.to_dict()
 

def get_pid(es_id):
    """Function takes Elastic search id and returns the object's
    pid.

    Args:
        pid -- PID of Fedora Object
    """
    es_doc = REPO_SEARCH.get_source(id=es_id, index="repository")
    return es_doc.get("pid")