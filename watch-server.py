import tornado.ioloop
import tornado.web
import tornado.websocket
import sys, time

class WatchApp(tornado.web.Application):
	"""Main app for the http server; stores references to handlers instances and watched files"""

	def __init__(self, *args, **kw):
		super(WatchApp, self).__init__(*args, **kw)
		self.active_handlers = {}
		self.update_files = 0
		self.debug_level = 0

	def __call__(self, request):
		handler = super(WatchApp, self).__call__(request)
		self.active_handlers[handler.client_id()] = handler
		return handler

	def debug(self, message, level=1):
		if self.debug_level >= level:
			print '[%s]  %s' % (time.strftime('%H:%M'), message)

	def forward_update(self, message):
		filename, update = (message.split('\n', 1) + [''])[0:2]
		if not filename or not update: return

		handlers = {k: v for k, v in self.active_handlers.iteritems() if filename in v.files}
		self.debug('updating %s with "%s"' % (', '.join(handlers.keys()), message.replace('\n', '\\n', 1)[0:60]), 2)
		[v.write_message(message) for k, v in handlers.iteritems()]

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
		[files.update(handler.files) for client_id, handler in self.active_handlers.iteritems()]
		if as_text: return unicode('\n'.join(files))
		return files

class PluginHandler(tornado.web.RequestHandler):
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

class WebSocketHandler(tornado.websocket.WebSocketHandler):
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

def start_tornado(port=9000, debug_level=1):
	"""Starts up a WatchApp (tornado.web.Application) on localhost:9000."""

	application = WatchApp([
		(r"/less_watch", PluginHandler),
		(r"/less_updates", WebSocketHandler),
	], )

	application.listen(port)
	application.debug_level = debug_level
	application.debug("Started watch server on localhost:%d, waiting for connections. Ctrl-c or close window to stop." % port)
	tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
	kw = {}
	if sys.argv[1:] and sys.argv[1].isdigit(): kw['port'] = int(sys.argv[1])
	if sys.argv[2:] and sys.argv[2].isdigit(): kw['debug_level'] = int(sys.argv[2])

	start_tornado(**kw)
