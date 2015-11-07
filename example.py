import wserver
import time


def getdate(opts):
    resp = "Hello %s the time is %s" % \
        (opts[0]['clientip'], time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
    return [200, resp]


# Create instance to listend on port 8080 with 5 threads
webserver = wserver.Webserver(8080, '0.0.0.0', 5)

# webserver will call function getdate on http://name/getdate
webserver.add_capability(getdate)

try:
    webserver.start()
except KeyboardInterrupt:
    webserver.stop()
