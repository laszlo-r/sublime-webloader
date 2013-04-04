import sublime, sublime_plugin
import os, httplib, contextlib, itertools
from functools import partial

plugin = __name__.title().replace('-', '')
settings = sublime.load_settings("LessWatcher.sublime-settings")
debug_level = settings.get('debug_level') or 0


def warning(message, level=1, console=1, status=1):
	"""Prints to the sublime console and status line, if debug_level > 0."""
	if debug_level < level or not (console or status): return
	prefix = settings.get('message_prefix', '')
	message = prefix + message
	if console: print message
	if status: sublime.status_message(message)


class Refresher(sublime_plugin.EventListener):
	"""
	Plugin contoller; listens to events, sends changes as short http requests.

	Keeps track of files the clients requested, and sends changes about the 
	current file to the server (which forwards it to any interested clients).
	For css/less files it sends live updates on each (file-changing) keypress.
	"""
	def __init__(self):
		self.message = HTTPMessage(
			settings.get('host', 'localhost'), 
			settings.get('port', 9000), 
			settings.get('url', '/watch_server'), 
			settings.get('timeout', 0.05)
		)
		self.parser = BlockParser()
		self.last_change = BlockInfo()
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
		self.watch_events = dict([ext, dict(map(convert, events))] for ext, events in settings.get('watch_events', {}).iteritems())

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
			warning('watch server not found, ignoring edits temporarily.')
			return 0

		if body: body = filter(None, map(str.strip, body.split('\n')))
		if not body:
			if not self.files: warning('no files to watch yet (refresh your browser, and check the javascript console).')
			return 0

		if debug_level > 1: warning('new file list: ' + ', '.join(body))
		elif not self.files: warning('watching files: ' + ', '.join(map(lambda x: x.rsplit('/', 2).pop(), body)))
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
		if not filename: return warning('an unknown file\'s %sevent was ignored.' % (event and event + ' '))

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

	def on_activated(self, view):
		if not view.file_name(): return
		events = self.file_type_events(view)
		self.active = int(bool(events))
		self.live_update = bool(events and events.get('edit') is not None)
		if self.refresh_files: self.update_files()

	def on_deactivated(self, view=None):
		self.refresh_files = None
		sublime.set_timeout(lambda: self.post_deactivated(view), 50)

	def post_deactivated(self, view=None):
		if self.refresh_files is None: self.refresh_files = True
	
	def on_load(self, view):
		self.file_event(view, 'open', 'opened')

	def on_post_save(self, view):
		self.file_event(view, 'save', 'saved')

	def on_close(self, view):
		self.file_event(view, 'close', 'closed')

	def on_modified(self, view):
		if not self.live_update: return
		self.update_files()
		if not self.watching_file(view): return

		cursor = view.sel()[0]

		# TODO: see in readme
		# don't move until the line is valid (no full-file parsing or networking)
		# print "line:", view.line(cursor), view.substr(view.line(cursor))
		# print 'region:', cursor, view.line(cursor)
		# line = view.substr(view.line(cursor))
		# if not self.parser.validate(line, cursor.begin() - view.line(cursor).begin()): return

		# get the id and contents of the current css block
		position = cursor.begin()
		self.parser.content = view.substr(sublime.Region(0, view.size()))
		info = self.parser.block_info(position)

		# should trust the sublime api that there WAS a modification
		# should track changes per file; check if the change matters, whitespace changes don't matter for example
		# if not info.id or self.last_change.block == info.block: return

		# show the active line when updating (the actual update sent to the server can be multiple lines)
		line = view.substr(view.line(cursor))
		warning("updating line: %s" % line, status=1)

		# store and send the change
		self.last_change = info
		self.file_event(view, 'edit', content=str(info))

class HTTPMessage(object):
	"""Wraps httplib.HTTPConnection, sends plain text messages, returns HTTPResponse or httplib.HTTPResponse."""

	def __init__(self, host='', port='', url='', timeout=0, debug=None):
		self.host, self.port, self.url, self.timeout = host, port, url, timeout
		self.headers = {'Content-type': 'text/plain', 'Accept': 'text/plain'}
		self.debug = debug or debug_level

	@contextlib.contextmanager
	def _http_connection(self, host):
		try:
			# warning('%s %s %s' % (self.host, self.port, self.timeout))
			conn = httplib.HTTPConnection(self.host, self.port, timeout=self.timeout)
			yield conn
		finally:
			conn.close()

	def send(self, message, debug=None):
		"""Sends a plain text message via a one-time httplib.HTTPConnection."""

		if debug is None: debug = self.debug
		with self._http_connection(self.host) as conn:
			if message and debug: warning("sending message: %s ..." % message.replace('\n', '\\n'))
			# try sending, if not successful, mock a http response with the exception
			try:
				conn.request('POST', self.url, message, self.headers)
				response = conn.getresponse()
			except Exception, e:
				response = HTTPResponse(reason='Cannot connect to the server: %s' % e)
			body = response.read()
			# non-standard responses should be seen
			if response.status != 200 and debug:
				warning("got response: %d %s, %d bytes" % (response.status, response.reason, response.length))
				if response.length: warning(body)
			return response, body

