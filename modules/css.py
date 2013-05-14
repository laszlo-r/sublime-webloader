import sublime
import itertools, re
from functools import partial

class Parser(object):
	"""Parses less and css definitions; methods always work on self.content."""

	def __init__(self, content=''):
		self.content = content
		self.props = {}
		self.defs = {}

	def brackets_match(self):
		"""True if the brackets match in self.content (<0.01s on a 10k file)."""
		return not sum(map(lambda x: 1 if x == "{" else -1 if x == "}" else 0, self.content))

	def find_next(self, keys, range):
		"""Returns (index, key) for the first key found in content in this range."""
		return next(((x, self.content[x]) for x in range if self.content[x] in keys), None)

	def get_block(self, cursor):
		"""Returns the brackets (with positions) and text of a block."""
		brackets = dict.fromkeys('{}', 0)
		start = self.find_next(brackets, reversed(xrange(0, cursor.begin()))) or (-1, '')
		end = self.find_next(brackets, xrange(cursor.begin(), len(self.content))) or (len(self.content), '')
		block = self.content[start[0] + 1:end[0]]
		return start, end, block

	def definitions(self, block, validate=0, with_selector=0):
		"""Returns css definitions from a block, validated if asked.

		If with_selector, the (stripped) part after the last ';' is included.
		"""
		block = re.sub(r"/[*].*[*]/", '', str(block))
		defs = map(self.definition_pair, block.split(';'))
		if with_selector: defs[-1] = [' '.join(defs[-1][0].split()), True]
		return dict(filter(self.valid_pair, defs) if validate else defs)

	def definition_pair(self, x):
		return map(str.strip, (x.split(':', 1) + [''])[0:2])

	def valid_pair(self, x):
		return len(x) == 2 and x[0] and x[1] and (x[0][0] == '@' or self.props.get(x[0]) or x[1] is True)

	def get_css_props(self):
		import css_completions
		self.props = css_completions.parse_css_data(css_completions.css_data)

	def has_changed(self, content, cursor):
		"""Checks the current block for changes, returns true if they matter.

		Verifies the following:
		- brackets don't match? ignore the change
		- find the current block, put it's VALID definitions into a dict
		- if it differs from the previous in self.defs, return true
		- if the block ends with '{', selector changes also matter
		"""
		self.content = content
		if not self.brackets_match(): return

		# this is a built-in module, assume it's available now
		if not self.props: self.get_css_props()

		start, end, block = self.get_block(cursor)
		defs = self.definitions(block, validate=1, with_selector=end[1] == '{')
		if self.defs == defs: return
		self.defs = defs
		return self.content


	def block_info(self, position, content=None):
		"""Returns a Block, with parent selectors and contents for the block at position."""

		if content is not None: self.content = content
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
		return Block(parents, block)

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

class Block(object):
	"""Contains the css selector chain and contents of a css block."""

	def __init__(self, id='', block=''):
		self.id = id
		self.block = block
	def __repr__(self): return self.__str__()
	def __str__(self): return '%s { %s }' % (' '.join(self.id), self.block)

