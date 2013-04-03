import tornado.ioloop
import tornado.web
import tornado.websocket
import sys, os, time, platform, contextlib, json

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


def warning(message):
	print message

def usage():
	return """
	LessWatcher server (based on Tornado)

	Usage:          python """ + __file__ + """ [sublime_path] [port] [debug_level]

	 sublime_path:  only necessary if the server can't find your sublime data directory
	 port:          any valid port number above 1024 which the server should use
	 debug_level:   set this higher if you want to see debug messages
	                0: silent; 1: only basic messages; 2: updates and requests
	"""

def start():
	if sys.argv[1:] and sys.argv[1].strip('-') in ['h', 'help', '?']:
		return warning(usage().replace('\t', ''))

	settings = load_settings()
	start_tornado(settings)

def load_settings():
	"""Loads and returns the merged package/user/script settings from the Sublime package directory."""

	class SimpleDict(dict):
		"""Dict with attribute access, credits to: http://stackoverflow.com/a/14620633/1393194"""
		def __init__(self, *args, **kw):
			super(SimpleDict, self).__init__(*args, **kw)
			self.__dict__ = self

	def readfile(f, as_json=1):
		try:
			with open(f, 'rU') as f:
				return f.read() if not as_json else json.loads(f.read() or '{}', object_hook=SimpleDict)
		except:
			return ['', {}][as_json]

	args = sys.argv[1:]
	script_settings = {}
	path = ''
	paths = readfile(__file__[0:-3] + '.json')

	if args and max(args[0].find(' '), args[0].find(os.sep)) > -1: script_settings['path'] = args.pop(0)
	if args and args[0].isdigit() and 0 <= int(args[0]) < 10: script_settings['debug_level'] = int(args.pop(0))
	if args and args[0].isdigit() and int(args[0]) > 1024: script_settings['port'] = int(args.pop(0))

	if 'path' in script_settings and os.path.exists(script_settings['path']): path = script_settings['path']

	if not path and platform.system() in paths['sublime_dir']:
		path = os.path.join(paths['sublime_dir'][platform.system()], paths['package_dir'])
		path = reduce(lambda path, key: path.replace('%' + key + '%', os.environ[key]), paths['replace'], path)

	if not os.path.exists(path):
		return warning("Can't find the Sublime Packages directory at '%s'. Please provide a correct path." % path)

	package_dir = os.path.join(path, paths['plugin_name'])
	user_dir = os.path.join(path, paths['user_dir'])
	settings_file = paths['plugin_name'] + paths['settings_ext']
	
	settings = readfile(os.path.join(package_dir, settings_file))
	user_settings = readfile(os.path.join(user_dir, settings_file))
	settings.update(user_settings, **script_settings)
	# print json.dumps(settings, indent=2, sort_keys=True)

	return settings

def start_tornado(settings):
	"""Starts up a WatchApp (tornado.web.Application) on localhost:9000."""

	# print json.dumps(settings, indent=4, sort_keys=1)

	application = WatchApp([
		('/' + settings.urls.plugin, PluginHandler),
		('/' + settings.urls.websocket, WebSocketHandler),
	], )

	application.listen(settings.port)
	application.debug_level = settings.debug_level
	application.debug("Started watch server on localhost:%d, waiting for connections. Ctrl-c or close window to stop." % settings.port)
	tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__": start()
