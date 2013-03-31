import tornado.ioloop
import tornado.web
import tornado.websocket

class PluginHandler(tornado.web.RequestHandler):
	def __init__(self, application, request, **kw):
		super(PluginHandler, self).__init__(application, request)

	# def get(self):
	# 	self.write("Hello, world")

	def post(self, *args, **kw):
		# self.write("You posted: %s, %s" % (args, kw))
		# self.write(repr(self.request))
		handler = self.application.websocket_handler
		if not handler:
			return self.write('No websocket connections yet (refresh the page, and check the javascript console for messages).')
		# print 'websocket_handler:', handler
		handler.write_message(self.request.body)

class WebSocketHandler(tornado.websocket.WebSocketHandler):
	# def forward(self, message):
	# 	self.write_message(message)

	def open(self):
		print "WebSocket opened"

	def on_message(self, message):
		self.write_message(u"this just in: " + message)

	def on_close(self):
		print "WebSocket closed"

class WatchApp(tornado.web.Application):
	def __init__(self, *args, **kw):
		super(WatchApp, self).__init__(*args, **kw)
		self.websocket_handler = None

	def __call__(self, request):
		# print "the request in app:", request
		handler = super(WatchApp, self).__call__(request)
		if self.is_websocket_request(request): self.websocket_handler = handler
		# print "the handler from app.__call__:", handler
		return handler

	def is_websocket_request(self, request):
		handlers = self._get_host_handlers(request)
		matches = lambda x: x.regex.match(request.path) and x.handler_class == WebSocketHandler
		return next((x for x in handlers if matches(x)), None)

def start_tornado():
	application = WatchApp([
		(r"/less_watch", PluginHandler),
		(r"/less_updates", WebSocketHandler),
	])

	if __name__ == "__main__":
		application.listen(9000)
		tornado.ioloop.IOLoop.instance().start()

start_tornado()
