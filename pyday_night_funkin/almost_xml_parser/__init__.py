
from xml.etree.ElementTree import TreeBuilder

from .almost_xml_parser import AlmostXMLParser as _AXP


class AlmostXMLParser():
	def __init__(self, *, target = None) -> None:
		self._parser = parser = _AXP()

		if target is None:
			target = TreeBuilder()

		parser.element_start_handler = target.start
		parser.element_end_handler = target.end
		parser.character_data_handler = target.data

		self.target = target

	def feed(self, data):
		self._parser.parse(data)
