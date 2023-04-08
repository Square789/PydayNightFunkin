
import typing as t

from loguru import logger

from pyday_night_funkin.constants import BLACK, GAME_DIMENSIONS
from pyday_night_funkin.core.scene import BaseScene
from pyday_night_funkin.core.tween_effects.eases import linear
from pyday_night_funkin.core.utils import to_rgba_tuple

if t.TYPE_CHECKING:
	from pyday_night_funkin.main_game import Game


class TransitionScene(BaseScene):
	def __init__(
		self, game: "Game", is_in: bool, on_end: t.Optional[t.Callable[[], t.Any]] = None
	) -> None:
		super().__init__(game)

		self.update_passthrough = True

		a, b = (255, 0) if is_in else (0, 255)

		self.obscurer = self.create_object()
		self.obscurer.make_rect(to_rgba_tuple((BLACK & 0xFFFFFF00) | a), *GAME_DIMENSIONS)
		self.effects.tween(self.obscurer, {"opacity": b}, 0.6, on_complete=lambda _, c=on_end: c())

	def on_subscene_removal(self, sc: "BaseScene", *args, **kwargs) -> None:
		logger.info("Tunneling on_subscene_removal request")
		prev_scene = self.game.get_previous_scene(self)
		if prev_scene is None:
			logger.warning("Transition scene was first in scene stack?")
			self.game.remove_scene(sc)
		else:
			prev_scene.on_subscene_removal(sc, *args, **kwargs)
