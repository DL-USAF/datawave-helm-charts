import helpers.pods as pods
from helpers.reload_accumulo_cache import reload_accumulo_cache, view_accumulo_cache
import pytest
from datetime import datetime
from utilities import setup_logger, log_test_start, assert_test
import re
import subprocess
import time
from utilities import Retry
from io import StringIO
import pandas as pd
import xml.etree.ElementTree as ET
from logging import Logger


# ---- Changable values ----
"""
- To change what namespace the tests is running against, change the namespace
    variable in the constants.py file.
-
"""
src_file = "resources/more-tv-shows.json"
data_folder = 'myjson'


@pytest.fixture()
def refresh_cache(log: Logger):
    """Fixture to handle teardown of ingest test.

    After ingesting we must refresh the accumulo cache to be able to query the
    ingested data. For some reasons that we're not entirely sure about the refresh
    needs to be ran twice in order to work. If either refresh fails to complete
    within 5 minutes we will log an error and exit the test as we can not proceed
    with query testing without both refreshes completing.
    """
    # setup
    yield
    # Teardown: Need to refresh accumulo cache when it's ready
    log.info('Attempting to refresh accumulo cache')
    try:
        reload_accumulo_cache()
        check_cache_ready(log)
        log.debug("\nWhat about refresh?\nYou've already had it.\nWe've had one, yes. What about second refresh?")
        reload_accumulo_cache()
        check_cache_ready(log)
    except TimeoutError as e:
        msg = 'Cache failed to refresh. You will need to do so manually before proceeding.'
        log.error(e)
        log.warning(msg)
        pytest.exit(msg, returncode=2)
    else:
        log.info('Cache refreshed and is now ready for queries.')


@Retry(time_limit_min=5, delay_sec=10)
def check_cache_ready(log: Logger):
    """Checks if the accumulo cache has been refreshed

    We don't entirely understand why this method of checking works but we think
    it is because when a cache reload is started the `lastRefresh` field of the
    tableCache objects are set to epoch, they are then updated to the current
    timestamp when the refresh completes. Apparently we only need the metadata
    tableCache to finish refreshing before we can continue on, so that is the
    only one that we check.
    """
    root = ET.fromstring(view_accumulo_cache())
    table = root.find(".//{http://webservice.datawave.nsa/v1}TableCache[@tableName='datawave.metadata']")
    if '1970' in table.attrib['lastRefresh']:
        msg = f'Cache not refreshed for {table.attrib["tableName"]} yet.'
        log.debug(msg)
        raise UserWarning(msg)


def get_mapreduce_statuses(resp: str, log: Logger):
    """
    Pulls out the status of each hadoop yarn application to and saves them into
    a list.

    Parameters
    ----------
    resp: str
        Response string of performing an exec command on a pod. Specifically the
        cmd 'yarn app -list -appStates ALL'.

    log: Logger
        The Logger object for logging to.

    Return
    ------
    statuses: list
        a list of strings representing the applications statuses.
    """
    resp = re.sub(' *', '', resp)
    df = pd.read_csv(StringIO(resp), sep='\t', skiprows=3, header=0)
    log.debug(df)
    statuses = df.State.to_list()

    return statuses


def get_mapreduce_last_status(resp: str, log: Logger):
    """
    Gets the status of the last application to have run in Hadoop Yarn MapReduce.

    Parameters
    ----------
    resp: str
        Response string of performing an exec command on a pod. Specifically the
        cmd 'yarn app -list -appStates ALL'.

    log: Logger
        The Logger object for logging to.

    Return
    ------
    status: str
        the status of the last Hadoop Yarn application.
    """
    statuses = get_mapreduce_statuses(resp, log)
    return statuses[-1]


@Retry(time_limit_min=3)
def check_app_statuses(baseline_num_apps: int, log: Logger):
    """
    Grabs the Hadoop Yarn applications and checks the statuses of each
    application found.

    Retry wrapper will recheck pod every 5 seconds for 3 minutes. This is a
    blocking wait.

    Parameters
    ----------
    baseline_num_apps: int
        the number of apps that were found in Hadoop Yarn before ingesting
        data.

    log: Logger
        The Logger object for logging to.

    Raises
    ------
    RuntimeError
        Raised if the any of the applications found in Hadoop Yarn have
        statuses failed or killed

    Notes
    -----
    This is a blocking operation. The program will wait until the retries are
    finished before exiting this function.

    We check if all apps have FINISHED and raise an error if any have not. This
    means that if an ingest from a prior run failed, it will still be in the app
    list and will fail this test. We don't expect this to cause problems as the
    intended use is immediately after deployment, so we expect each run to be
    with a fresh pod without any failing ingests for most practical executions.
    """
    cmd = 'yarn application -list -appStates ALL'
    END_STATES = ['FINISHED', 'FAILED', 'KILLED']

    resp = pods.yarn_rm_pod.execute_cmd(cmd)
    statuses = get_mapreduce_statuses(resp, log)

    if len(statuses) == baseline_num_apps:
        msg = "Have not yet received a new Yarn application"
        log.info(msg)
        raise RuntimeError(msg)
    elif any(status != 'FINISHED' for status in statuses):
        log.info(f"MapReduce App Status: {statuses}")
        msg = "One or more Yarn applications have not yet finished."
        log.info(msg)
        raise RuntimeError(msg)


def test_datawave_ingest(refresh_cache: None, log: Logger):
    """Tests the ingest of data into DataWave.
    Step 1) Get number of existent apps in Hadoop Yarn
    Step 2) copy data into DataWave HDFS
    Step 3) Check the Hadooop Yarn Applications
    """
    log_test_start(log, test_datawave_ingest)
    # get baseline number of statuses
    cmd = 'yarn application -list -appStates ALL'
    resp = pods.yarn_rm_pod.execute_cmd(cmd)
    num_of_starting_statuses = len(get_mapreduce_statuses(resp, log))
    log.info(f"Number of Apps before starting ingest: {num_of_starting_statuses}")

    test_filename = f"test-{num_of_starting_statuses+1}.json"
    # copy data file to hdfs node
    cmd = [
        'kubectl',
        'cp',
        '-n',
        pods.namespace,
        src_file,
        f"{pods.hdfs_nn_pod.podname}:/tmp/{test_filename}"
    ]
    log.debug(cmd)
    log.info("Running kubectl copy...")
    proc = subprocess.run(cmd)
    log.debug(proc)

    # Check file got copied to pod
    cmd = f"ls tmp"
    log.info("Checking the test data file got copied to pod...")
    resp = pods.hdfs_nn_pod.execute_cmd(cmd)
    if test_filename not in resp:
        raise RuntimeError("Test data file was not found inside hadoop pod.")

    # copy local pod file to hdfs
    cmd = f'hdfs dfs -put /tmp/{test_filename} hdfs://hdfs-nn:9000/data/{data_folder}'
    log.info("Running copy into HDFS...")
    resp = pods.hdfs_nn_pod.execute_cmd(cmd)
    log.debug(resp)
    log.info("copy into HDFS complete...")

    failed = None
    # Check Hadoop yarn for any failed or running applications
    try:
        log.info("Checking application statuses")
        check_app_statuses(num_of_starting_statuses, log)
    except (RuntimeError, TimeoutError) as e:
        failed = repr(e)

    assert_test(not failed, log, fail_msg=failed)
