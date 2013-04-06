
# ---------------------------------------------------------
# ---------------------------------------------------------
# should follow the same api as the SocketServer.BaseServer
# ---------------------------------------------------------
# ---------------------------------------------------------

import threading, time, socket
import struct
import SocketServer, mimetools
from functools import partial
from contextlib import contextmanager
from base64 import b64encode
from hashlib import sha1
from StringIO import StringIO


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


class Common(object):
	debug_lock = threading.RLock()
	def log(self, *message):
		ident = '?'
		if hasattr(self, 'client_address'): ident = '%-15s %-5d' % self.client_address
		elif hasattr(self, 'address'): ident = 'Server'
		sign = len(message) > 1 and isinstance(message[0], str) and len(message[0]) == 1
		now = time.strftime('%X') if time else '--------'
		# locks for timeout-related client output?
		# Common.debug_lock.acquire()
		message = '%s  %-21s %s%s' % (now, ident, ['| ', ''][sign], ' '.join(map(str, message)))
		logfile = 'server.log'
		with open(logfile, 'a') as f: f.write(message + '\n')
		# print message
		# Common.debug_lock.release()


class WebSocketMixin(object):
	# websocket recipe from on https://gist.github.com/jkp/3136208
	magic = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

	def handshake(self):
		if hasattr(self, 'handshake_done'): return self.handshake_done
		self.handshake_done = False
		data = self.request.recv(1024).strip()
		headers = mimetools.Message(StringIO(data.split('\r\n', 1)[1]))
		if headers.get("Upgrade", None) != "websocket": return

		key = headers['Sec-WebSocket-Key']
		digest = b64encode(sha1(key + self.magic).hexdigest().decode('hex'))
		response = 'HTTP/1.1 101 Switching Protocols\r\n'
		response += 'Upgrade: websocket\r\n'
		response += 'Connection: Upgrade\r\n'
		response += 'Sec-WebSocket-Accept: %s\r\n\r\n' % digest
		self.handshake_done = self.request.send(response)
		return self.handshake_done

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

	def read_message(self, debug=1):
		log = [lambda: 1, self.log][debug]
		length = None
		with ignored(socket.timeout): length = self.rfile.read(2)
		if length is None: return None
		if not length or not self.running or not self.rfile or self.rfile.closed:
			log('rfile: %s, aborting' % ('EOF' if not length else 'rfile closed'))
			return ''

		length = ord(length[1]) & 127
		if length == 126: length = struct.unpack(">H", self.rfile.read(2))[0]
		elif length == 127: length = struct.unpack(">Q", self.rfile.read(8))[0]
		masks = [ord(byte) for byte in self.rfile.read(4)]
		log('rfile: length: %s, mask: %s' % (length, masks))

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
			self.request.send(126)
			self.request.send(struct.pack(">H", length))
		else:
			self.request.send(127)
			self.request.send(struct.pack(">Q", length))
		return self.request.send(message)


class Server(Thread, Common):
	default_address = ('localhost', 9000)

	def __init__(self, address=None, debug=0, **kw):
		super(Server, self).__init__()
		self.address = address or Server.default_address
		self.socket = None
		self.test_mode = debug
		self._clients = []

	def start(self):
		return super(Server, self).start() or self

	def run(self):
		try:
			self.log('-' * 80)
			self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			self.socket.bind(self.address)
			self.log('listening on %s #%s%s' % (self.address, self.socket.fileno(), \
				self.test_mode and ' in test mode (stopping after %d clients)' % self.test_mode or ''))
			self.socket.listen(1)
			while 1:
				self.add_client(self.socket.accept())
				if self.test_mode:
					self.test_mode -= 1
					if self.test_mode > 0: continue
					time.sleep(2)
					self.stop('ending test mode, waiting for %d client to close' % len(self.clients))
					break
		except socket.error as error:
			self.stop(error)

	def stop(self, reason=None):
		if not self.socket: return
		self.for_each_client(self.stop_client, 'server stopping')
		self.log('=', 'stopping%s' % (' (%s)' % str(reason) if reason else ''))
		self.socket.close()
		self.socket = None

	def __del__(self): self.stop()
	def on_stop(self):
		self.log('server thread stopped')
		self.stop()

	def on_message(self, client, message):
		pass

	@contextmanager
	def lock(self, lock):
		lock = 'lock_' + lock
		if not hasattr(self, lock): setattr(self, lock, threading.RLock())
		yield getattr(self, lock).acquire()
		getattr(self, lock).release()

	@property
	def clients(self, filename=''):
		return [x for x in self._clients if x and x.is_alive()]

	def add_client(self, addr):
		client = Client(addr[0], addr[1], server=self)
		# self.broadcast('a new client arrived: %s' % client)
		self._clients.append(client)
		client.start()

	def remove_client(self, client):
		if client.running: self._clients.remove(client)

	def stop_client(self, client, reason=None):
		return client.stop(reason)

	def for_each_client(self, method=None, *fargs, **fkw):
		if method is None: method, self = self, None
		def f(self, *args, **kw):
			# with self.lock('debug'):
			callback = method if hasattr(method, 'im_self') else partial(method, self)
			res = [callback(x, *args, **kw) for x in self.clients]
			self.log('@', '%s for each client:' % method.__name__, res)
			return res
		return f(self, *fargs, **fkw) if self else f

	@for_each_client
	def broadcast(self, client, message):
		self.log('broadcasting to', client, message)
		return client.send(message)


class Client(Thread, SocketServer.StreamRequestHandler, WebSocketMixin, Common):

	# BaseRequestHandler: setup, handle, finish; request, client_address, server
	# StreamRequestHandler: self.connection == self.request (the socket), rfile/wfile (file-likes)

	def __init__(self, request, address, server):
		Thread.__init__(self)
		request.settimeout(5)
		SocketServer.StreamRequestHandler.__init__(self, request, address, server)
		self.handshake()
		self.log('+', 'handshake: %s' % self.handshake_done)
		self.running = 1

	def handle(self): pass
	def finish(self): pass

	def run(self):
		try:
			while self.running and self.read(): pass
		finally:
			self.stop()

	def read(self):
		message = self.read_message() # string or None (timeout)
		if message:
			self.log("<", "'%s' (%d)" % (message.replace('\n', '\\n')[0:80], len(message)))
			self.on_read(message)
			self.server.on_message(self, message)
		return message is None or len(message)

	def send(self, message):
		self.log(">", "'%s' (%d)" % (message.replace('\n', '\\n')[0:80], len(message)))
		self.on_send(message)
		return self.send_message(message)

	def stop(self, reason=''):
		if not self.running: return self.running
		self.running = 0
		self.server.remove_client(self)
		if reason: self.send('closed_connection\n\n%s' % reason)
		if not self.rfile.closed: super(Client, self).finish()
		self.log('-', 'stopped client')
		return self.running

	def on_stop(self): self.log('client thread stopped')
	def on_send(self, message): pass
	def on_read(self, message): pass


if __name__ == '__main__':
	Server(debug=1).start()

