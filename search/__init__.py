"""Module wraps Elastic Search functionality"""

__author__ = "Jeremy Nelson, Sarah Bogard"

import click
import os
import requests
import sys

from collections import OrderedDict
from copy import deepcopy
from flask import abort
from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, Q, A
import xml.etree.ElementTree as etree

etree.register_namespace("mods", "http://www.loc.gov/mods/v3")

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
REPO_SEARCH = None
AGGS_DSL = {
    "sort": ["titlePrincipal.keyword"],
    "size": 0,
    "aggs": {
        "Format": {
             "terms": {
                 "field": "typeOfResource.keyword"
            }
        },
        "Geographic": {
            "terms": {
                "field": "subject.geographic.keyword"
            }
        },
        "Genres": {
            "terms": {
                "field": "genre.keyword"
            }
        },
        "Languages": {
	        "terms": {
                "field": "language.keyword"
			}
        },
        "Publication Year": {
            "terms": {
                "field": "publicationYear.keyword"
			}
        },
        "Temporal (Time)": {
            "terms": {
                "field": "subject.temporal.keyword"
            }
        },
        "Topic": {
            "terms": {
                "field": "subject.topic.keyword"
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

def advanced_search(form):
    """Function takes the Advanced Search form and builds query

    Args:
        form(AdvancedSearch): Advanced Search form
    """
    search = Search(using=REPO_SEARCH, index="repository")
    query_chain = None
    for row in form.text_search:
        if len(row.q.data) < 1:
            continue
        if row.mode.data.startswith("creator"):
            query = Q("match_phrase", creator=row.q.data)
        elif row.mode.data.startswith("kw"):
            query = Q("query_string", query=row.q.data)
        elif row.mode.data.startswith("subject"):
            query = Q("multi_match", 
                      query=row.q.data, 
                      fields=["subject.geographic",
                              "subject.topic",
                              "subject.temporal"])
        elif row.mode.data.startswith("title"):
            query = Q("match_phrase", titlePrincipal=row.q.data)
        if query_chain is not None:
            if row.operator.data.startswith("or"):
                query_chain = query_chain | query
            elif row.operator.data.startswith("not"):
                query_chain = query_chain&~query
            else:
                query_chain = query_chain & query
        else:
            query_chain = query
    search = search.query(query_chain)   
    obj_formats = None
    for row in form.obj_format:
        if row.data is True:
            if row.name.endswith("audio"):
                value = "sound recording"
            elif row.name.endswith("moving_image"):
                value = "moving image"
            elif row.name.endswith("image"):
                value = "still image"
            elif row.name.endswith("mixed_material"):
                value = "mixed material"
            elif row.name.endswith("pdf"):
                value = "text"
            obj_query = Q("match_phrase", typeOfResource=value)
            if obj_formats is None:
                obj_formats = obj_query
            else:
                obj_formats = obj_formats|obj_query
    if obj_formats:
        search = search.query(obj_formats)
    search = __by_collection__(search, form.by_collection.data)
    if form.by_genre.data and form.by_genre.data != "none":
        search = search.query(Q("match_phrase", genre=form.by_genre.data)) 
    search = __by_topic__(search, form.by_topic.data)
    search.aggs.bucket("Format", A("terms", field="typeOfResource.keyword"))
    search.aggs.bucket("Geographic", A("terms", field="subject.geographic.keyword"))
    search.aggs.bucket("Genres", A("terms", field="genre.keyword"))
    search.aggs.bucket("Languages", A("terms", field="language.keyword"))
    search.aggs.bucket("Publication Year", A("terms", field="publicationYear.keyword"))
    search.aggs.bucket("Temporal (Time)", A("terms", field="subject.temporal.keyword"))
    search.aggs.bucket("Topic", A("terms", field="subject.topic.keyword"))
    search = search.params(size=250)
    results = search.execute()
    output = results.to_dict()
    return output, search.to_dict()

def __by_collection__(search, collection_data):
    """Helper function adds by_collection if available"""
    if collection_data.endswith("thesis"):
        search = search.query(Q("match_phrase", genre="thesis"))
    elif collection_data.endswith("special collections"):
        spc_collection_search = Search(using=REPO_SEARCH, index='repository')
        spc_collection_search = spc_collection_search.query(
            Q("match_phrase", titlePrincipal="Special Collections Materials")).\
            source(["pid"])
        spc_collection_result = spc_collection_search.execute()
        if spc_collection_result.hits.total > 0:
            in_collection = spc_collection_result.hits.hits[0]["_source"]["pid"]
            search = search.query(Q("match_phrase", inCollection=in_collection))
    ## elif collection_data.endswith("general"):
    elif collection_data.endswith("music library"):
        music_dept_search = Search(using=REPO_SEARCH, index="repository")
        music_dept_search = music_dept_search.query(
            Q("match_phrase", titlePrincipal="Music Department")).\
            source(["pid"])
        music_dept_result = music_dept_search.execute()
        if music_dept_result.hits.count > 0:
            in_music = music_dept_result.hits.hits[0]["_source"]["pid"]
            search = search.query(Q("match_phrase", inCollection=in_music))
    return search

def __by_topic__(search, topic_data):
    """Helper function adds by_topic """
    return search
    

def browse(pid, from_=0, size=25):
    """Function takes a pid and runs query to retrieve all of it's children
    pids

    Args:
		pid: PID of Fedora Object
        from_(int): Start result from, default is 0
        size(int): Size of shard, default is 25
    """
    search = Search(using=REPO_SEARCH, index="repository") \
             .filter("term", **{"parent.keyword": pid}) \
             .params(size=size, from_=from_) \
             .sort("titlePrincipal.keyword")
    results = search.execute()
    output = results.to_dict()
    search = Search(using=REPO_SEARCH, index="repository") \
             .filter("term", inCollections=pid) \
             .params(size=0)
    search.aggs.bucket("Format", A("terms", field="typeOfResource.keyword"))
    search.aggs.bucket("Geographic", A("terms", field="subject.geographic.keyword"))
    search.aggs.bucket("Genres", A("terms", field="genre.keyword"))
    search.aggs.bucket("Languages", A("terms", field="language.keyword"))
    search.aggs.bucket("Publication Year", A("terms", field="publicationYear.keyword"))
    search.aggs.bucket("Temporal (Time)", A("terms", field="subject.temporal.keyword"))
    search.aggs.bucket("Topic", A("terms", field="subject.topic.keyword"))
    facets = search.execute()
    output['aggregations'] = facets.to_dict()["aggregations"]
    return output

def filter_query(facet, facet_value, query=None, size=25, from_=0):
    """Function takes a facet, facet_value, and query string, and constructs
    filter for Elastic search.

    Args:
		facet: Facet name
		facet_value: Facet value
		query: Query, if blank searches entire index
		size: size of result set, defaults to 25
		from_: From location, used for infinite browse
    """
    dsl = {
        "size": size,
	"from": from_,
        "aggs": AGGS_DSL['aggs'],
    }
    field_name = AGGS_DSL["aggs"][facet]["terms"]["field"] 
    if query is not None:
        dsl["query"] = {
            "bool": {
                "must": [
                    {
                        "match": {
                            "_all": query
                        }
                    }
                ],
                "filter": [
                    {
                        "term": {
                            field_name : facet_value
                        }
                    }
                ]
            }
        }
    else:
        dsl["query"] = {
            "term": {
                field_name : facet_value
            }
        }
    results = REPO_SEARCH.search(body=dsl, index="repository")
    return results


def specific_search(query, type_of, size=25, from_=0, pid=None):
    """Function takes a query and fields list and runs a search on those
    specific fields.

    Args:
        query: query terms to search on
        type_of: Type of query, choices should be creator, title, subject,
                 and number

    Returns:
	    A dict of the search results
    """
    search = Search(using=REPO_SEARCH, index="repository")
    if type_of.startswith("creator"):
        search = search.query("match_phrase", creator=query)
    elif type_of.startswith("number"):
        search = search.filter("term", pid=query)
    elif type_of.startswith("title"):
        search = search.query("match_phrase", titlePrincipal=query)
    elif type_of.startswith("subject"):
        search = search.query(Q("match_phrase", **{"subject.topic": query}) |\
                     Q("match_phrase", **{"subject.geographic": query}) |\
                     Q("match_phrase", **{"subject.temporal": query}))
    elif query is None and pid is not None:
        search = search.filter("term", parent=pid) \
                 .params(size=size, from_=from_) \
                 .sort("titlePrincipal")
    else:
        search = search.query(
            Q("query_string", query=query, default_operator="AND"))
        search = search.params(size=size, from_=from_)
    search.aggs.bucket("Format", A("terms", field="typeOfResource.keyword"))
    search.aggs.bucket("Geographic", A("terms", field="subject.geographic.keyword"))
    search.aggs.bucket("Genres", A("terms", field="genre.keyword"))
    search.aggs.bucket("Languages", A("terms", field="language.keyword"))
    search.aggs.bucket("Publication Year", A("terms", field="dateCreated.keyword"))
    search.aggs.bucket("Temporal (Time)", A("terms", field="subject.temporal.keyword"))
    search.aggs.bucket("Topic", A("terms", field="subject.topic.keyword"))
    results = search.execute()
    return results.to_dict()

def get_aggregations(pid=None):
    """Function takes an optional pid and returns the aggregations
    scoped by the pid, if pid is None, runs aggregation on full ES
    index.

    Args:
        pid -- PID of Fedora Object, default is NoneBASE_DIR = os.path.dirname(os.path.dirname(__file__))

    Returns:
        dictionary of the results
    """
    #search = Search(using=REPO_SEARCH, index="repository) \
    dsl = deepcopy(AGGS_DSL)
    if pid is not None:
        dsl["query"] = {"term": { "inCollections": pid } }
    results = REPO_SEARCH.search(index="repository", body=dsl)['aggregations']
    output = OrderedDict()
    for key in sorted(results):
        aggregation = results[key]
        if len(aggregation.get('buckets')) > 0:
            output[key] = aggregation
    return output
        
def get_detail(pid):
    """Function takes a pid and returns the detailed dictionary from 
    the search results.

    Args:
        pid -- PID of Fedora Object
    """
    search = Search(using=REPO_SEARCH, index="repository") \
             .filter("term", **{"pid.keyword":pid})
    result = search.execute()
    if len(result) > 0:
        return result.to_dict()
 

def get_pid(es_id):
    """Function takes Elastic search id and returns the object's
    pid.

    Args:
        pid -- PID of Fedora Object
    """
    es_doc = REPO_SEARCH.get_source(id=es_id, index="repository")
    return es_doc.get("pid")

def get_title(pid):
    """Function takes a pid and returns the titlePrincipal as a string

    Args:
        pid -- PID of Fedora Object
    """
    result = REPO_SEARCH.search(body={"query": {"term": {"pid.keyword": pid }},
			                         "_source": ["titlePrincipal"]},
                                index='repository')
    if result.get('hits').get('total') == 1:
        return result['hits']['hits'][0]['_source']['titlePrincipal']
    return "Home"

if __name__ == "__main__":
    print()
