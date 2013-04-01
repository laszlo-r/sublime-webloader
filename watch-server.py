import tornado.ioloop
import tornado.web
import tornado.websocket

class PluginHandler(tornado.web.RequestHandler):
	"""Handles the connection for the less-watch sublime plugin."""
	def __init__(self, application, request, **kw):
		super(PluginHandler, self).__init__(application, request)
		self.wshandler = None

	def post(self, *args, **kw):
		"""Handles requests from the sublime plugin, sends back file list, forwards to the websocket client"""
		handler = self.wshandler
		self.wshandler = self.application.websocket_handler
		if not self.wshandler: return self.write('No websocket connections yet (watch the javascript console, and refresh the page).')
		# new websocket handler? send its filelist to the plugin
		if self.wshandler and handler != self.wshandler:
			self.write(unicode(self.wshandler.files))
		# otherwise forward the message from the plugin to the websocket client
		if self.request.body:
			self.wshandler.write_message(self.request.body)

class WebSocketHandler(tornado.websocket.WebSocketHandler):
	"""Handles the connection for the websocket client, and stores the files to watch"""
	def __init__(self, application, request, **kw):
		super(WebSocketHandler, self).__init__(application, request)
		self.files = {}

	def client_host(self, request):
		return request.arguments.get('client', [request.headers.get('Origin', 'Unknown host')])[0]

	def open(self): print "%s   opens websocket" % self.client_host(self.request)
	def on_close(self): print "%s   closes websocket" % self.client_host(self.request)

	def on_message(self, message):
		"""Expects a file list (string with linebreaks, except first line), and stores them for the plugin"""
		files = message.split('\n')[1:]
		self.files.update(dict.fromkeys(files, 1))
		print "%s   new files to watch: %s" % (self.client_host(self.request), ', '.join(files))
		# remove the reference in the pluginhandler to signal new files
		if self.application.plugin_handler: self.application.plugin_handler.wshandler = None

class WatchApp(tornado.web.Application):
	"""Main app for the http server; stores references to the PluginHandler and WebSocketHandler instances"""
	def __init__(self, *args, **kw):
		super(WatchApp, self).__init__(*args, **kw)
		self.plugin_handler = None
		self.websocket_handler = None

	def __call__(self, request):
		handler = super(WatchApp, self).__call__(request)
		# store references to handlers, refreshing old ones
		if type(handler) == WebSocketHandler: self.websocket_handler = handler
		if type(handler) == PluginHandler: self.plugin_handler = handler
		return handler

def start_tornado():
	application = WatchApp([
		(r"/less_watch", PluginHandler),
		(r"/less_updates", WebSocketHandler),
	])

	print "Started local Tornado server, waiting for connections."
	application.listen(9000)
	tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
	start_tornado()
