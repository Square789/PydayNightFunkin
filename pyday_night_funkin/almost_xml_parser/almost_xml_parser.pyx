"""
Haxe's XML parser tolerates `<` and `>` inside of tag attribute strings,
where python's parser fails. (Good on it, because that isn't valid XML.)
Unfortunately, alphabet.xml contains a less-than sign in a string and I
am dead-fucking-set on keeping the assets unchanged, so this is a cython
copypaste of haxe's XML parser, found here:
https://github.com/HaxeFoundation/haxe/blob/development/std/haxe/xml/Parser.hx
It only implements the handlers that are used in the standard
`xml.etree.ElementTree.XMLParser` class.
"""

from libc.stdint cimport uint8_t

ctypedef uint8_t bool


ctypedef enum STATE:
	IGNORE_SPACES,
	BEGIN,
	BEGIN_NODE,
	TAG_NAME,
	BODY,
	ATTRIB_NAME,
	EQUALS,
	ATTVAL_BEGIN,
	ATTRIB_VAL,
	CHILDS, # "childs" lol
	CLOSE,
	WAIT_END,
	WAIT_END_RET,
	PCDATA,
	HEADER,
	COMMENT,
	DOCTYPE,
	CDATA,
	ESCAPE



cdef bool is_valid_char(unsigned int c):
	return (
		(c >= ord('a') and c <= ord('z')) or
		(c >= ord('A') and c <= ord('Z')) or
		(c >= ord('0') and c <= ord('9')) or
		c == ord(':') or
		c == ord('.') or
		c == ord('_') or
		c == ord('-')
	)

cdef bool is_space(int c):
	return c in (10, 13, 9, 32) # ('\n', '\r', '\t', ' ')

cdef int ord_at(str string, int idx):
	if idx < 0 or idx >= len(string):
		return -1
	return ord(string[idx])

class AlmostXMLParserException(SyntaxError):
	def __init__(self, msg, p, *args, **kwargs):
		super().__init__(f"{msg} (pos {p})", *args, **kwargs)



cdef dict ESCAPES = {
	"lt": "<",
	"gt": ">",
	"amp": "&",
	"quot": "\"",
	"apos": "'",
}


