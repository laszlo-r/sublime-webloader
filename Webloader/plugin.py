import sublime, sublime_plugin
import os, time, contextlib, re
import modules


@contextlib.contextmanager
def ignored(*exceptions):
	try: yield
	except exceptions: pass


class Webloader(object):
	def __init__(self):
		self.settings = sublime.load_settings("Webloader.sublime-settings")

		address = self.settings.get('server', 'localhost:9000').split(':')
		self.server_address = (address[0], int(address[1]))

		ip_pattern = lambda x: re.compile(x.replace('*', '[0-9]+')) if '*' in x else None
		clients = str(self.settings.get('clients') or '').split()
		self.client_ips = {} if not clients or '*' in clients else dict((k, ip_pattern(k)) for k in clients if k)

		self.watch_events = self.settings.get('watch_events', {})
		self.sites = self.settings.get('sites', {})

		self.save_parsed_less = self.settings.get('save_parsed_less', None)
		self.prefix = self.settings.get('message_prefix', '[Webloader] ')
		self.logfile = os.path.join(sublime.packages_path(), 'Webloader', self.settings.get('logfile', 'webloader.log'))
		self.console_log = self.settings.get('console_log', 0)

		self._server = None

		if self.get_server(if_running=1):
			return self.log('\nstarted -- server already running on %s:%d ' % self._server.address)
		self.check_server()

	def check_server(self):
		"""Attempts to get the server after settings.init_server_delay seconds."""
		delay = 0
		with ignored(Exception): delay = float(self.settings.get('init_server_delay'))
		delay = min(max(delay, 0), 20)
		self.log('\nstarted -- checking server in %d seconds' % delay)
		if delay: sublime.set_timeout(self.get_server, int(delay * 1000))

	def get_server(self, if_running=0):
		"""Checks or restarts the server; always returns the current server."""
		if not self._server and hasattr(sublime, 'webloader_server'):
			self._server = sublime.webloader_server
			self._server.plugin = self
			if self.server_address[1] != self._server.address[1]: self.server.stop()

		# true if running OR initializing (False)
		if self._server and self._server.running is not None: return self._server
		if if_running: return None

		if not self.server_address:
			self.log('invalid server address %s (check plugin settings)' % str(self.server_address))
			raise Exception('invalid server address %s' % str(self.server_address))

		self._server = sublime.webloader_server = modules.server.Server(
			self.server_address, plugin=self, client_ips=self.client_ips.copy(), log=self.log, debug=100).start()
		self.log('\nserver started on %s:%d ' % self._server.address)
		return self._server

	@property
	def server(self):
		return self.get_server()

	def command(self, cmd, filename='', content='', client=None):
		# access self._server directly so as not to cause an automatic restart
		if cmd == 'stop': return self._server and self._server.stop()
		elif cmd == 'restart': return self._server and self._server.stop() or sublime.set_timeout(self.get_server, 1000)
		elif cmd == 'start': return self.server

		if self.server.running is None: return # not running, or starting

		def runcommand():
			try: self.server.command(cmd, filename, content, client)
			except Exception as e: self.log('Could not send command:', e)

		modules.websocket.Thread(target=runcommand).start()

	def status_message(self, message):
		f = lambda: sublime.status_message("%s%s" % (self.prefix, message))
		sublime.set_timeout(f, 50)

	def console_message(self, message, open=0):
		def f():
			if open: sublime.active_window().run_command('show_panel', {'panel': 'console', 'xtoggle': True})
			print "%s%s" % (self.prefix, message)
		sublime.set_timeout(f, 50)

	def message(self, client, message):
		client_id = client.page
		message = '%s sends: %s' % (client_id, message)
		self.log(message)

	# logging:
	# should add a logging class, produced and configured by this class,
	# because other threads will not always be able to access 'self' and
	# will throw exceptions while this is (re)loading or removed
	def log(self, obj, *message):
		if isinstance(obj, (str, unicode)):
			message = (obj,) + message
			obj = self

		ident = ''
		if isinstance(obj, modules.server.Client): ident = 'Client#%-5d' % (obj.ident or 0)
		elif isinstance(obj, modules.server.Server): ident = 'Server#%-5d' % (obj.ident or 0)
		elif obj == self: ident = 'Webloader'

		sign = ['| ', ''][len(message) > 1 and isinstance(message[0], str) and len(message[0]) == 1]
		message = ' '.join(map(str, message))
		newline = ['', '\n'][message[0] == '\n']
		now = time.strftime('%y%m%d %X') if time else ''

		if obj == self or self.console_log: print self.prefix + (message[1:] if newline else message)

		message = '%s  %-12s %s%s' % (now, ident, sign, message[1:] if newline else message)

		if obj == self: message = message.ljust(80, '-') # usually important messages
		with open(self.logfile, 'a') as f: f.write(newline + message + '\n')


webloader = Webloader()


