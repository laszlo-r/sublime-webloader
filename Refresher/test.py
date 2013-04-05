import sublime, sublime_plugin
import threading, time, contextlib, httplib
import modules



class RunJsCommand(sublime_plugin.WindowCommand):
# class RunJsCommand(sublime_plugin.ApplicationCommand):
# class TestCommand(sublime_plugin.TextCommand):
# class TestCommand():
	# def __init__(self, view):
	# 	super(TestCommand, self).__init__(view)
		# self.thread = None
	def __init__(self, window):
		super(RunJsCommand, self).__init__(window)
		self.prev = ''
	def on_done(self, js):
		self.prev = js
		print "Running js command: '%s'" % js
		sublime.status_message("Running js command: '%s'" % js)
		self.window.show_input_panel('Run javascript', self.prev, self.on_done, None, None)
	def run(self, **args):
		# look at the current file, find the attached client, and run the js there
		# if more clients, show_quick_panel with clients, user selects a target (store it)
		#   run commands on that client, until user cancels the dialog, reset stored client

		# self.window.run_command('show_panel', {'panel': 'console', 'xtoggle': True})

		self.window.show_input_panel('Run javascript', self.prev, self.on_done, None, None)

		# def on_done(index):
		# 	sublime.status_message('Selected item %d' % index)
		# items = ['run on item1', ['item2', 'item2 line 2']]
		# self.window.show_quick_panel(items, on_done)

		return

		if self.thread:
			if self.thread.is_alive():
				print "daemon thread still running"
				return
			result = self.thread.result
			print 'thread finished with result:', result
			self.thread = None
		else:
			self.thread = Thread(self)
			self.thread.daemon = True
			print 'starting daemon thread', self.thread
			self.thread.start()

class Thread(threading.Thread):
	def __init__(self, command):
		threading.Thread.__init__(self)
		self.command = command
		self.result = None
	def run(self):
		stopat = time.time() + 10
		while time.time() < stopat:
			print 'running in thread', self, self.command, time.time()
			time.sleep(3)
		print 'finished running'
		self.result = time.time()

def start_server():
	import socket
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.bind(("", 9999))
	sock.listen(5)

	handshake = '\
	HTTP/1.1 101 Web Socket Protocol Handshake\r\n\
	Upgrade: WebSocket\r\n\
	Connection: Upgrade\r\n\
	WebSocket-Origin: http://localhost:8888\r\n\
	WebSocket-Location: ws://localhost:9999/\r\n\r\n\
	'
	handshaken = False
	print "TCPServer Waiting for client on port 9999"

	data = ''
	header = ''

	client, address = sock.accept()
	while True:
		if handshaken == False:
			header += client.recv(16)
			if header.find('\r\n\r\n') != -1:
				data = header.split('\r\n\r\n', 1)[1]
				handshaken = True
				client.send(handshake)
		else:
			tmp = client.recv(128)
			data += tmp;

			validated = []

			msgs = data.split('\xff')
			data = msgs.pop()

			for msg in msgs:
				if msg[0] == '\x00':
					validated.append(msg[1:])

			for v in validated:
				print v
				client.send('\x00' + v + '\xff')





class HTTPMessage(object):
	"""Wraps httplib.HTTPConnection, sends plain text messages, returns HTTPResponse or httplib.HTTPResponse."""

	def __init__(self, host='', port='', url='', timeout=0, debug=None):
		self.host, self.port, self.url, self.timeout = host, port, url, timeout
		self.headers = {'Content-type': 'text/plain', 'Accept': 'text/plain'}
		self.debug = debug

	def debug(self, message, **kw):
		print message

	@contextlib.contextmanager
	def _http_connection(self, host):
		try:
			# self.debug('%s %s %s' % (self.host, self.port, self.timeout))
			conn = httplib.HTTPConnection(self.host, self.port, timeout=self.timeout)
			yield conn
		finally:
			conn.close()

	def send(self, message, debug=None):
		"""Sends a plain text message via a one-time httplib.HTTPConnection."""

		if debug is None: debug = self.debug
		with self._http_connection(self.host) as conn:
			if message and debug: self.debug("sending message: %s ..." % message.replace('\n', '\\n'))
			# try sending, if not successful, mock a http response with the exception
			try:
				conn.request('POST', self.url, message, self.headers)
				response = conn.getresponse()
			except Exception, e:
				response = HTTPResponse(reason='Cannot connect to the server: %s' % e)
			body = response.read()
			# non-standard responses should be seen
			if response.status != 200 and debug:
				self.debug("got response: %d %s, %d bytes" % (response.status, response.reason, response.length))
				if response.length: self.debug(body)
			return response, body

class HTTPResponse(object):
	"""A blank http response, returned by HTTPMessage.send() if there were errors with the connection."""

	def __init__(self, status=0, reason='', length=0, body=''):
		self.status = status
		self.reason = reason
		self.length = length
	def read(self):
		return ''
