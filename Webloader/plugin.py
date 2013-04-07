import sublime, sublime_plugin
import os, time
import modules
import select


class Webloader(object):
	def __init__(self):
		self.settings = sublime.load_settings("Webloader.sublime-settings")
		self.server = None
		self.prefix = self.settings.get('message_prefix', '[Webloader] ')
		self.logfile = os.path.join(sublime.packages_path(), 'Webloader', self.settings.get('logfile', 'webloader.log'))
		self.console_log = self.settings.get('console_log', 0)
		self.log('plugin loaded, checking server...')
		sublime.set_timeout(self.check_server, 1000)

	def check_server(self):
		if not hasattr(sublime, 'websocket_server') or not sublime.websocket_server.socket:
			address = self.settings.get('host'), self.settings.get('port')
			if None in address: return self.log('invalid server address %s, aborting' % str(address))
			self.server = sublime.websocket_server = modules.server.Server(address, plugin=self, log=self.log, debug=10).start()
			self.log('server started on %s:%d' % self.server.address)
		else:
			self.server = sublime.websocket_server
			self.server.plugin = self
			self.log('server running on %s:%d' % self.server.address)

	def command(self, cmd, filename='', content=''):
		if self.server:
			self.server.command(cmd, filename, content)

	def message(self, message):
		message = self.settings.get('message_prefix', '') + message
		print message

	def log(self, obj, *message):
		if isinstance(obj, (str, unicode)):
			message = (obj,) + message
			obj = self
		ident = ''
		if hasattr(obj, 'client_address'): ident = '%-15s %-5d' % obj.client_address
		elif hasattr(obj, 'address'): ident = 'Server'
		sign = len(message) > 1 and isinstance(message[0], str) and len(message[0]) == 1
		now = time.strftime('%X') if time else '--------'
		message = '%s%s  %-21s %s%s' % (self.prefix, now, ident, ['| ', ''][sign], ' '.join(map(str, message)))

		if self.console_log: print message
		with open(self.logfile, 'a') as f: f.write(message + '\n')


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
		self.active = False
		self.live_update = False
		self.refresh_files = True
		self.files = {}
		self.default_commands = {
			'open': 'reload_file', 
			'save': 'reload_file', 
			'close': 'reload_file', 
			'edit': 'update', 
		}

		convert = lambda x: x if type(x) is list else [x, 0]
		self.watch_events = dict([ext, dict(map(convert, events))] for ext, events in webloader.settings.get('watch_events', {}).iteritems())

	def log(self, message, level=1, console=1, status=1):
		"""Prints to the sublime console and status line, if debug_level > 0."""
		if not (console or status) or self.debug_level < level: return
		message = webloader.settings.get('message_prefix', '') + message
		if console: print message
		if status: sublime.status_message(message)

	def filename(self, f):
		return (f if isinstance(f, (str, unicode)) else 
			(f.file_name() or '') if isinstance(f, sublime.View) else 
			'').replace(os.path.sep, '/')

	def update_files(self, response=None, body=None):
		if not self.refresh_files and self.files and not response: return 0

		# don't refresh files until a window reactivation (to avoid shooting file list requests)
		self.refresh_files = False

		# ask for a fresh file list (send an empty message, expect a file on each line)
		if not response: response, body = self.message.send('')

		if not response or response.status != 200:
			self.live_update = False
			self.log('watch server not found, ignoring edits temporarily.')
			return 0

		if body: body = filter(None, map(str.strip, body.split('\n')))
		if not body:
			if not self.files: self.log('no files to watch yet (refresh your browser, and check the javascript console).')
			return 0

		if self.debug_level > 1: self.log('new file list: ' + ', '.join(body))
		elif not self.files: self.log('watching files: ' + ', '.join(map(lambda x: x.rsplit('/', 2).pop(), body)))

		self.files = dict.fromkeys(body, 1)
		return len(body)

	def file_type_events(self, filename='', event=''):
		filename = self.filename(filename)
		if not filename: return 0
		events = self.watch_events.get(filename.rsplit('.', 2).pop())
		return events.get(unicode(event)) if events and event else events

	def watching_file(self, filename):
		"""Checks if this file matches one of the watched files (self.files)

		The match is flexible: */some/path.less matches /some/path.less
		If found, store the filepath:fileurl pair; if not, flag it as non-watched.
		After a window refocus, the next event will request a fresh file list,
		so a non-watched file will re-checked then.

		If self.files[filename] exists, it can be:
		1: a to-be-watched file handle (clients track files by basepath + filename)
		str/unicode: the file handle matching this filename
		None: a file which can be watched (see settings), but no clients asked for it
		"""
		filename = self.filename(filename)

		if filename not in self.files:
			self.files[filename] = next((handle for handle, watched in self.files.iteritems() if watched and filename.endswith(handle)), None)

		return self.files[filename]

	def file_event(self, view, event, args=None, content=''):
		filename = self.filename(view)
		if not filename: return self.log('an unknown file\'s %sevent was ignored.' % (event and event + ' '))

		cmd = self.file_type_events(filename, event) or self.default_commands.get(event)
		if not cmd: return

		# if no watched files or we have to refresh, do it, this file may have been requested
		self.update_files()

		# if we watch this file, get it's handle, otherwise ignore it
		filename = self.watching_file(filename)
		if not filename: return

		# try sending, with a low timeout, server could be down
		cmd = [cmd] + (args if isinstance(args, list) else [args] if args else [])
		response, body = self.message.send("%s\n%s\n%s" % (filename, ' '.join(cmd), content))

		# a non-empty response means a fresh file list, so refresh it
		if response.length: self.update_files(response, body)

	def xxon_activated(self, view):
		if not view.file_name(): return
		events = self.file_type_events(view)
		self.active = int(bool(events))
		self.live_update = bool(events and events.get('edit') is not None)
		if self.refresh_files: self.update_files()

	def xxon_deactivated(self, view=None):
		self.refresh_files = None
		sublime.set_timeout(lambda: self.post_deactivated(view), 50)

	def post_deactivated(self, view=None):
		if self.refresh_files is None: self.refresh_files = True
	
	def xxon_load(self, view):
		self.file_event(view, 'open', 'opened')

	def xxon_post_save(self, view):
		self.file_event(view, 'save', 'saved')

	def xxon_close(self, view):
		self.file_event(view, 'close', 'closed')

	def xxon_modified(self, view):
		if not self.live_update: return
		self.update_files()
		if not self.watching_file(view): return

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
		if not hasattr(self, 'prev'): self.prev = 'example_command on_filename with any content'
		self.window.show_input_panel('Run server command', self.prev, self.on_done, None, None)

	def on_done(self, cmd):
		self.prev = cmd
		sublime.status_message("Running server command: '%s'" % cmd)
		webloader.command(*cmd.split(' ', 2))

