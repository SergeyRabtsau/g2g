# g2g
## Description
Github to Graphite connector that get data about PR from Github project, make aggregation according to some business rules and send it to graphite db.

## Requirements
all PIP are declared in `requirements.txt` file

## Quick Start

Getting started with this connector you need update `config.ini` file and provide following configuration properties first:

* `api_token` of your github account that will be used to access github data
* `repo_name` in user/project_name format
* `graphite_server` ip address of graphite server without port

After all configurations were made you can run `get_info.py` file.
You can setup cron job that will send github data into graphite db according to your schedule.