import threading, time, socket
import struct
import BaseHTTPServer, SocketServer
from functools import partial
from contextlib import contextmanager
from base64 import b64encode
from hashlib import sha1


@contextmanager
def ignored(*exceptions):
	try: yield
	except exceptions: pass

def log_fallback(self, *args):
	print '%s  %s' % (self, ' '.join(map(str, args)))


class Server(SocketServer.ThreadingTCPServer):

	def __init__(self, server_address, requesthandler, log=None, debug=0):
		# SocketServer.ThreadingMixin does not inherit object, so no super()
		self.allow_reuse_address = True
		SocketServer.ThreadingTCPServer.__init__(self, server_address, requesthandler)
		self.test_mode = debug
		self._clients = []
		self.log = partial(log or log_fallback, self)

	def start(self):
		self.thread = threading.Thread(target=self.serve_forever)
		self.thread.start()
		return self

	def process_request(self, request, client_address):
		# starts finish_request(req, addr) and shutdown_request(req) in a thread
		SocketServer.ThreadingTCPServer.process_request(self, request, client_address)
		if not self.test_mode: return
		self.test_mode -= 1
		if self.test_mode > 0: return
		self.log('ending test mode, %d clients active' % len(self.clients))
		self.shutdown()

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

	@property
	def running(self):
		return self._BaseServer__serving and not self._BaseServer__is_shut_down.is_set()

	@property
	def clients(self, filename=''):
		return [x for x in self._clients if x and x.running]

	def remove_client(self, client):
		if client.running: self._clients.remove(client)

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

	@for_each_client
	def broadcast(self, client, message):
		self.log('broadcasting to', client, message)
		return client.send(message)


class WebSocketHandler(BaseHTTPServer.BaseHTTPRequestHandler):
	# websocket recipe from on https://gist.github.com/jkp/3136208
	magic = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

	def setup(self):
		# no super, as BaseRequestHandler does not inherit object
		BaseHTTPServer.BaseHTTPRequestHandler.setup(self)
		if hasattr(self, 'handshake_done') and self.handshake_done: return
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


class Client(WebSocketHandler):

	def setup(self):
		WebSocketHandler.setup(self)
		self.running = False
		self.connection.settimeout(1)
		self.handshake_timeout = time.time() + 5 # stop if no data after handshake
		self.lock_read = threading.RLock()
		self.lock_send = threading.RLock()
		self.server._clients.append(self)

		log = log_fallback
		if self.server.log:
			if isinstance(self.server.log, partial): log = self.server.log.func
			elif hasattr(self.server.log, 'im_func'): log = self.server.log.im_func
		self.log = partial(log, self)

	def handle(self):
		if self.handshake_done: self.running = True
		while self.running and self.read(): pass

	def finish(self, reason=''):
		if self.running == None: return self.running
		self.server.remove_client(self)
		self.running = None
		WebSocketHandler.finish(self)
		if self.connection: self.connection.close()
		self.log('-', 'client stopped' + ((' (%s)' % reason) if reason else ''))
		return self.running

	def read(self):
		with self.server.locked(self.lock_read):
			message = self.read_message() # string or None (timeout)
		if not (self.server and self.server.running): return self.finish('server closed')
		if message == '': return self.finish('remote closed')
		if self.handshake_timeout:
			if message: self.handshake_timeout = 0
			elif self.handshake_timeout < time.time():
				return self.finish('timeout after handshake')
		if message == None: return True # read timeout, continue reading
		return self.on_read(message) and len(message)

	def send(self, message):
		message = self.on_send(message)
		with self.server.locked(self.lock_send):
			return self.send_message(message)

	def on_read(self, message): return len(message)
	def on_send(self, message): return message


if __name__ == '__main__':
	Server(('localhost', 9000), Client, debug=2).start()
