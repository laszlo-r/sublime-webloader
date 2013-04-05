import threading, time
import ws

class Server(threading.Thread, ws.WebSocketServer):
	def __init__(self, plugin=None, **kw):
		super(threading.Thread, self).__init__()
		super(ws.WebSocketServer, self).__init__(**kw)
		self.plugin = plugin
		self.update_files = 0

	def run(self):
		if not self.plugin: return self.debug('Refresher plugin not found, stopping server.')
		stop_at = time.time() + 10
		while time.time() < stop_at:
			time.sleep(1)
		self.debug('Stopping server.')

	def active_clients(self, filename=''):
		return [x for x in self.clients if x and x.live and len(x.files) and (not filename or x.files.get(filename))]

	def file_event(self, message):
		filename, update = (message.split('\n', 1) + [''])[0:2]
		if not filename or not update: return

		clients = self.active_clients(filename)
		self.debug('updating %s with "%s"' % (', '.join(clients), message.replace('\n', '\\n', 1)[0:60]), 2)
		[x.write(message) for x in clients]

	def new_files(self, status=None, as_text=None):

		if status is not None:
			self.update_files = int(status)
			return
		if as_text is None: return self.update_files
		self.update_files = 0
		files = self.watchlist(as_text=as_text)
		self.debug('currently watching: ' + files.replace('\n', ', '), 2)
		return files

	def watchlist(self, as_text=0):
		files = {}
		[files.update(handler.files) for client_id, handler in self.active_handlers.iteritems() if handler]
		if as_text: return unicode('\n'.join(files))
		return files



class PluginHandler(object):
	"""Handles the connection for the less-watch sublime plugin."""

	def __init__(self, application, request, **kw):
		super(PluginHandler, self).__init__(application, request)
		self.files = {}

	def client_id(self): return 'sublime-plugin'

	def post(self, *args, **kw):
		"""Handles requests from the sublime plugin, which are either updates, commands, or filelist requests (empty request)"""
		if self.request.body:
			self.application.forward_update(self.request.body)
		if not self.request.body or self.application.new_files():
			self.write(self.application.new_files(as_text=1))

class WebSocketHandler(object):
	"""Handles the connection for the websocket client, and stores which files to watch."""

	def __init__(self, application, request, **kw):
		super(WebSocketHandler, self).__init__(application, request)
		self.files = {}

	def client_id(self): return self.request.arguments.get('client', [self.request.headers.get('Origin', None)])[0]
	def open(self): self.application.debug("%s   opens websocket" % self.client_id(), 2)
	def on_close(self): self.application.debug("%s   closes websocket" % self.client_id(), 2)

	def on_finish(self): print 'on_finish in websockethandler'

	def on_message(self, message):
		"""Expects a file list (string with linebreaks, except first line), and stores them for the plugin."""
		files = message.split('\n')[1:]
		self.files.update(dict.fromkeys(files, 1))
		self.application.new_files(1)
		self.application.debug("%s   asks to watch: %s" % (self.client_id(), ', '.join(files)))
