# Tests
Note: To run tests, make sure you are in the `tests` directory.

| Test Name | Description |
| --------- | ----------- |
| Test_Pods | This checks the running pods and their containers to verify they are running |
| Test_Ingest | Takes a test file (tv data) and uploads it to the HDFS for ingest into DataWave. Will monitor the Accumulo MapReduce job and verify it gets to finished. |
| Test_Query | Runs the follow tests: Verify the end points are working for DataWave (create, next, close); Verify the fields made query-able for the data type myjson (tv data) are query-able; Using a specific event, query specific data from DataWave to verify the data being ingested and pulled out matches it in the before state; and testing various combinations of authorizations. |

## Setup
Before running any tests, make sure to ```pip install -r requirements.txt```

## Running the tests
Run `pytest` to run the all the tests defined above.
