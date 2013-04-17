import itertools
from functools import partial

class Parser(object):
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

