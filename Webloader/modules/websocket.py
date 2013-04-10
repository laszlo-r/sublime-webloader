
import threading, time, socket
import struct
import BaseHTTPServer
from functools import partial
from contextlib import contextmanager
from base64 import b64encode
from hashlib import sha1

# ---------------------------------------------------------
import select
# ---------------------------------------------------------
# should follow the same api as the SocketServer.BaseServer
# ---------------------------------------------------------


@contextmanager
def ignored(*exceptions):
	try: yield
	except exceptions: pass


class Thread(threading.Thread):
	"""Thread with more callbacks, which are either a callable or a defined method (param takes precedence)"""
	def __init__(self, on_start=None, on_stop=None, **kw):
		super(Thread, self).__init__(**kw)
		if on_start and hasattr(on_start, '__call__'): self.on_start = on_start
		if on_stop and hasattr(on_stop, '__call__'): self.on_stop = on_stop

	def start(self):
		if hasattr(self, 'on_start') and self.on_start: self.on_start(*([] if hasattr(self.on_start, 'im_self') else [self]))
		super(Thread, self).start()

	def __stop(self):
		if hasattr(self, 'on_stop') and self.on_stop: self.on_stop(*([] if hasattr(self.on_stop, 'im_self') else [self]))
		super(Thread, self).__stop()


class Server(Thread):
	default_address = ('localhost', 9000)

	def __init__(self, address=None, handler=None, log=None, debug=0, **kw):
		super(Server, self).__init__()
		self.address = address or Server.default_address
		self.handler_class = handler or Client
		self.socket = False
		self.running = False # means initializing
		self.test_mode = debug
		self._clients = []
		if not log:
			def log(*x): print x
		self.log = partial(log, self) if log else lambda *x: None

	def start(self):
		return super(Server, self).start() or self

	def run(self):
		try:
			self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.socket.settimeout(5)
			self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			self.socket.bind(self.address)
			self.socket.listen(1)
			self.on_run()
			# if other threads called stop(), making it None, don't change it
			if self.running == False: self.running = True
			while self.running:
				try:
					self.add_client(self.socket.accept())
				except socket.timeout:
					if not self.running: break
				else:
					if not self.test_mode: continue
					self.test_mode -= 1
					if self.test_mode > 0: continue
					time.sleep(1)
					self.stop('ending test mode, waiting for %d client to close' % len(self.clients))
					break
		except Exception as e:
			self.stop(e)
		finally:
			# close socket here, preventing socket errors by other threads closing it sooner
			self.socket.close()
			self.stop()

	def stop(self, reason=None):
		if self.running: self.running = None

	def __del__(self): self.stop()

	def on_start(self): pass
	def on_run(self): pass
	def on_stop(self): pass
	def on_message(self, client, message): pass

	def lock(self, name):
		name = 'lock_' + name
		if not hasattr(self, name): setattr(self, name, threading.RLock())
		return getattr(self, name)

	def set_lock(self, name): return self.lock(name).acquire()
	def release_lock(self, name): return self.lock(name).release()

	@contextmanager
	def locked(self, lock=None):
		if not lock: lock = threading.RLock()
		yield lock.acquire()
		lock.release()

	def for_each_client(self, method=None, *args, **kw):
		# when decorating, called with a single function argument
		if method is None: method, self = self, None
		match = kw.pop('match', None)
		def f(self, *fargs, **fkw):
			# if not bound, bind the server as first argument
			m = method if hasattr(method, 'im_self') else partial(method, self)
			# decorated methods send arguments via fargs, normal calls send via args
			a = args or fargs
			k = kw or fkw
			# clients could modify any args
			called = '%s(%s, %s) =' % (method.__name__, a, k)
			res = [m(x, *a, **k) for x in self.clients if not match or match(x)]
			self.log('@', called, res)
			return res
		return f(self) if self else f

	@property
	def clients(self, filename=''):
		return [x for x in self._clients if x and x.running and x.is_alive()]

	def add_client(self, addr):
		client = self.handler_class(addr[0], addr[1], server=self)
		self._clients.append(client)
		client.start()

	def remove_client(self, client):
		if client.running: self._clients.remove(client)

	@for_each_client
	def broadcast(self, client, message):
		self.log('broadcasting to', client, message)
		return client.send(message)


