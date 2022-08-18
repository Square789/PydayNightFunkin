
from xml.etree.ElementTree import TreeBuilder

from .almost_xml_parser import AlmostXMLParser as _AXP


class AlmostXMLParser:
	def __init__(self, *, target = None) -> None:
		self._parser = parser = _AXP()

		if target is None:
			target = TreeBuilder()

		parser.element_start_handler = target.start
		parser.element_end_handler = target.end
		parser.character_data_handler = target.data
		if hasattr(target, "pi"):
			parser.processing_instruction_handler = target.pi
		if hasattr(target, "comment"):
			parser.comment_handler = target.comment

		self.target = target

	def feed(self, data):
		self._parser.feed(data)

	def close(self):
		self._parser.close()
		if hasattr(self.target, "close"):
			return self.target.close()
		return None
