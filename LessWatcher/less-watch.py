import sublime, sublime_plugin
import os, httplib, contextlib, itertools
from functools import partial


plugin = __name__.title().replace('-', '')
settings = sublime.load_settings("LessWatcher.sublime-settings")
debug_level = settings.get('debug_level') or 0


def warning(message, level=1):
	if debug_level < level: return
	print "[less-watch] %s" % message
	sublime.status_message("[less-watch] %s" % message)

class HTTPMessage(object):
	def __init__(self, message=None, silent=1):
		self.host = 'localhost:9000'
		self.url = '/watch_server'
		self.headers = {'Content-type': 'text/plain', 'Accept': 'text/plain'}
		self.silent = silent
		# settings = sublime.load_settings("LessWatcher.sublime-settings")
		# current = s.get("font_size", 10)
		if message is not None: self.send(message)

	@contextlib.contextmanager
	def _http_connect(self, host, timeout=0.05):
		try:
			conn = httplib.HTTPConnection(host, timeout=timeout)
			yield conn
		finally:
			conn.close()

	def send(self, message, silent=None):
		if silent is None: silent = self.silent
		with self._http_connect(self.host) as conn:
			if message and not silent: warning("sending message: %s ..." % message.replace('\n', '\\n'))
			# try sending, if not successful, mock a http response with the exception
			try:
				conn.request('POST', self.url, message, self.headers)
				response = conn.getresponse()
			except Exception, e:
				response = HTTPResponse(reason='Cannot connect to the server: %s' % e)
			body = response.read()
			# non-standard responses should be seen
			if response.status != 200 and not silent:
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
	def __init__(self, id='', block=''):
		self.id = id
		self.block = block
	def __repr__(self): return self.__str__()
	def __str__(self): return '%s { %s }' % (' '.join(self.id), self.block)

class BlockParser(object):
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

class EditListener(sublime_plugin.EventListener):
	def __init__(self):
		self.message = HTTPMessage()
		self.parser = BlockParser()
		self.last_change = BlockInfo()
		self.active = False
		self.files = {}

		self.default_commands = {
			'open': 'reload_file', 
			'save': 'reload_file', 
			'close': 'reload_file', 
			'edit': 'update', 
		}

		convert = lambda x: x if type(x) is list else [x, 0]
		self.watch = dict([ext, dict(map(convert, events))] for ext, events in settings.get('watch_events', {}).iteritems())

	def filename(self, f):
		return (f if type(f) in [str, unicode] else (f.file_name() or '') if type(f) is sublime.View else '').replace(os.path.sep, '/')

	def update_files(self):
		# active 1 means a view has been activated; no files means a freshly (re)loaded plugin
		if self.active is not 1 and self.files: return 2 # already have a fresh filelist

		# ask for a fresh file list (send an empty message, expect a file on each line)
		# if no server, or no filelist, deactivate until the next window focus (to avoid shooting these empty requests)
		response, body = self.message.send('', silent=1)
		result = self.check_file_update(response, body)
		if not result: self.on_deactivated()
		else: self.active = result
		return result

	def check_file_update(self, response, body):
		if not response or response.status != 200:
			return warning('watch server not found, ignoring edits temporarily.')
		body = filter(None, map(str.strip, body.split('\n')))
		if not body:
			if not self.files: warning('no files to watch yet (refresh your browser, and check the javascript console).')
			return
		if debug_level > 1: warning('new file list: ' + ', '.join(body))
		elif not self.files: warning('watching files: ' + ', '.join(map(lambda x: x.rsplit('/', 2).pop(), body)))
		self.files = dict.fromkeys(body, 1)
		return True # be active, but don't ask for new files

	def watching_file_type(self, filename='', event=''):
		filename = self.filename(filename)
		if not filename: return 0
		events = self.watch.get(filename.rsplit('.', 2).pop())
		return events.get(unicode(event)) if events and event else events

	def watching_file(self, filename):
		filename = self.filename(filename)

		# check if this file matches one of the watched files (flexibly, /web/docroot/some/path.less matches /some/path.less)
		# if found, either store the localfile: filehandle pair, or flag as non-watched
		# after a window reactivation, the first watched event will request a fresh file list, and check the file again
		if filename not in self.files:
			self.files[filename] = next((handle for handle, watched in self.files.iteritems() if watched and filename.endswith(handle)), None)

		# None/False/0: a file type which should be watched (see settings), but no webclients asked for watching it
		# 1: watched file, but no event happened since the last window activation
		# str/unicode: a watched file's filehandle (webclients track files by basepath + filename)
		return self.files[filename]

	def file_event(self, filename, event, custom_arg=''):
		filename = self.filename(filename)
		if not filename: return warning('an unknown file\'s %sevent was ignored.' % (event and event + ' '))

		command = self.watching_file_type(filename, event) or self.default_commands.get(event)
		if not command: return

		# check if the file list is fresh, and if this file is watched
		if not self.update_files() or not self.watching_file(filename): return

		# get the url of this file (self.files should have it if we watched it), if none, skip it
		filename = self.files.get(filename, None)
		if not filename: return
		response, body = self.message.send("%s\n%s %s" % (filename, command, custom_arg))

	def on_activated(self, view):
		self.active = int(bool(self.watching_file_type(view)))

	def on_deactivated(self, view=None):
		self.active = False

	def on_load(self, view):
		self.file_event(view, 'open', 'opened')

	def on_post_save(self, view):
		self.file_event(view, 'save', 'saved')

	def on_close(self, view):
		self.file_event(view, 'close', 'closed')

	def on_modified(self, view):
		if not self.active: return

		# see if edit updates are enabled for this file type
		# this currently only makes sense for less and css files; the code below only works with these
		filename = view.file_name() or ''
		if not filename or not self.watching_file_type(filename, 'edit'): return

		# check if there are any files to watch, and if this file is watched
		if not self.update_files() or not self.watching_file(filename): return
		filename = filename.replace(os.path.sep, '/')

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
		sublime.status_message("[less-watch: updating line] %s" % line)

		# store and send the change: filehandle\ncommand\ncontents
		self.last_change = info
		response, body = self.message.send("\n".join([self.files[filename], 'update', str(info)]), silent=1)

		# a non-empty response means a fresh file list, so refresh it
		if response.length: self.update_files(response, body)

