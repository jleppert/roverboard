# RoverBoard App


To run the webserver:
```
pip3 install -r requirements.txt
python3 webserver.py
```

URL root is:

http://127.0.0.1:9005


Commands are:

```
# get rover status
curl http://127.0.0.1:9005/status

#start run
curl http://127.0.0.1:9005/start

GET Parameters:
distance (float) = distance in meters (default 1)

pattern (string) = pattern to run, values are "square" for square scan, otherwise straight line

record_gpr (bool) = default false, if set will scan GPR data


#cancel run
curl http://127.0.0.1:9005/cancel



```
