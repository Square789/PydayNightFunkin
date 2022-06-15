
from xml.etree.ElementTree import TreeBuilder, XMLParser
from pyday_night_funkin.core.almost_xml_parser import AlmostXMLParser

XML_DATA = [
	"<bad> </data>",
	"<good> data </good>",
	"<good a='1' b='3'> data </good>",
	"<ok><bad very='1' very='2'> terrible </bad></ok>",
	"<swap><schmap>bad data</swap></schmap>",
	"<This> <is quite='really'> <some/> nested stuff </is></This>",
	"<hello></and goodbye>",
	'<SubTexture name="<0001" x="797" y="74" width="38" height="56"/>',
	'<?xml version="1.0" encoding="utf-8"?>',
	"<!--le epic comment--> <x a='&;&lt;' />",
	"<BadData a='&#x;&lt;3' />",
]


class LoudTreeBuilder(TreeBuilder):
	_indent = 0

	def _indent_print(self, *args, **kwargs):
		print(" " * self._indent, end = "")
		print(*args, **kwargs)

	def start(self, tag, attrs):
		self._indent_print(f"Start element {tag!r} {attrs}")
		self._indent += 2
		super().start(tag, attrs)

	def end(self, tag):
		self._indent -= 2
		self._indent_print(f"End element {tag!r}")
		super().end(tag)

	def start_ns(self, prefix, uri):
		self._indent_print(f"Namespace start {prefix} {uri}")
		super().start_ns(prefix, uri)

	def end_ns(self, prefix):
		self._indent_print(f"Namespace end {prefix}")
		super().end_ns(prefix)

	def data(self, data_):
		self._indent_print(f"Character data {data_!r}")
		super().data(data_)

	def comment(self, cstr):
		self._indent_print(f"Comment {cstr!r}")

	def pi(self, pi_):
		self._indent_print(f"Processing instruction {pi_!r}")
		# super().pi(pi_)

if __name__ == "__main__":
	for i, blob in enumerate(XML_DATA):
		print(f"=== {i} - {blob!r} === ")
		xp = XMLParser(target=LoudTreeBuilder())
		axp = AlmostXMLParser(target=LoudTreeBuilder())

		print("== Default parser:")
		try:
			xp.feed(blob)
			xp.close()
		except Exception as e:
			print("[!]", e)
		print()

		print("== Custom parser:")
		try:
			axp.feed(blob)
			axp.close()
		except Exception as e:
			print("[!]", e)
		print()

	print("=== DONE ===")
