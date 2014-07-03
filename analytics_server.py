from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn
import threading
import urlparse
import json
from datetime import datetime, timedelta
import GeoIP
import os.path

FILE_MPVERSIONS = "data/mailpile.versions"
FILE_MPNEWS = "data/mailpile.news"
CHECKIN_CACHE_MAX = 500
MAX_NEWS_AGE = 300
MAX_CACHE_AGE = 30

versions = []
checkin_cache = []
news_lastchecked = datetime(1970, 1, 1, 0, 0, 1)
checkindb_lastwrite = datetime.now()
news_cache = ""
checkin_lock = threading.Lock()
news_lock = threading.Lock()

def load_versions(vfile):
    global versions
    with open(vfile) as f:
        versions = [x.strip() for x in f.readlines()]
    print "Loaded Mailpile versions"

class Handler(BaseHTTPRequestHandler):
    def __init__(self, a, b, c):
        self.dispatch = {
            "/": self._index,
            "/checkin/": self._checkin,
        }
        BaseHTTPRequestHandler.__init__(self, a, b, c)

    def _get_next_checkin_time(self):
        str(datetime.now() + timedelta(seconds=604800))

    def _get_newest_version(self):
        return versions[-1]

    def _register_checkin(self, uptime, country, version):
        global checkindb_lastwrite
        global checkin_cache
        with checkin_lock:
            checkin_cache.append((uptime, country, version))
            if (len(checkin_cache) >= CHECKIN_CACHE_MAX or
                (datetime.now() - checkindb_lastwrite).seconds 
                    > MAX_CACHE_AGE):
                with open("checkindb.txt", "a") as fh:
                    for l in checkin_cache:
                        fh.write("%s,%s,%s\n" % l)
                checkin_cache = []
                checkindb_lastwrite = datetime.now()
                print "Wrote out to checkindb"

    def _get_news(self):
        global news_cache
        global news_lastchecked
        if (datetime.now() - news_lastchecked).seconds > MAX_NEWS_AGE:
            if datetime.utcfromtimestamp(os.path.getmtime(FILE_MPNEWS)) > news_lastchecked:
                with news_lock:
                    news_cache = open(FILE_MPNEWS).read()
                    news_lastchecked = datetime.now()
                    print "Reloaded news"
                    load_versions(FILE_MPVERSIONS)

        return news_cache

    def _index(self, qd):
        self._response(200, "Hello!")

    def _checkin(self, qd):
        response = {}
        query = urlparse.parse_qs(qd.query, False, True)

        try:
            assert("ts" in query and len(query["ts"]))
            assert("cc" in query and len(query["cc"]))
            assert("vn" in query and len(query["vn"]))
        except AssertionError, e:
            return self._response(400, "Missing parameters")

        try:
            uptime = int(query["ts"][0])
        except ValueError, e:
            return self._response(400, "ts must be an integer")

        try:
            country = query["cc"][0]
            assert(country in GeoIP.country_codes)
        except AssertionError, e:
            return self._response(400, "cc must be a valid country code")

        try:
            version = query["vn"][0]
            assert(version in versions)
        except AssertionError:
            return self._response(400, "vn must be a valid version number")

        # print uptime, country, version
        self._register_checkin(uptime, country, version)

        response["newest_version"] = self._get_newest_version()
        response["news"] = self._get_news()
        response["reportback_next"] = self._get_next_checkin_time()
        response["reportback_server"] = "checkin.mailpile.is"

        self._response(200, json.dumps(response))

    def _response(self, response_code, message):
        self.send_response(response_code)
        self.end_headers()
        self.wfile.write(message)

    def _404(self, qd):
        self._response(404, "Nothing found")

    def _500(self, qd):
        self._response(500, "Error")

    def do_GET(self):
        parsed_path = urlparse.urlparse(self.path)
        print "Dispatching '%s'" % (str(parsed_path),)
        cb = self.dispatch.get(parsed_path.path, self._404)

        cb(parsed_path)
        try:
            pass
        except Exception, e:
            print e
            print "Something bad happened!"
            self._500(parsed_path)
 

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass

if __name__ == '__main__':
    load_versions(FILE_MPVERSIONS)
    server = ThreadedHTTPServer(('localhost', 8080), Handler)
    print 'Starting server, use <Ctrl-C> to stop'
    server.serve_forever()