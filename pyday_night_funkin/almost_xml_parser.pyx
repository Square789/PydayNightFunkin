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

cdef bool is_space(unsigned int c):
	return c in (10, 13, 9, 32) # ('\n', '\r', '\t', ' ')

cdef int ord_at(str string, int idx):
	if idx < 0 or idx >= len(string):
		return -1
	return ord(string[idx])

class AlmostXMLParserException(SyntaxError):
	def __init__(self, msg, p, *args, **kwargs):
		super().__init__(f"{msg} (pos {p})", *args, **kwargs)


cdef class AlmostXMLParser():

	DefaultHandlerExpand = None
	StartElementHandler = None
	EndElementHandler = None
	StartNamespaceDeclHandler = None
	EndNamespaceDeclHandler = None
	CharacterDataHandler = None
	CommentHandler = None
	ProcessingInstructionHandler = None

	cpdef parse(self, str string, int p = 0):
		cdef STATE state = STATE.BEGIN
		cdef STATE next_ = STATE.BEGIN
		cdef str aname
		cdef int start = 0
		cdef int nsubs = 0
		cdef int nbrackets = 0
		cdef str buf = ""
		cdef STATE escape_next = STATE.BEGIN
		cdef int attr_val_quote = -1

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
					# TODO
					print("Create PCDATA", repr(buf))
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
					# TODO
					print("Create CDATA", repr(string[start:p]))
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
					# TODO
					# raise AlmostXMLParserException("Expected node name [BEGIN_NODE]", p)
					print("Check parent for null")
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
						raise AlmostXMLParserException("Expected node name [TAG_NAME]", p)
					# TODO
					print("Create element", repr(string[start:p]))
					state = STATE.IGNORE_SPACES
					next_ = STATE.BODY
					continue

			elif state == STATE.BODY:
				if c == ord('/'):
					state = STATE.WAIT_END
				elif c == ord('>'):
					state = STATE.CHILDS
				else:
					state = STATE.ATTRIB_NAME
					start = p
					continue

			elif state == STATE.ATTRIB_NAME:
				if not is_valid_char(c):
					if start == p:
						raise AlmostXMLParserException("Expected attribute name", p)
					aname = string[start:p]
					# TODO
					print("Check attribute name duplication for", repr(aname))
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
					# TODO
					print("Set attribute name", repr(aname), "to", repr(buf))
					buf = ""
					state = STATE.IGNORE_SPACES
					next_ = STATE.BODY

			elif state == STATE.CHILDS:
				p = self.parse(string, p)
				start = p
				state = STATE.BEGIN

			elif state == STATE.WAIT_END:
				if c == ord('>'):
					state = STATE.BEGIN
				else:
					raise AlmostXMLParserException("Expected '>'", p)

			elif state == STATE.WAIT_END_RET:
				if c == ord('>'):
					if nsubs == 0:
						pass
						# TODO fuck what
						# parent.addChild(Xml.createPCData(""));
						print("Add child to parent? Oh no")
					return p
				else:
					raise AlmostXMLParserException("Expected '>'", p)

			elif state == STATE.CLOSE:
				if not is_valid_char(c):
					if start == p:
						raise AlmostXMLParserException("Expected node name [CLOSE]", p)

					tmpsub = string[start:p]

					# TODO
					# if (parent == null || parent.nodeType != Element) {
					# 	throw new XmlParserException('Unexpected </$v>, tag is not open', str, p);
					# }
					# if (v != parent.nodeName)
					# 	throw new XmlParserException("Expected </" + parent.nodeName + ">", str, p);
					print("S.CLOSE stuff")

					state = STATE.IGNORE_SPACES
					next_ = STATE.WAIT_END_RET
					continue

			elif state == STATE.COMMENT:
				if string[p : p+3] == "-->":
					# TODO
					print("Add comment")
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

					# TODO
					# var str = str.substr(start + 1, p - start - 2);
					# addChild(Xml.createProcessingInstruction(str));
					print("Create ProcessingInstruction")

					state = STATE.BEGIN

			elif state == STATE.ESCAPE:
				if c == ord(';'):
					esc_str = string[start:p]
					if esc_str[0] == ord('#'):
						pass
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
			# TODO
			# if (parent.nodeType == Element) {
			# 	throw new XmlParserException("Unclosed node <" + parent.nodeName + ">", str, p);
			# }
			# if (p != start || nsubs == 0) {
			# 	buf.addSub(str, start, p - start);
			# 	addChild(Xml.createPCData(buf.toString()));
			# }
			print("PCDATA stuff")
			return p

		if state == STATE.ESCAPE and escape_next == STATE.PCDATA:
			buf += ord('&')
			buf += string[start:p]
			# addChild(Xml.createPCData(buf.toString()));
			print("Add child ESCAPE -> PCDATA", repr(buf))
			return p

		raise AlmostXMLParserException("Unexpected EOF", p)
