import errno
import email.utils
import logging
import Queue
import re
import socket
import threading
import sys


class Webserver(object):

    class Worker(threading.Thread):
        def __init__(self, inq, func):
            threading.Thread.__init__(self)
            self.inq = inq
            self.func = func
            self.start()

        def run(self):
            val = self.inq.get()
            while val['socket'] != '_END':
                self.func(val)
                val = self.inq.get()

    class stdoutLogger():

        def __init__(self):
            logger = logging.getLogger()
            logger.setLevel(logging.DEBUG)
            handler = logging.StreamHandler(sys.stdout)
            logger.addHandler(handler)
            self.logger = logger

        def get(self):
            return self.logger

    def __init__(self, port=8080, listen_addr='0.0.0.0', thread_count=3, logger=None):
        self.port = port
        self.listen_addr = listen_addr
        self.thread_count = thread_count
        self.server_running = True
        self.inputq = Queue.Queue()
        self.MAXLINE = 1024
        self.response_functions = {}
        self.RESPONSE_CODES = {200: "OK",
                               201: "Created",
                               300: "Redirect",
                               400: "Bad Request",
                               401: "Unauthorized",
                               403: "Forbidden",
                               404: "Not Found",
                               409: "Conflict",
                               500: "Internal Server Error",
                               501: "Not Implemented",
                               503: "Service Unavailable"
                               }
        if not logger:
            l = self.stdoutLogger()
            self.logger = l.get()
        else:
            self.logger = logger

    def _comms(self, data):
        inn = data['socket'].recv(self.MAXLINE)
        inn = inn.split('\n')
        self.logger.debug("%s\t%s" % (data['clientip'], inn[0]))
        httphead = False
        if re.match("^GET|^HEAD", inn[0]):
            if re.match("^HEAD", inn[0]):
                httphead = True
            get = inn[0].split()
            cmd = get[1].strip('/')
            cmd = cmd.split('/')
            cmd = [data] + cmd
            if cmd[1] in self.response_functions:
                curr_function = self.response_functions[cmd[1]]['function_ref']
                if len(self.response_functions[cmd[1]]) > 1:
                    cmd[0].update(self.response_functions[cmd[1]])
                    del cmd[0]['function_ref']
                status, resp = curr_function(cmd)
                # status, resp = self.response_functions[cmd[1]][0](cmd)
                if httphead:
                    resp = ''
                data['socket'].send(self._httpresp(status, resp))
            else:
                resp = '' if httphead else "Not Implemented"
                data['socket'].send(self._httpresp(501, resp))
        else:
            resp = '' if httphead else "Not Supported"
            data['socket'].send(self._httpresp(501, resp))
        if httphead:
            resp = "EMPTY"
        self.logger.info("Response %s\t%s" % (data['clientip'], resp))
        data['socket'].close()
        return

    def _httpresp(self, status, data):
        # Generate simple and compliant HTTP responses
        resp = []
        if status in self.RESPONSE_CODES:
            resp.append("HTTP/1.0 %s %s\r\n" % (status, self.RESPONSE_CODES[status]))
        else:
            resp.append("HTTP/1.0 %s %s\r\n" % (200, self.RESPONSE_CODES[200]))
        resp.append("Date: %s\r\n" %
                    email.utils.formatdate(timeval=None, localtime=False, usegmt=True))
        resp.append("Server: (custom)\r\nContent-Type: text/html\r\n\r\n%s" % (data))
        return "".join(resp)

    def start(self):
        serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.logger.info("Starting server on %s:%d" % (self.listen_addr, self.port))
            serversocket.bind((self.listen_addr, self.port))
        except Exception as err:
            self.logger.error("Error binding to %s:%d : %s" %
                              (self.listen_addr, self.port, str(err)))
            return None
        serversocket.listen(115)
        threads = []
        for _ in range(self.thread_count):
            threads.append(self.Worker(self.inputq, self._comms))
        while self.server_running:
            d = {}
            try:
                (d['socket'], address) = serversocket.accept()
                d['clientip'] = address[0]
                self.logger.debug("Accepted connection from: %s" % d['clientip'])
                self.inputq.put(d)
            except socket.error as (code, msg):
                if code != errno.EINTR:
                    self.logger.warning(msg)
                    raise
        self.logger.info("Webserver exiting")

    def stop(self):
        d = {}
        d['socket'] = '_END'
        self.logger.info("Shutting down")
        for _ in range(self.thread_count):
            self.inputq.put(d)
        self.server_running = False

    def add_capability(self, newfunc, **kwargs):
        params = kwargs
        params['function_ref'] = newfunc
        self.response_functions[newfunc.func_name] = params