class WebloaderEvents(sublime_plugin.EventListener):
	"""
	On watch_events, sends commands for the current file to the webloader.

	If there is an event for the current file extension in watch_events
	(defined in settings), calls webloader.command(). Also tracks the
	window's status: is it focused; active (any events for current file);
	live edit updates are enabled for current file.
	"""
	def __init__(self):
		self.debug_level = webloader.settings.get('debug_level', 0)
		self.parser = modules.css.Parser()
		self.last_change = modules.css.Block()
		self.focused = True # Sublime window active
		self.active = False # watching the currently open file
		self.live_update = False # live-updating changes in current file
		self.files = {}
		self.default_events = {
			'open': 'reload_file',
			'save': 'reload_file',
			'close': 'reload_file',
			'edit': 'update',
		}

		events = webloader.settings.get('watch_events', {})
		self.watch_events = dict([ext, dict(map(self.parse_event, ev))] for ext, ev in events.iteritems())
		sublime.webloader_events = self

	def parse_event(self, event):
		"""Interprets an event definition, returns [event, [action1, ...]]"""
		return ['', 0] if not event else \
			[event, 0] if not isinstance(event, list) else \
			(event + [0])[0:2] if len(event) < 3 else \
			event[0:1] + [event[1:]]

	def filename(self, f):
		return ((f.file_name() or '') if isinstance(f, sublime.View) else f).replace(os.path.sep, '/')

	def file_type_events(self, filename='', event=''):
		"""
		Returns events defined for this filetype or actions for an event.

		Either None (not watching this filetype or event), or a dict of events
		(if event is not specified), or a list of actions (non-empty).
		"""

		filename = self.filename(filename)
		if not filename: return 0
		events = self.watch_events.get(filename.rsplit('.', 2).pop())
		if not event or not events: return events or None

		events = events.get(unicode(event))
		if not events and events is not None: events = self.default_events.get(event)
		if not events: return None
		return events if isinstance(events, list) else [events]

	def file_event(self, view, event, args=None, content=''):
		if not self.active: return
		filename = self.filename(view)
		if not filename: return

		# when developing, saving the plugin interrupts with tests, disabled for now
		if filename.endswith('Webloader/plugin.py'): return

		commands = self.file_type_events(filename, event)
		if not commands: return
		args = ' '.join(args) if isinstance(args, list) else args or ''
		if args: commands = map(lambda x: '%s %s' % (x, args), commands)

		[webloader.command(cmd, filename, content) for cmd in commands]

	def on_activated(self, view):
		self.focused = True
		events = self.file_type_events(view) # anything for current file?
		self.active = bool(events and True)
		self.live_update = bool(events and events.get('edit', None) is not None)

	def on_deactivated(self, view=None):
		self.focused = None
		sublime.set_timeout(lambda: self.post_deactivated(view), 50)

	def post_deactivated(self, view=None):
		if self.focused is None: self.focused = True

	def on_load(self, view): self.file_event(view, 'open', 'opened')
	def on_post_save(self, view): self.file_event(view, 'save', 'saved')
	def on_close(self, view): self.file_event(view, 'close', 'closed')

	def on_modified(self, view):
		if not (self.focused and self.active and self.live_update and view.file_name()): return

		# TODO:
		# 1. validate the currently edited "key:value;" against known keys, skip if unknown
		# 2. remove whitespace, compare to previous update, skip if unchanged
		# 3. figure out an efficient way for selector and bracket changes (don't send a whole file)

		cursor = view.sel()[0]
		line = view.substr(view.line(cursor))
		sublime.status_message("%supdating line: %s" % (webloader.prefix, line))
		block_info = self.parser.block_info(cursor.begin(), view.substr(sublime.Region(0, view.size())))
		self.last_change = block_info
		self.file_event(view, 'edit', content=str(block_info))


class WebloaderJsCommand(sublime_plugin.WindowCommand):
	def __init__(self, *args, **kw):
		super(WebloaderJsCommand, self).__init__(*args, **kw)
		self.clients = []
		self.client = None
		self.open = 0
		self.prev = "console.log('Hey!')"

	def run(self, run_prev=None, *args, **kw):
		if self.client not in webloader.server.clients: return self.select_client()
		self.show_panel()

	def show_panel(self):
		if self.open: return self.select_client()
		self.open = 1
		self.window.show_input_panel('Run javascript on %s:' % self.client_id(), self.prev, self.on_done, None, self.on_cancel)

	def on_cancel(self):
		self.open = 0

	def on_done(self, js):
		self.open = 0
		js = js.strip()
		if not self.client or not js: return
		self.prev = js
		webloader.command('run', content=js, client=self.client)
		sublime.status_message("Running js: '%s'" % js)
		sublime.set_timeout(self.run, 50)

	def client_id(self, client=None):
		if not client: client = self.client
		return '/'.join(client.page.rsplit('/', 3)[1:]) if client else '?'

	def select_client(self):
		watching = None
		clients = webloader.server.clients

		if len(clients) > 1:
			view = self.window.active_view()
			filename = (view.file_name() or '').replace(os.path.sep, '/')
			watching = webloader.server.clients_watching(filename)
			if watching: clients = watching

		if len(clients) > 1:
			def setclient(index):
				if index < 1: return
				self.client = self.clients[index - 1]
				sublime.set_timeout(self.run, 50)

			header = ['Select a page to run javascript on (up/down/enter or mouse):']
			if watching: header.append("These all watch this '%s'" % os.path.basename(filename))
			items = [header] + [["Run on %s" % self.client_id(x), x.page] for x in clients]
			self.clients = clients
			self.open = 0
			return self.window.show_quick_panel(items, setclient)

		if clients: self.client = clients[0]


class WebloaderServerCommand(sublime_plugin.WindowCommand):

	def run(self, *args, **kw):
		if not hasattr(self, 'prev'): self.prev = ''
		self.window.show_input_panel('Run server command', self.prev, self.on_done, None, None)

	def on_done(self, cmd):
		self.prev = cmd
		sublime.status_message("Running server command: '%s'" % cmd)
		webloader.command(*cmd.split(' ', 2))

