import sublime, sublime_plugin
import httplib, contextlib, itertools
from functools import partial
import os, ast

def warning(message):
	print "[less-watch] %s" % message 

class HTTPMessage(object):
	def __init__(self, message=None, silent=1):
		self.host = 'localhost:9000'
		self.url = '/less_watch'
		self.headers = {'Content-type': 'text/plain', 'Accept': 'text/plain'}
		self.silent = silent
		# s = sublime.load_settings("Preferences.sublime-settings")
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

	def update_files(self, response, body):
		if not response or response.status != 200:
			return warning('watch server not found, ignoring edits temporarily.')
		body = filter(None, map(str.strip, body.split('\n')))
		if not body:
			if not self.files: warning('no files to watch yet (refresh your browser, and check the javascript console).')
			return
		self.files = dict.fromkeys(body, 1)
		warning('watching files: ' + ', '.join(body))
		return 1

	def refresh_file(self, view=None, status=''):
		filename = (view if type(view) is str else (view.file_name() or '')).replace(os.path.sep, '/')
		if not filename: return warning('an unknown file should have been refreshed (skipping this refresh).')
		# get the url of this file (self.files should have it if we watched it), if none, ignore it
		filename = self.files.get(filename, None)
		if not filename: return
		message = "%s\n/refresh %s" % (filename, status)
		response, body = self.message.send(message)

	def on_activated(self, view):
		if (view.file_name() or '').endswith('.less'): self.active = 1

	def on_deactivated(self, view): self.active = False

	def on_post_save(self, view): self.refresh_file(view, 'saved')

	def on_close(self, view): self.refresh_file(view, 'closed')

	def on_modified(self, view):
		if not self.active: return

		filename = view.file_name() or ''
		if not filename.endswith('.less'): return

		# active 1 or no files means we should ask for a fresh file list (send an empty message, expect a file on each line)
		# if no server connection or no files, deactivate until the next window focus (to avoid shooting lots of requests)
		if self.active is 1 or not self.files:
			response, body = self.message.send('', silent=1)
			if not self.update_files(response, body): return self.on_deactivated(view)
			self.active = True

		filename = filename.replace(os.path.sep, '/')
		# check if this file matches one of the watched files (/docroot/some/path.less matches /some/path.less)
		# either store the matched web-filename, or flag it as non-watched (window reactivation resets the file list anyway)
		if filename not in self.files:
			self.files[filename] = next((name for name, watched in self.files.iteritems() if watched and filename.endswith(name)), None)
		if not self.files[filename]: return

		selections = view.sel()
		cursor = selections[0]

		# TODO: see in readme
		# don't move until the line is valid (no full-file parsing or networking)
		# print "line:", view.line(cursor), view.substr(view.line(cursor))
		# print 'region:', cursor, view.line(cursor)
		# line = view.substr(view.line(cursor))
		# if not self.parser.validate(line, cursor.begin() - view.line(cursor).begin()): return

		# get the id and contents of the current block, see if it changed, ignore if not
		position = cursor.begin()
		self.parser.content = view.substr(sublime.Region(0, view.size()))
		info = self.parser.block_info(position)
		if not info.id or self.last_change.block == info.block: return

		# store and send changes
		self.last_change = info
		response, body = self.message.send("%s\n%s" % (self.files[filename], info), silent=1)

		# a non-empty response means an updated file list
		if response.length: self.update_files(response, body)

