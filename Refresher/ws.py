if __name__ != '__main__':
	import sublime, sublime_plugin
import threading, time, socket

class Thread(threading.Thread):
	"""Thread with 'on_stop' callback, which is either a callable constructor param or a class method (param overrides method)"""
	def __init__(self, on_stop=None, **kw):
		super(Thread, self).__init__(**kw)
		if on_stop and hasattr(on_stop, '__call__'): self.on_stop = on_stop

	def __stop(self):
		if hasattr(self, 'on_stop') and self.on_stop: self.on_stop(*([] if hasattr(self.on_stop, 'im_self') else [self]))
		super(Thread, self).__stop()

	@staticmethod
	def debug(name='   ', *message):
		print '[%s %s]  %s' % (time.strftime('%H:%M') if time else '-----', name, ' '.join(map(str, message)))

class Server(Thread):
	default_host = 'localhost'
	default_port = 9007

	def __init__(self, host='', port='', debug=1, **kw):
		super(Server, self).__init__()
		self.address = (host or Server.default_host, port or Server.default_port)
		self.socket = None
		self._clients = []
		self.test_mode = debug
		self.conn_type = 'S  '

	@staticmethod
	def run_server(**kw):
		server = Server(**kw)
		server.start()
		return server

	@staticmethod
	def test():
		server = Server.run_server(debug=1)
		sublime.set_timeout(server.test_client, 500)

	def test_client(self):
		Client((socket.socket(), self.address), server=self).start()

	def debug(self, *message):
		Thread.debug('%s %5d' % (self.conn_type, self.address[1:2][0]), *message)

	def run(self):
		try:
			self.debug('-' * 80)
			self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.socket.settimeout(5)
			self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			self.socket.bind(self.address)
			self.debug('listening on %s #%s' % (self.address, self.socket.fileno()))
			self.socket.listen(1)
			while 1:
				self.add_client(self.socket.accept())
				if self.test_mode:
					time.sleep(10)
					self.stop('ending test mode')
					break
		except socket.error as error:
			self.stop(error)

	def __del__(self): self.stop()
	def on_stop(self): self.stop()

	def stop(self, reason=None):
		if not self.socket: return
		[x.on_stop() for x in self._clients]
		self.socket.close()
		self.debug('stopping%s' % (' (%s)' % str(reason) if reason else ''))
		self.socket = None

	def add_client(self, addr):
		# order matters: client has to sit in the list first, before starting
		client = Handler(addr, server=self)
		self._clients.append(client)
		client.start()
		client.socket.sendall('welcome!')

	def clients(self, filename=''):
		return [x for x in self._clients if x and x.is_alive()]

class Connection(Thread):
	init_vars = {'server': '', 'conn_type': ' - ', 'delay': 1, 'max_idle': 60, 'idling': 0, 'keep_alive': 3}

	def __init__(self, addr, **kw):
		self.socket, self.address = addr
		[self.__setattr__(k, kw.pop(k, v)) for k, v in Connection.init_vars.iteritems()]
		super(Connection, self).__init__(**kw)

	def debug(self, *message):
		Thread.debug('%s %5d' % (self.conn_type, self.address[1:2][0]), *message)

	def run(self):
		def make_loops():
			self.idling = time.time()
			while time.time() - self.idling < self.max_idle:
				self.debug('idle since %.1fsec' % (time.time() - self.idling))
				if self.loop(): self.idling = time.time()
				time.sleep(self.delay)
		try:
			if self.on_open(): return
			self.debug('opened')
			if self._Thread__target: return super(Client, self).run()
			while 1:
				make_loops()
				if self.keep_alive <= 0 or not self.on_idling(): break
				self.keep_alive -= 1
				self.debug('idling, but kept alive (%d remaining)' % self.keep_alive)
			self.debug('idled out')
		except socket.error as error:
			self.debug(error)

	def loop(self): pass

	def close(self):
		if not self.socket: return
		self.debug('closing')
		self.socket.close()
		self.on_close()
		self.socket = None

	def on_stop(self): self.close()
	def on_open(self): pass
	def on_close(self): pass
	def on_idling(self): pass

class Handler(Connection):
	def __init__(self, addr, **kw):
		super(Handler, self).__init__(addr, **kw)
		self.conn_type = ' H '
		self.socket.settimeout(0.1)
		self.max_idle = 3

	def loop(self):
		data = ''
		try:
			data = self.socket.recv(1024)
			self.debug("incoming: '%s', %s" % (data, type(data)))
			data = ''
		except Exception as e:
			self.debug("no incoming data yet")
		return len(data)

	def on_idling(self):
		return self.socket.send('\n') == None

class Client(Connection):
	def __init__(self, addr, send='', get=None, **kw):
		super(Client, self).__init__(addr, **kw)
		self.conn_type = '  C'
		self.socket.settimeout(0.1)
		self.max_idle = 3
		self.send = send# or 'hello'
		self.get = get

	def on_open(self):
		self.socket.connect(self.address)
		self.address = self.socket.getsockname()
		if self.send:
			try:
				self.debug("sending '%s'" % self.send)
				if self.socket.sendall(self.send) is not None: self.debug('sending failed')
			except socket.error as error:
				self.debug("sending error:", error)
		if self.get:
			try:
				response = self.socket.recv(1024)
				self.debug("received '%s', %s" % (response, type(response)))
			except socket.error as error:
				self.debug('receive error:', error)

	def loop(self):
		return 0

if __name__ == '__main__':
	Server.run_server()
else:
	Server.test()
