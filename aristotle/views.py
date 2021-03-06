"""This module extends and refactors Aristotle Library Apps projects for
Flask using Elasticsearch"""
__author__ = "Jeremy Nelson"

import click
import datetime
import os
import requests

import click

HOME = os.path.abspath(os.curdir)
with open(os.path.join(HOME, "VERSION")) as fo:
    VERSION = fo.read()

from flask import abort, jsonify, render_template, redirect, request,\
    Response, url_for, current_app
from . import cache, REPO_SEARCH
from .blueprint import aristotle
from .forms import SimpleSearch, AdvancedSearch
from search import advanced_search, browse, filter_query, get_aggregations,\
    get_detail, get_pid, specific_search

@aristotle.route("/digitalcc/about")
@aristotle.route("/about")
def about_aristotle():
    """Displays details of current version of Aristotle"""
    index_created_on = REPO_SEARCH.indices.get('repository').get('repository').get('settings').get('index').get('creation_date')
    indexed_on = datetime.datetime.utcfromtimestamp(int(index_created_on[0:10]))
    return render_template("discovery/About.html",
        indexed_on = indexed_on,
        search_form=SimpleSearch(),
        version = VERSION)
    

@aristotle.route("/browse", methods=["POST", "GET"])
def browser():
    """Browse view for AJAX call from client based on the PID in the
    Form
    Returns:
        jsonified version of search result
    """
    if request.method.startswith("POST"):
        pid = request.form["pid"]
        from_ = request.form.get("from", 0)
    else:
        pid = request.args.get('pid')
        from_ = request.args.get('from', 0)
    cache_key = "{}-{}".format(pid, from_)
    browsed = cache.get(cache_key)
    if not browsed:
        browsed = browse(pid, from_)
        cache.set(cache_key, browsed)
    return jsonify(browsed)

@aristotle.route("/contribute")
def view_contribute():
    return render_template("discovery/Contribute.html",
        search_form=SimpleSearch())

@aristotle.route("/copyright")
def view_copyright():
    return render_template("discovery/Copyright.html",
        search_form=SimpleSearch())

@aristotle.route("/takedownpolicy")
def view_takedownpolicy():
    return render_template("discovery/Takedown.html",
        search_form=SimpleSearch())

@aristotle.route("/thesis-capstones")
def theses_capstones():
    return render_template("discovery/ThesesCapstones.html",
        search_form=SimpleSearch())	

@aristotle.route("/needhelp")
def view_help():
    return render_template("discovery/Help.html",
        search_form=SimpleSearch())	
	
@aristotle.route("/pid/<pid>/datastream/<dsid>")
@aristotle.route("/pid/<pid>/datastream/<dsid>.<ext>")
def get_datastream(pid, dsid, ext=None):
    """View returns the datastream based on pid and dsid

    Args:
        pid -- Fedora Object's PID
        dsid -- Either datastream ID of PID
    """
    fedora_url = "{}{}/datastreams/{}/content".format(
        current_app.config.get("REST_URL"),
        pid,
        dsid)
    exists_result = requests.get(fedora_url)
    if exists_result.status_code == 404:
        abort(404)
    return Response(
        exists_result.content, 
        mimetype=exists_result.headers.get('Content-Type'))


@aristotle.route("/detail", methods=["POST"])
def detailer():
    """Detail view for AJAX call from client based on the PID in
	the Form.

    Returns:
        jsonified version of the search result
    """
    if request.method.startswith("POST"):
        pid = request.form["pid"]
        detailed_info = get_detail(pid)
        return jsonify(detailed_info)


@aristotle.route("/image/<uid>")
def image(uid):
    """View extracts the Thumbnail datastream from Fedora based on the
    Elasticsearch ID

    Args:
        uid: Elasticsearch ID
    """
    pid = get_pid(uid)
    thumbnail_url = "{}{}/datastreams/TN/content".format(
        app.config.get("REST_URL"),
        pid)
    raw_thumbnail = cache.get(thumbnail_url)
    if not raw_thumbnail:
        result = requests.get(thumbnail_url)
        if result.status_code > 399:
           abort(500)
        #raw_thumbnail = result.text
        return Response(result.text, mimetype="image/jpeg")

@aristotle.route("/advanced-search",  methods=["POST", "GET"])
def advanced_searching():
    """Advanced search"""
    query=request.args.get('q', None)
    facets=get_aggregations(current_app.config.get("INITIAL_PID"))
    adv_search_form = AdvancedSearch()
    adv_search_form.by_genre.choices = []
    mode=request.args.get("mode", "kw")
    size=request.args.get("size", 125)
    offset=request.args.get("offset", 0)
    facet=request.args.get("facet")
    facet_value = request.args.get("val")
    for bucket in facets.get("Genres").get('buckets'):
        key = bucket.get('key')
        adv_search_form.by_genre.choices.append((key, 
                                                 key.title()))
    adv_search_form.by_genre.choices =  sorted(adv_search_form.by_genre.choices)
    adv_search_form.by_genre.choices.insert(0, ("none", "None"))
    adv_search_form.by_topic.choices = []
    for bucket in facets.get("Topic").get('buckets'):
        key = bucket.get('key')
        adv_search_form.by_topic.choices.append((key, key.title()))
    adv_search_form.by_topic.choices = sorted(adv_search_form.by_topic.choices)
    adv_search_form.by_topic.choices.insert(0, ("none", "None"))
    #adv_search_form.by_thesis_dept.choices = [('all', 'All')]
    if adv_search_form.validate_on_submit():
        search_results, query = advanced_search(adv_search_form)
        #if "html" in request.headers.get("Accept"):
        return render_template(
            'discovery/search-results.html',
            facet=facet,
            facet_val=facet_value,
            mode=mode,
            is_advanced_search=True,
            results = search_results,
            adv_search_form=adv_search_form,
            q=query,
            size=size,
            offset=offset
        )
    else:
        click.echo("Form errors {}".format(adv_search_form.errors.items()))
        #return "In search  form values {}".format(adv_search_form.text_search.data.items())
    return render_template(
        'discovery/index.html',
        pid="coccc:root",
        is_advanced_search=True,
        adv_search_form=adv_search_form,
        q=query,
        mode=request.args.get('mode', 'kw')
    )

