from datetime import datetime
from utilities import setup_logger, log_http_response
from helpers import pods
import requests
import logging

log = setup_logger("reload_accumulo_cache", log_level=logging.DEBUG)


def reload_accumulo_cache():
    log.info("Reloading the accumulo cache...")
    request = f"https://localhost:8443/DataWave/Common/AccumuloTableCache/reload/datawave.metadata"
    resp = requests.get(request, cert="resources/mock_server.pem", verify=False)
    log_http_response(resp, log)


def view_accumulo_cache():
    log.info("Viewing the accumulo cache...")
    request = f"https://localhost:8443/DataWave/Common/AccumuloTableCache/"
    resp = requests.get(request, cert="resources/mock_server.pem", verify=False)
    log_http_response(resp, log)
    log.info(resp.text)
    return resp.text


if __name__ == "__main__":
    view_accumulo_cache()
    # reload_accumulo_cache()