class HTTPResponse(object):
	"""A blank http response, returned by HTTPMessage.send() if there were errors with the connection."""

	def __init__(self, status=0, reason='', length=0, body=''):
		self.status = status
		self.reason = reason
		self.length = length
	def read(self):
		return ''

class BlockInfo(object):
	"""Contains the css selector chain and contents of a css block."""

	def __init__(self, id='', block=''):
		self.id = id
		self.block = block
	def __repr__(self): return self.__str__()
	def __str__(self): return '%s { %s }' % (' '.join(self.id), self.block)

class BlockParser(object):
	"""Parses less and css definitions; methods always work on the current content."""

	def __init__(self, content=''):
		self.content = content

	def valid_pair(self, pair):
		return len(pair) == 2 and len(pair[0].strip()) and len(pair[0].split()) == 1 \
			and len(pair[1].strip())

	def validate(self, line, position):
		# print "validating: '%s', '%s', %d" % (line, line[position], position)
		line = line.strip()
		a, b = line.find('{') + 1, max(line.rfind('}'), 0) or len(line)
		line = line[a:b].strip()
		# problematic = map(lambda x: x.split(':'), line.split(';'))
		# print "validating: '%s'" % line
		return 1

	def block_info(self, position):
		"""Returns a BlockInfo, with parent selectors and contents for the block at position."""

		parents = self.get_parents(position)

		brackets = [self.get_bracket(position, forward=0), self.get_bracket(position)]
		block = self.content.__getslice__(*brackets).strip()
		brackets = [0, brackets[1] - brackets[0]]

		# crude optimization: if a multiline block, cut it at the starting line of the first child block
		next_line = block.find('\n')
		if next_line > -1:
			next_bracket = block.find('{', next_line)
			if next_bracket > -1:
				last_line = block.rfind('\n', next_line - 1, next_bracket)
				if last_line > -1: block = block[0:last_line]

		block = block.strip()
		return BlockInfo(parents, block)

	def get_bracket(self, position, forward=1, brackets='{}'):
		"""Returns the index of the next bracket forward or backward from position."""

		if not forward: brackets = list(reversed(brackets))

		string_type = type(self.content)
		lookup_in_content = partial([string_type.rfind, string_type.find][forward], self.content)
		lookup_if_needed = lambda string, pos, value: \
			value if value > -1 else \
			lookup_in_content(*[string] + ([pos + 1] if forward else [0, pos]))

		def next_bracket(position):
			pair = [-1, -1]
			while 1:
				pair = list(itertools.imap(lookup_if_needed, list(brackets), [position] * 2, pair))
				if pair[0] == pair[1] == -1: raise StopIteration
				elif pair[0] == -1: which = 1
				elif pair[1] == -1: which = 0
				else: which = pair[0] > pair[1] if forward else pair[0] < pair[1]
				position, pair[which] = pair[which], -1
				yield position

		# store the depth of the current position:
		# if > 0, in a child block; if 0, in the original block; if < 0, outside the original block
		depth = 0
		result = next_bracket(position)

		while not (position < 0 or depth < 0):
			position = next(result, -1)
			if position > -1: depth += (-1, 1)[self.content[position] == brackets[0]]

		if position > -1: return position + int(not forward)
		return len(self.content) if forward else 0

	def get_parents(self, position):
		"""Returns the css selector list (parents + own) of the block at position."""

		parents, in_block = [], 0
		# TODO: should convert to generator, like above
		while position > 0:
			a, b = self.content.rfind('{', 0, position), self.content.rfind('}', 0, position)
			position = max(a, b)
			if position < 0: break
			if a < b: in_block += 1
			elif in_block: in_block -= 1
			else: parents.append(str(self.content[max(self.content.rfind('\n', 0, a), 0):a-1].strip()))

		return list(reversed(parents))