cdef class AlmostXMLParser():
	"""
	Not fully compliant XML Parser.
	It also cheats and will concat all calls to `feed`'s strings and
	process them only once when `close` is called.
	"""

	cdef public element_start_handler
	cdef public element_end_handler
	cdef public character_data_handler
	cdef public processing_instruction_handler
	cdef public comment_handler

	cdef str _strbuf

	def __cinit__(self):
		self.element_start_handler = None
		self.element_end_handler = None
		self.character_data_handler = None
		self.processing_instruction_handler = None
		self.comment_handler = None

		self._strbuf = ""

	cpdef feed(self, str string):
		self._strbuf += string

	cpdef close(self):
		self.parse(self._strbuf)

	cdef parse(self, str string, int p = 0):
		cdef STATE state = STATE.BEGIN
		cdef STATE next_ = STATE.BEGIN
		cdef int start = 0
		cdef int nbrackets = 0
		cdef str buf = ""
		cdef str element_name
		cdef list element_name_stack = []
		cdef STATE escape_next = STATE.BEGIN
		cdef str attr_name
		cdef dict attrs = {}
		cdef int attr_val_quote = -1
		cdef int c

		while p < len(string):
			c = ord_at(string, p)
			if state == STATE.IGNORE_SPACES:
				if not is_space(c):
					state = next_
					continue

			elif state == STATE.BEGIN:
				if c == ord('<'):
					state = STATE.IGNORE_SPACES
					next_ = STATE.BEGIN_NODE
				else:
					start = p
					state = STATE.PCDATA
					continue

			elif state == STATE.PCDATA:
				if c == ord('<'):
					buf += string[start:p]
					# print("Create PCDATA", repr(buf))
					if self.character_data_handler is not None:
						self.character_data_handler(buf)
					buf = ""
					state = STATE.IGNORE_SPACES
					next_ = STATE.BEGIN_NODE
				elif c == ord('&'):
					buf += string[start:p]
					state = STATE.ESCAPE
					escape_next = STATE.PCDATA
					start = p + 1

			elif state == STATE.CDATA:
				if string[p : p+3] == "]]>":
					# print("Create CDATA", repr(string[start:p]))
					if self.character_data_handler is not None:
						self.character_data_handler(string[start:p])
					p += 2
					state = STATE.BEGIN

			elif state == STATE.BEGIN_NODE:
				if c == ord('!'):
					if ord_at(string, p + 1) == ord('['):
						p += 2
						if string[p : p+6] != "CDATA[":
							raise AlmostXMLParserException("Expected <![CDATA[", p)
						p += 5
						state = STATE.CDATA
						start = p + 1
					elif ord_at(string, p + 1) in (ord('D'), ord('d')):
						if string[p+2 : p+8] != "OCTYPE":
							raise AlmostXMLParserException("Expected <!DOCTYPE", p)
						p += 8
						state = STATE.DOCTYPE
						start = p + 1
					elif string[p+1 : p+3] != "--":
						raise AlmostXMLParserException("Expected <!--", p)
					else:
						p += 2
						state = STATE.COMMENT
						start = p + 1
				elif c == ord('?'):
					state = STATE.HEADER
					start = p
				elif c == ord('/'):
					if not element_name_stack:
						raise AlmostXMLParserException("Found closing node with no open elements", p)
					start = p + 1
					state = STATE.IGNORE_SPACES
					next_ = STATE.CLOSE
				else:
					state = STATE.TAG_NAME
					start = p
					continue

			elif state == STATE.TAG_NAME:
				if not is_valid_char(c):
					if p == start:
						raise AlmostXMLParserException("Expected node name", p)
					element_name = string[start:p]
					state = STATE.IGNORE_SPACES
					next_ = STATE.BODY
					continue

			elif state == STATE.BODY:
				if c == ord('/'):
					state = STATE.WAIT_END
				elif c == ord('>'):
					if self.element_start_handler is not None:
						self.element_start_handler(element_name, attrs)
					element_name_stack.append(element_name)
					attrs = {}
					element_name = ""
					state = STATE.BEGIN
				else:
					state = STATE.ATTRIB_NAME
					start = p
					continue

			elif state == STATE.ATTRIB_NAME:
				if not is_valid_char(c):
					if start == p:
						raise AlmostXMLParserException("Expected attribute name", p)
					attr_name = string[start:p]
					if attr_name in attrs:
						raise AlmostXMLParserException(f"Duplicate attribute name {attr_name!r}", p)
					state = STATE.IGNORE_SPACES
					next_ = STATE.EQUALS
					continue

			elif state == STATE.EQUALS:
				if c == ord('='):
					state = STATE.IGNORE_SPACES
					next_ = STATE.ATTVAL_BEGIN
				else:
					raise AlmostXMLParserException("Expected '='", p)

			elif state == STATE.ATTVAL_BEGIN:
				if c == ord('"') or c == ord('\''):
					buf = ""
					state = STATE.ATTRIB_VAL
					start = p + 1
					attr_val_quote = c
				else:
					raise AlmostXMLParserException("Expected '\"'", p)

			elif state == STATE.ATTRIB_VAL:
				if c == ord('&'):
					buf += string[start:p]
					state = STATE.ESCAPE
					escape_next = STATE.ATTRIB_VAL
					start = p + 1
				# no dumb > < check
				elif c == attr_val_quote:
					buf += string[start:p]
					attrs[attr_name] = buf
					buf = ""
					state = STATE.IGNORE_SPACES
					next_ = STATE.BODY

			elif state == STATE.WAIT_END:
				# WAIT_END is only entered on an instantly closed element, i.e.
				# <br />
				#      ^ here
				if c == ord('>'):
					if self.element_start_handler is not None:
						self.element_start_handler(element_name, attrs)
					if self.element_end_handler is not None:
						self.element_end_handler(element_name)
					attrs = {}
					element_name = ""
					state = STATE.BEGIN
				else:
					raise AlmostXMLParserException("Expected '>'", p)

			elif state == STATE.WAIT_END_RET:
				# WAIT_END_RET is only entered after CLOSE (and possibly IGNORE_SPACES) i.e.
				# <hello>world</hello >
				#                     ^ here
				if c == ord('>'):
					#print(f"Element {element_name_stack[-1]!r} closed")
					if self.element_end_handler is not None:
						self.element_end_handler(element_name_stack[-1])
					element_name_stack.pop()

					state = STATE.BEGIN
				else:
					raise AlmostXMLParserException("Expected '>'", p)

			elif state == STATE.CLOSE:
				# This state is entered right after BEGIN_NODE finds a `/`, i.e.
				# <hello>world</hello>
				#               ^ here
				if not is_valid_char(c):
					if start == p:
						raise AlmostXMLParserException("Expected node name", p)

					tmpsub = string[start:p]

					# check not required afaict since CLOSE is only reachable in one other place and
					# that one already checks for `parent == null`, which - due to the original
					# parser's recursive nature - means that no element opening node exists.
					# (And I'll gladly ignore what the `parent.nodeType != Element` check may be
					# responsible for)
					# if (parent == null || parent.nodeType != Element) {
					# 	throw new XmlParserException('Unexpected </$v>, tag is not open', str, p);
					# }
					if tmpsub != element_name_stack[-1]:
						raise AlmostXMLParserException(f"Expected </{element_name_stack[-1]}>", p)

					state = STATE.IGNORE_SPACES
					next_ = STATE.WAIT_END_RET
					continue

			elif state == STATE.COMMENT:
				if string[p : p+3] == "-->":
					if self.comment_handler is not None:
						self.comment_handler(string[start:p])
					p += 2
					state = STATE.BEGIN

			elif state == STATE.DOCTYPE:
				if c == ord('['):
					nbrackets += 1
				elif c == ord(']'):
					nbrackets -= 1
				elif c == ord('>') and nbrackets == 0:
					# TODO
					# addChild(Xml.createDocType(str.substr(start, p - start)));
					print("Create doctype")
					state = STATE.BEGIN

			elif state == STATE.HEADER:
				if c == ord('?') and ord_at(string, p + 1) == ord('>'):
					p += 1

					if self.processing_instruction_handler is not None:
						self.processing_instruction_handler(string[start+1 : p-2])

					state = STATE.BEGIN

			elif state == STATE.ESCAPE:
				if c == ord(';'):
					esc_str = string[start:p]
					if ord_at(esc_str, 0) == ord('#'):
						try:
							if ord_at(esc_str, 1) == ord('x'):
								buf += chr(int(esc_str[2:], 16))
							else:
								buf += chr(int(esc_str[1:]))
						except ValueError as e:
							raise AlmostXMLParserException("Bad integer value", p) from e
					elif esc_str not in ESCAPES:
						buf += f"&{esc_str};"
					else:
						buf += ESCAPES[esc_str]
					start = p + 1
					state = escape_next
				elif not is_valid_char(c) and c != ord('#'):
					buf += ord('&')
					buf += string[start:p]
					p -= 1
					start = p + 1
					state = escape_next

			p += 1

		if state == STATE.BEGIN:
			start = p
			state = STATE.PCDATA

		if state == STATE.PCDATA:
			if element_name_stack:
				raise AlmostXMLParserException(f"Unclosed node <{element_name_stack[-1]}>", p)
			if p != start:
				if self.character_data_handler is not None:
					self.character_data_handler(string[start:p])
			return p

		if state == STATE.ESCAPE and escape_next == STATE.PCDATA:
			buf += ord('&')
			buf += string[start:p]
			if self.character_data_handler is not None:
				self.character_data_handler(buf)
			return p

		raise AlmostXMLParserException("Unexpected EOF", p)
