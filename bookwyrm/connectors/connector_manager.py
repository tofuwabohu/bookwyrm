""" interface with whatever connectors the app has """
import importlib
import re
from urllib.parse import urlparse

from django.dispatch import receiver
from django.db.models import signals

from requests import HTTPError

from bookwyrm import models
from bookwyrm.tasks import app


class ConnectorException(HTTPError):
    """ when the connector can't do what was asked """


def search(query, min_confidence=0.1):
    """ find books based on arbitary keywords """
    if not query:
        return []
    results = []

    # Have we got a ISBN ?
    isbn = re.sub(r"[\W_]", "", query)
    maybe_isbn = len(isbn) in [10, 13]  # ISBN10 or ISBN13

    dedup_slug = lambda r: "%s/%s/%s" % (r.title, r.author, r.year)
    result_index = set()
    for connector in get_connectors():
        result_set = None
        if maybe_isbn:
            # Search on ISBN
            if not connector.isbn_search_url or connector.isbn_search_url == "":
                result_set = []
            else:
                try:
                    result_set = connector.isbn_search(isbn)
                except (HTTPError, ConnectorException):
                    pass

        # if no isbn search or results, we fallback to generic search
        if result_set in (None, []):
            try:
                result_set = connector.search(query, min_confidence=min_confidence)
            except (HTTPError, ConnectorException):
                continue

        # if the search results look the same, ignore them
        result_set = [r for r in result_set if dedup_slug(r) not in result_index]
        # `|=` concats two sets. WE ARE GETTING FANCY HERE
        result_index |= set(dedup_slug(r) for r in result_set)
        results.append(
            {
                "connector": connector,
                "results": result_set,
            }
        )

    return results


def local_search(query, min_confidence=0.1, raw=False):
    """ only look at local search results """
    connector = load_connector(models.Connector.objects.get(local=True))
    return connector.search(query, min_confidence=min_confidence, raw=raw)


def isbn_local_search(query, raw=False):
    """ only look at local search results """
    connector = load_connector(models.Connector.objects.get(local=True))
    return connector.isbn_search(query, raw=raw)


def first_search_result(query, min_confidence=0.1):
    """ search until you find a result that fits """
    for connector in get_connectors():
        result = connector.search(query, min_confidence=min_confidence)
        if result:
            return result[0]
    return None


def get_connectors():
    """ load all connectors """
    for info in models.Connector.objects.order_by("priority").all():
        yield load_connector(info)


def get_or_create_connector(remote_id):
    """ get the connector related to the object's server """
    url = urlparse(remote_id)
    identifier = url.netloc
    if not identifier:
        raise ValueError("Invalid remote id")

    try:
        connector_info = models.Connector.objects.get(identifier=identifier)
    except models.Connector.DoesNotExist:
        connector_info = models.Connector.objects.create(
            identifier=identifier,
            connector_file="bookwyrm_connector",
            base_url="https://%s" % identifier,
            books_url="https://%s/book" % identifier,
            covers_url="https://%s/images/covers" % identifier,
            search_url="https://%s/search?q=" % identifier,
            priority=2,
        )

    return load_connector(connector_info)


@app.task
def load_more_data(connector_id, book_id):
    """ background the work of getting all 10,000 editions of LoTR """
    connector_info = models.Connector.objects.get(id=connector_id)
    connector = load_connector(connector_info)
    book = models.Book.objects.select_subclasses().get(id=book_id)
    connector.expand_book_data(book)


def load_connector(connector_info):
    """ instantiate the connector class """
    connector = importlib.import_module(
        "bookwyrm.connectors.%s" % connector_info.connector_file
    )
    return connector.Connector(connector_info.identifier)


@receiver(signals.post_save, sender="bookwyrm.FederatedServer")
# pylint: disable=unused-argument
def create_connector(sender, instance, created, *args, **kwargs):
    """ create a connector to an external bookwyrm server """
    if instance.application_type == "bookwyrm":
        get_or_create_connector("https://{:s}".format(instance.server_name))
