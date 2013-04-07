import urlparse, json
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

	def on_message(self, client, message):
		self.plugin.message(client, message)

	def pack_message(self, message): return json.dumps(message, ensure_ascii=False)
	def unpack_message(self, message): return json.loads(message)


class Client(websocket.Client):
	"""Stores which files to watch, so there is less traffic when broadcasting events."""

	def __init__(self, *args, **kw):
		super(Client, self).__init__(*args, **kw)
		self.files = {}

		# clients should send their full page url (path is /?client=pageurl)
		url = urlparse.urlparse(self.path) # original url parts
		q = urlparse.parse_qs(url.query, True) # params
		url = urlparse.urlparse(q.get('client', [''])[0]) # pageurl
		self.page = url.netloc + url.path # empty if no client param
		self.log('+', 'page: %s' % self.page)

	def watches(self, filename):
		if not filename in self.files:
			self.files[filename] = next((x for x in self.files.iterkeys() if x.endswith(filename)), None)
		return self.files[filename]

	def on_read(self, message):
		message = self.server.unpack_message(message)
		# to update the server if needed:
		# self.server.on_message(message)
		cmd = message.get('cmd')
		content = message.get('content')
		if cmd == 'watch':
			if content and isinstance(content, list): self.files.update(dict.fromkeys(content))
		elif cmd == 'message':
			self.server.on_message(self, content)


if __name__ == '__main__':
	Server(debug=3).start()
