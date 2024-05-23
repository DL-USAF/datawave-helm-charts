import requests
import logging
import json
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from utilities import setup_logger, log_http_response
from logging import Logger
from helpers import pods


@dataclass
class QueryParams:
    query_name: str
    column_visibility: str
    query: str
    auths: str
    page_size: int = 5
    begin: str = '19700101'
    end: str = '20990101'

    def get(self):
        return {"queryName": self.query_name,
                "columnVisibility": self.column_visibility,
                "pagesize": self.page_size,
                "begin": self.begin,
                "end": self.end,
                "query": self.query,
                "auths": self.auths
                }


class QueryConnection:
    """A class representing a connection for executing queries.

    This class provides functionality to establish and manage a connection
    for executing queries on a remote server.

    Parameters
    ----------
    ip : str
        The IP address of the server to connect to.
    port : str
        The port number of the server to connect to.
    cert : str
        The path to the SSL certificate for secure communication.
    query_params : QueryParams
        An instance of the QueryParams class containing parameters for the query.
    log : Logger, optional
        An optional logger object for logging messages. If not provided,
        a default logger will be created.

    Attributes
    ----------
    url_base : str
        The URL of the server.
    cert : str
        The path to the SSL certificate for secure communication.
    query_params : QueryParams
        An instance of the QueryParams class containing parameters for the query.
    log : Logger
        The logger object used for logging messages.

    """
    create_endpoint: str = 'DataWave/Query/EventQuery/create.json'
    quuid: Optional[str] = None

    def __init__(self, ip: str, port: str, cert: str, query_params: QueryParams, log: Logger = None):
        self.url_base = f'https://{ip}:{port}'
        self.cert = cert
        self.query_params = query_params

        if log is None:
            now = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.log = setup_logger(__name__, log_file=f'logs/local/{__name__}_{now}.log', log_level=logging.DEBUG)
        else:
            self.log = log

    @property
    def next_endpoint(self):
        if self.quuid is None:
            raise ValueError("Query UUID not set, cannot create the next endpoint.")
        return f'DataWave/Query/{self.quuid}/next.json'

    @property
    def close_endpoint(self):
        if self.quuid is None:
            raise ValueError("Query UUID not set, cannot create the close endpoint.")
        return f'DataWave/Query/{self.quuid}/close.json'

    def __enter__(self):
        """Enter method for context manager

        This method is called when entering a context managed by the 'with' statement.
        It initiates the creation of a query endpoint and sets the necessary attributes
        to maintain the query state.

        Returns
        -------
        self:
            The current instance with the query endpoint created.

        Raises
        ------
        RuntimeError:
            If the Datawave `create` endpoint fails with a non-200 response.
        """
        self.log.debug("Inside enter...")
        request = f'{self.url_base}/{self.create_endpoint}'
        self.log.debug(request)
        self.log.debug(f'Executing with {self.query_params}')

        resp = requests.post(request, data=self.query_params.get(), cert=self.cert, verify=False)
        log_http_response(resp, self.log)
        if (resp.status_code == 200):
            self.quuid = resp.json()['Result']
            self.open = True
        else:
            self.log.error(f"Request failed - (Status Code:{resp.status_code}, Reason:{resp.reason})")
            raise RuntimeError(f"Create endpoint came back with non-200 response. {resp.status_code}")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit method for context manager

        This method is called when exiting a context managed by the 'with' statement.
        It finalizes the query by closing the connection to the endpoint.

        Parameters
        ----------
        exc_type:
            The type of the exception raised, if any.

        exc_value: Exception
            The exception raised, if any.

        traceback:
            The traceback object representing the call stack.

        Notes
        -----
        Any exception raised within the 'with' block will be passed to this method.
        If an exception is not handled within the method, it will propagate.
        """
        self.log.debug("Inside exit...")
        request = f'{self.url_base}/{self.close_endpoint}'
        self.log.debug(request)
        requests.get(request, cert=self.cert, verify=False)
        self.open = False

    def __iter__(self):
        """Iterator method for iterator.

        This method is called when the object is used in an iteration context
        (e.g., in a 'for' loop).
        It ensures that the query has been started and returns the instance for
        iteration.

        Returns
        -------
        self:
            The current instance ready for iteration.

        Raises
        ------
        RuntimeError:
            If the query has not been started.
        """
        self.log.debug("Inside iter...")
        if not self.open:
            raise RuntimeError("Query has not been started!")
        return self

    def __next__(self):
        """Next method for iterator

        This method is called to retrieve the next item in the iteration sequence.
        It performs a request to fetch the next data from the query endpoint and returns it.

        Returns
        -------
            dict: The next item in the iteration sequence.

        Raises
        ------
        StopIteration:
            If there are no more items to iterate over.
            Note: this is the normal method to stop an iterator.
        """
        self.log.debug("Inside next...")
        request = f'{self.url_base}/{self.next_endpoint}'
        self.log.debug(request)
        next_resp = requests.get(request, cert=self.cert, verify=False)
        log_http_response(next_resp, self.log)
        if (next_resp.status_code == 200):
            return next_resp.json()
        else:
            raise StopIteration


def print_query_fields(query_params: QueryParams, cert, log=setup_logger('query', log_level=logging.DEBUG)):
    """Helper method for verifying fields of a query"""
    with QueryConnection(pods.web_datawave_pod.pod_ip, '8443', cert, query_params, log=log) as qc:
        for data in qc:
            print(f"Number of Returned Events: {data['ReturnedEvents']}")
            events = data['Events']
            for event in events:
                print(f"Event:\n{json.dumps(event, indent=1)}")
                fields = event['Fields']
                for field in fields:
                    if (field['name'] == 'NAME'):
                        print(f"Value: {field['Value']['value']}")


if __name__ == "__main__":
    """
    GENRES == 'action' || GENRES =~ 'adv.*'
    """
    query_params = QueryParams(query_name="test-query",
                               column_visibility="BAR",
                               query="GENRES == 'Comedy'",
                               auths="BAR,FOO,PRIVATE,PUBLIC")
    print_query_fields(query_params, 'resources/mock_server.pem')