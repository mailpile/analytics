import sys
import re
import urllib
import urllib2
import urlparse
import requests
import socket
import threading
import time
import GeoIP
from datetime import datetime
import math
import random

server = "localhost:8080"
versions = []
threadhits = []

def approx_poisson():
    # Poi(lambd) ~ Norm(lambd, lambd**2) if lambd ~ 10 and
    # continuum is corrected. This is a naive implementation.
    x = random.normalvariate(10, 3.16227)
    if x < 0:
        return approx_poisson()
    return x

def installed_time():
    # Something nice and random
    return int(3600 * 24 * approx_poisson())

def load_versions(vfile):
    global versions
    with open(vfile) as f:
        versions = [x.strip() for x in f.readlines()]
    print "Loaded Mailpile versions"


def hit(id):
    for i in range(100):
        # print "Loop %d on thread %d" % (i, id)
        threadhits[id] += 1
        cc = random.sample(GeoIP.country_codes, 1)[0]
        ts = installed_time()
        vn = random.sample(versions, 1)[0]
        parms = urllib.urlencode({"cc": cc, "ts": ts, "vn": vn})
        try:
            res = urllib2.urlopen("http://%s/checkin/?%s" % (server, parms))
            # print res.read()
        except urllib2.HTTPError, e:
            print e

def stresstest():
    threads = []
    for i in range(10):
        print "Starting thread %d" % i
        threadhits.append(0)
        T = threading.Thread(target=hit, args=[i])
        threads.append(T)
        T.start()

    [x.join() for x in threads]


if __name__ == "__main__":
    load_versions("data/mailpile.versions")
    t0 = datetime.now()
    stresstest()
    t1 = datetime.now()
    print "Stress test of %d hits completed in %s seconds" % (sum(threadhits), (t1-t0))
