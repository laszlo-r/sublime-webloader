import sublime, sublime_plugin
import os, time, contextlib
import modules


@contextlib.contextmanager
def ignored(*exceptions):
	try: yield
	except exceptions: pass


class Webloader(object):
	def __init__(self):
		self.settings = sublime.load_settings("Webloader.sublime-settings")
		self.prefix = self.settings.get('message_prefix', '[Webloader] ')
		self.logfile = os.path.join(sublime.packages_path(), 'Webloader', self.settings.get('logfile', 'webloader.log'))
		self.console_log = self.settings.get('console_log', 0)
		self.watch_events = self.settings.get('watch_events', {})
		self._server = None

		if self.get_server(if_running=1):
			return self.log('\nstarted -- server running on %s:%d ' % self._server.address)
		self.check_server()

	def check_server(self):
		"""Attempts to get the server after settings.init_server_delay seconds."""
		delay = 0
		with ignored(Exception): delay = float(self.settings.get('init_server_delay'))
		delay = min(max(delay, 0), 20)

		self.log('\nstarted -- checking server in %d seconds' % delay)
		if delay: sublime.set_timeout(self.get_server, int(delay * 1000))

	def get_server(self, if_running=0):
		"""Checks or restarts the server, and returns a server instance (or raises an exception)."""
		if not self._server and hasattr(sublime, 'webloader_server'):
			self._server = sublime.webloader_server
			self._server.plugin = self

		# true if running OR initializing (False)
		if self._server and self._server.running is not None: return self._server
		if if_running: return None

		address = self.settings.get('host'), self.settings.get('port')
		if None in address:
			self.log('invalid server address %s, aborting (check plugin settings)' % str(address))
			raise Exception('invalid server address %s' % str(address))

		self._server = sublime.webloader_server = modules.server.Server(address, plugin=self, log=self.log, debug=100).start()
		self.log('\nserver started on %s:%d ' % self._server.address)
		return self._server

	@property
	def server(self):
		return self.get_server()

	def command(self, cmd, filename='', content=''):
		# access self._server directly so as not to cause an automatic restart
		if cmd == 'stop': return self._server and self._server.stop()
		elif cmd == 'restart': return self._server and self._server.stop() or sublime.set_timeout(self.get_server, 1000)
		elif cmd == 'start': return self.server

		if self.server.running is None: return # not running, or starting

		self.server.command(cmd, filename, content)

	def message(self, client, message):
		client_id = client.page
		message = '%s xsends: %s' % (client_id, message)
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

		message = ' '.join(map(str, message))
		newline = ['', '\n'][message[0] == '\n']
		sign = ['| ', ''][len(message) > 1 and isinstance(message[0], str) and len(message[0]) == 1]
		now = time.strftime('%X') if time else ''

		message = '%s  %-12s %s%s' % (now, ident, sign, message[1:] if newline else message)

		if obj == self or self.console_log: print self.prefix + message
		if obj == self: message = message.ljust(80, '-') # usually important messages
		with open(self.logfile, 'a') as f: f.write(newline + message + '\n')


webloader = Webloader()


class WebloaderEvents(sublime_plugin.EventListener):
	"""
	Plugin contoller; listens to events, sends changes as short http requests.

	Keeps track of files the clients requested, and sends changes about the
	current file to the server (which forwards it to any interested clients).
	For css/less files it sends live updates on each (file-changing) keypress.
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

	def log(self, message, level=1, console=1, status=1):
		"""Prints to the sublime console and status line, if debug_level > 0."""
		if not (console or status) or self.debug_level < level: return
		message = webloader.settings.get('message_prefix', '') + message
		if console: print message
		if status: sublime.status_message(message)

	def parse_event(self, event):
		"""Interprets an event definition, returns [event, [action1, ...]]"""
		return ['', 0] if not event else \
			[event, 0] if not isinstance(event, list) else \
			(event + [0])[0:2] if len(event) < 3 else \
			event[0:1] + [event[1:]]

	def filename(self, f):
		return (f.file_name() if isinstance(f, sublime.View) else f).replace(os.path.sep, '/')

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
		if not view.file_name(): return
		self.focused = True
		events = self.file_type_events(view) # anything for current file?
		self.active = bool(events and True)
		self.live_update = bool(events and events.get('edit') and True)

	def on_deactivated(self, view=None):
		self.focused = None
		sublime.set_timeout(lambda: self.post_deactivated(view), 50)

	def post_deactivated(self, view=None):
		if self.focused is None: self.focused = True

	def on_load(self, view): self.file_event(view, 'open', 'opened')
	def on_post_save(self, view): self.file_event(view, 'save', 'saved')
	def on_close(self, view): self.file_event(view, 'close', 'closed')

	def on_modified(self, view):
		if not (self.focused and self.active and self.live_update): return

		# TODO:
		# 1. validate the currently edited "key:value;" against known keys, skip if unknown
		# 2. remove whitespace, compare to previous update, skip if unchanged
		# 3. figure out an efficient way for selector and bracket changes (don't send a whole file)

		cursor = view.sel()[0]
		self.log("updating line: %s" % view.substr(view.line(cursor)), status=1)
		block_info = self.parser.block_info(cursor.begin(), view.substr(sublime.Region(0, view.size())))
		self.last_change = block_info
		self.file_event(view, 'edit', content=str(block_info))


class WebloaderJsCommand(sublime_plugin.WindowCommand):
# class WebloaderJsCommand(sublime_plugin.ApplicationCommand):
# class WebloaderJsCommand(sublime_plugin.TextCommand):
	def __init__(self, *args, **kw):
		super(WebloaderJsCommand, self).__init__(*args, **kw)

	def run(self, **args):
		# look at the current file, find the attached client, and run the js there
		# if more clients, show_quick_panel with clients, user selects a target (store it)
		#   run commands on that client, until user cancels the dialog, reset stored client

		# quick_panel example
		# def on_done(index):
		# 	sublime.status_message('Selected item %d' % index)
		# items = ['run on item1', ['item2', 'item2 line 2']]
		# self.window.show_quick_panel(items, on_done)

		if not hasattr(self, 'prev'): self.prev = "alert('Hey!')"
		self.window.show_input_panel('Run javascript', self.prev, self.on_done, None, None)

		# self.window.run_command('show_panel', {'panel': 'console', 'xtoggle': True})

	def on_done(self, js):
		self.prev = js
		sublime.status_message("Running js: '%s'" % js)
		self.window.show_input_panel('Run javascript', self.prev, self.on_done, None, None)
		webloader.command('run', content=js)


class WebloaderServerCommand(sublime_plugin.WindowCommand):

	def run(self, *args, **kw):
		if not hasattr(self, 'prev'): self.prev = ''
		self.window.show_input_panel('Run server command', self.prev, self.on_done, None, None)

	def on_done(self, cmd):
		self.prev = cmd
		sublime.status_message("Running server command: '%s'" % cmd)
		webloader.command(*cmd.split(' ', 2))

