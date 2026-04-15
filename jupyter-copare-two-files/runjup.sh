#!/usr/bin/env bash
source /home/mpoil/empoil/bin/activate
nohup jupyter notebook --no-browser --ip=0.0.0.0 --port=58818 --NotebookApp.token='' --certfile=mycert.pem --keyfile mykey.key &