@aristotle.route("/search", methods=["POST", "GET"])
def query():
    """View returns Elasticsearch query search results

    Returns:
        jsonified version of the search result
    """
    if request.method.startswith("POST"):
        mode = request.form.get('mode', 'keyword')
        facet = request.form.get('facet')
        facet_val = request.form.get('val')
        offset = request.form.get('offset', 0)
        size = request.form.get('size', 25)
        query = request.form["q"]
    else:
        mode = request.args.get('mode', 'keyword')
        facet = request.args.get('facet')
        offset = request.args.get('offset', 0)
        size = request.args.get('size', 25)
        facet_val = request.args.get('val')
        query = request.args.get('q', None)
    search_results = None
    if mode in ["creator", "title", "subject", "number"]:
         search_results = specific_search(
                query,
                mode,
                size,
                offset)
    if mode.startswith("facet"):
        search_results = filter_query(
            facet, 
            facet_val, 
            query,
            size,
            offset)
    if not search_results and query is not None:
       search_results = specific_search(
           query,
           "keyword",
           size,
           offset)
    if "html" in request.headers.get("Accept"):
        return render_template(
            'discovery/search-results.html',
            facet=facet,
            facet_val=facet_val,
            mode=mode,
            results = search_results,
            search_form=SimpleSearch(),
            q=query,
            size=size,
            offset=offset
        )
    else:
        return jsonify(search_results)
    
@aristotle.route("/pid/<pid>/datastream/<dsid>.<ext>")
def fedora_datastream(pid, dsid, ext):
    """View returns a specific Fedora Datastream including Images, PDFs,
    audio, and video datastreams

    Args:
        pid -- PID
        dsid -- Datastream ID
        ext -- Extension for datastream
    """
    ds_url = "{}{}/datastream/{}".format(
        app.config.get("REST_URL"),
        pid,
        dsid)
    result = requests.get(ds_url)
    if ext.startswith("pdf"):
        mimetype = 'application/pdf'
    if ext.startswith("jpg"):
        mimetype = 'image/jpg'
    if ext.startswith("mp3"):
        mimetype = "audio/mpeg"
    if ext.startswith("wav"):
        mimetype = "audio/wav"
    return Response(result.text, mimetype=mimetype) 


@aristotle.route("/<identifier>/<value>")
def fedora_object(identifier, value):
    """View routes to a Fedora Object based on type of identifier and
    a value. Currently only supports routing by PID, should support DOI
    next.

    Args:
        identifier: Identifier type, currently supports pid
        value: Identifier value to search on

    Returns:
        Rendered HTML from template and Elasticsearch
    """
    size = request.args.get('size')
    if size is None:
        size = current_app.config.get("SIZE", 25) # Default size is 25
    if identifier.startswith("pid"):
        offset = request.args.get("offset", 0)
        results = browse(value, from_=offset, size=size)
        if results['hits']['total'] < 1:
            detail_result = get_detail(value)
            if not 'islandora:collectionCModel' in\
                detail_result['hits']['hits'][0]['_source']['content_models']:
                return render_template(
                    'discovery/detail.html',
                    pid=value,
                    mode='detail',
                    size=size,
                    info=detail_result['hits']['hits'][0],
                    search_form=SimpleSearch())
        if value == current_app.config.get("INITIAL_PID"):
            info = dict()
        else:
            info = get_detail(value)['hits']['hits'][0]['_source']
        return render_template(
            'discovery/index.html',
            pid=value,
            results=results,
            info=info,
            search_form=SimpleSearch(),
            q=value,
            mode='browse',
            size=size,
            offset=offset,
            facets=get_aggregations(value))
    if identifier.startswith("thumbnail"):
        thumbnail_url = "{}{}/datastreams/TN/content".format(
            current_app.config.get("REST_URL"),
            value)
        tn_result = requests.get(thumbnail_url)
        if tn_result.status_code == 404:
            thumbnail = cache.get('default-thumbnail')
            if not thumbnail:
                with current_app.open_resource(
                    "static/img/default-tn.png") as fo:
                    thumbnail = fo.read()
                    cache.set('default-thumbnail', thumbnail)
            mime_type = "image/png"
        else:
            thumbnail = tn_result.content
            mime_type = "image/jpg"
        return Response(thumbnail, mimetype=mime_type)


    return "Should return detail for {} {}".format(identifier, value)


@aristotle.route("/digitalcc")
@aristotle.route("/")
def index():
    """Displays Home-page of Digital Repository"""
    query = request.args.get('q', None)
    mode=request.args.get('mode', 'landing')
    pid = request.args.get('pid', current_app.config.get("INITIAL_PID"))
    if query is None:  
        results = browse(pid)
    else:
        results = search(q=query)
    return render_template(
        'discovery/index.html',
        pid=pid,
        q=query,
        size=current_app.config.get("SIZE", 25), # Default size is 25
        results = results,
        search_form=SimpleSearch(),
        featured_collection=browse(
            current_app.config.get("FEATURED_COLLECTION")),
        mode=mode
    )
