from helpers.pod_information import PodInformation
from constants import namespace

"""
List of pods where we have specific interactions
"""

ingest_pod = PodInformation(['app.kubernetes.io/component=ingest'], '/srv/logs/ingest/', namespace=namespace)
yarn_rm_pod = PodInformation(['component=yarn-rm'], '', namespace=namespace)
hdfs_nn_pod = PodInformation(['component=hdfs-nn'], '', namespace=namespace)
web_datawave_pod = PodInformation(['application=dwv-web-datawave'], '', namespace=namespace)
web_dictionary_pod = PodInformation(['application=dwv-web-dictionary'], '', namespace=namespace)
web_authorization_pod = PodInformation(['application=dwv-web-authorization'], '', namespace=namespace)