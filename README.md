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

#cancel run
curl http://127.0.0.1:9005/cancel



```
