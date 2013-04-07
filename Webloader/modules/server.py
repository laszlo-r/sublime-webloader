import websocket

class Server(websocket.Server):

	def __init__(self, address=None, plugin=None, *args, **kw):
		if not kw.get('handler'): kw['handler'] = Client
		super(Server, self).__init__(address, *args, **kw)
		self.plugin = plugin

	def command(self, cmd, filename='', content=''):
		if not (cmd and len(cmd)): return False
		message = self.pack_message(cmd, filename, content)
		match = None if not filename else lambda x: x.watches(filename)
		return self.for_each_client(self.send_message, message, match=match)

	def send_message(self, client, message):
		client.send(message)

	# def on_message(self, client, message): pass

	# TODO: message class maybe
	def pack_message(self, *message): return '\n'.join(message[0:3])
	def unpack_message(self, message): return (message.split('\n', 2) + ['', ''])[0:3]


class Client(websocket.Client):
	"""Stores which files to watch, so there is less traffic when broadcasting events."""

	def __init__(self, *args, **kw):
		super(Client, self).__init__(*args, **kw)
		self.files = {}

	def watches(self, filename):
		if not filename in self.files:
			self.files[filename] = next((x for x in self.files.iterkeys() if x.endswith(filename)), None)
		return self.files[filename]

	def on_read(self, message):
		message = self.server.unpack_message(message)
		if message[0] == 'watch':
			self.files.update(dict.fromkeys(message[1].split('\n')))
		# to update the server if needed:
		# self.server.on_message(message)
