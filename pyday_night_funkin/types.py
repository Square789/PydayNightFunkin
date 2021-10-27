
import typing as t

if t.TYPE_CHECKING:
	from pyday_night_funkin.graphics import PNFSprite


PNFSpriteBound = t.TypeVar("PNFSpriteBound", bound="PNFSprite")
Numeric = t.Union[int, float]