class WebSocketHandler(BaseHTTPServer.BaseHTTPRequestHandler):
	# websocket recipe from on https://gist.github.com/jkp/3136208
	magic = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

	def handle(self):

		# sample websocket request:

		# GET /some/path/ HTTP/1.1
		# Upgrade: websocket
		# Connection: Upgrade
		# Host: localhost:9000
		# Origin: http://localhost
		# Pragma: no-cache
		# Cache-Control: no-cache
		# Sec-WebSocket-Key: YGbMI5TKfyADYxqqy0w4LQ==
		# Sec-WebSocket-Version: 13
		# Sec-WebSocket-Extensions: x-webkit-deflate-frame
		# User-Agent: Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.15 Safari/537.36
		# Cookie: PHPSESSID=nl2sbe2ga5rtkn5i0obq97cdm3

		# some vars from BaseHTTPRequestHandler:
		# self.error_code
		# self.command # GET
		# self.path
		# self.headers.get('Origin')

		if self.handshake_done: return self.handshake_done

		self.raw_requestline = self.rfile.readline()
		self.error_code = self.error_message = None
		self.parse_request()
		if not hasattr(self, 'headers') or self.headers.get("Upgrade", None) != "websocket": return

		key = self.headers['Sec-WebSocket-Key']
		digest = b64encode(sha1(key + self.magic).hexdigest().decode('hex'))
		response = 'HTTP/1.1 101 Switching Protocols\r\n' + \
			'Upgrade: websocket\r\n' + \
			'Connection: Upgrade\r\n' + \
			'Sec-WebSocket-Accept: %s\r\n\r\n' % digest
		self.handshake_done = self.request.send(response)

	# see page 27 at http://tools.ietf.org/html/rfc6455
	# reading steps:
	#	read opcode(8bit) + payload length(8bit)
	#	opcode: 1 bit if final message fragment; 3 bit for extensions (must be 0 by default)
	#	payload length: mask flag (8th bit, always 1) + length (7 bit)
	#	if length == 126, read 16 bits, if 127, read 64 bits
	#	read 4 byte mask for decoding
	#	read payload and decode it char-by-char
	# sending steps:
	#	send an opcode (8th: final message, 1th: text frame)
	#	send length as a single byte, or 126 + 2-byte, or 127 + 8-byte

	def read_message(self, debug=0):
		# log = [lambda *x: 1, self.log][debug]
		length = None
		with ignored(socket.timeout): length = self.rfile.read(2)
		if length is None: return None
		if not length or not self.running or not self.rfile or self.rfile.closed:
			# log('rfile: %s, aborting' % ('EOF' if not length else 'rfile closed'))
			return ''

		length = ord(length[1]) & 127
		if length == 126: length = struct.unpack(">H", self.rfile.read(2))[0]
		elif length == 127: length = struct.unpack(">Q", self.rfile.read(8))[0]
		masks = [ord(byte) for byte in self.rfile.read(4)]
		# log('rfile: length: %s, mask: %s' % (length, masks))

		decoded = ""
		for char in self.rfile.read(length):
			decoded += chr(ord(char) ^ masks[len(decoded) % 4])
		return decoded

	def send_message(self, message):
		self.request.send(chr(129))
		length = len(message)
		if length <= 125:
			self.request.send(chr(length))
		elif length >= 126 and length <= 65535:
			self.request.send(chr(126))
			self.request.send(struct.pack(">H", length))
		else:
			self.request.send(chr(127))
			self.request.send(struct.pack(">Q", length))
		return self.request.send(message)


class Client(Thread, WebSocketHandler):

	# BaseRequestHandler: setup, handle, finish; request, client_address, server
	# StreamRequestHandler: self.connection == self.request (the socket), rfile/wfile (file-likes)

	def __init__(self, request, address, server, timeout=1, log=None):
		Thread.__init__(self)
		request.settimeout(timeout)
		self.handshake_done = False
		self.handshake_timeout = time.time() + 5 # stop if handshake is not finished
		self.running = False
		self.lock_read = threading.RLock()
		self.lock_send = threading.RLock()
		# does the handshake, sets self.headers, self.path (among several others)
		WebSocketHandler.__init__(self, request, address, server)

		if not log:
			if self.server.log:
				if isinstance(self.server.log, partial): log = self.server.log.func
				elif hasattr(server.log, 'im_func'): log = self.server.log.im_func
			else:
				def log(*x): print x
		self.log = partial(log, self)

	# BaseHTTPRequestHandler would call this in __init__, ignore it
	def finish(self): pass

	def run(self):
		if self.handshake_done: self.running = True
		self.on_run()
		try:
			while self.running and self.read(): pass
		finally:
			self.stop()

	def read(self):
		with self.server.locked(self.lock_read):
			message = self.read_message() # string or None (timeout)
		if not self.server.running: return self.stop('server closed')
		if message == '': return self.stop('remote closed')
		if self.handshake_timeout:
			if message: self.handshake_timeout = 0
			elif self.handshake_timeout < time.time():
				return self.stop('timeout after handshake')
		if message == None: return True # read timeout, continue reading
		# continue reading if on_read(), or any message
		# this can return very uninformative exceptions
		try: return self.on_read(message) or len(message)
		except Exception as e: return self.stop(repr(e))

	def send(self, message):
		self.on_send(message)
		with self.server.locked(self.lock_send):
			return self.send_message(message)

	# called after run(); on_stop is called as the thread exits
	def stop(self, reason=''):
		if self.running == None: return self.running
		self.running = None
		self.server.remove_client(self)
		# if reason: self.send('closed_connection\n\n%s' % reason)
		if not self.rfile.closed: super(Client, self).finish()
		if self.connection: self.connection.close()
		return self.running

	def on_start(self): pass
	def on_run(self): pass
	def on_stop(self): pass
	def on_read(self, message): pass
	def on_send(self, message): pass


if __name__ == '__main__':
	Server(debug=3).start()
