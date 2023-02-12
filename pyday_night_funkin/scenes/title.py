
import random
import typing as t

from pyday_night_funkin.alphabet import TextLine
from pyday_night_funkin import constants as CNST
from pyday_night_funkin.base_game_pack import load_frames
from pyday_night_funkin.core.asset_system import load_image, load_sound, load_text
from pyday_night_funkin.core.tweens import linear
from pyday_night_funkin.core.utils import to_rgba_tuple
from pyday_night_funkin.enums import CONTROL
from pyday_night_funkin import scenes

if t.TYPE_CHECKING:
	from pyday_night_funkin.alphabet import AlphabetCharacter


class TitleScene(scenes.MusicBeatScene):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		self.gf = self.create_object("main", x=CNST.GAME_WIDTH * 0.4, y=CNST.GAME_HEIGHT * 0.07)
		self.gf.frames = load_frames("preload/images/gfDanceTitle.xml")
		self.gf.animation.add_by_indices("dance_left", "gfDance", [*range(15)], 24, False)
		self.gf.animation.add_by_indices("dance_right", "gfDance", [*range(15, 30)], 24, False)
		self.gf.visible = False

		self.gf_dance_left = False

		self.logo = self.create_object("main", x=-150, y=-100)
		self.logo.frames = load_frames("preload/images/logoBumpin.xml")
		self.logo.animation.add_by_prefix("bump", "logo bumpin", 24, False)
		self.logo.animation.play("bump")
		self.logo.visible = False

		self.title_text = self.create_object("title_text", x=100, y=CNST.GAME_HEIGHT * 0.8)
		self.title_text.frames = load_frames("preload/images/titleEnter.xml")
		self.title_text.animation.add_by_prefix("idle", "Press Enter to Begin", 24)
		self.title_text.animation.add_by_prefix("enter", "ENTER PRESSED", 24)
		self.title_text.animation.play("idle")
		self.title_text.visible = False

		ng_logo = load_image("preload/images/newgrounds_logo.png")
		self.ng_logo = self.create_object("main", image=ng_logo, y=CNST.GAME_HEIGHT * 0.52)
		self.ng_logo.set_scale_and_repos(.8)
		self.ng_logo.screen_center(CNST.GAME_DIMENSIONS, y=False)
		self.ng_logo.visible = False

		intro_texts = [*filter(None, load_text("preload/data/introText.txt").split("\n"))]
		chosen = random.choice(intro_texts).split("--")
		self.intro_text = [chosen[0], ""] if len(chosen) < 2 else chosen

		self.confirm_sound = load_sound("preload/sounds/confirmMenu.ogg")

		self.conductor.bpm = 102 #420
		self.game.player.set(load_sound("preload/music/freakyMenu.ogg"))
		self.game.player.loop = True
		self.sync_conductor_from_player(self.game.player)

		self._intro_ended = False
		self._leaving_scene = False

		self.text_lines: t.List[t.List["AlphabetCharacter"]] = []

		self._BEAT_FUNCS = {
			1: lambda: self._create_text("original game by"),
			2: lambda: self._create_text(
				"ninjamuffin99", "phantomArcade", "kawaisprite", "evilsk8er"
			),
			4: self._delete_text,
			5: lambda: (
				self._create_text("In association", "with", "newgrounds"),
				setattr(self.ng_logo, "visible", True),
			),
			7: lambda: (self._delete_text(), setattr(self.ng_logo, "visible", False)),
			8: lambda: self._create_text("Python rewrite by"),
			9: lambda: self._create_text("Square789"),
			11: self._delete_text,
			12: lambda: self._create_text(self.intro_text[0]),
			13: lambda: self._create_text(self.intro_text[1]),
			# 13: lambda: self._create_text("Friday"),
			# 14: lambda: self._create_text("Night"),
			# 15: lambda: self._create_text("Funkin"), # No cool title sadly
			15: self._delete_text,
			16: self._intro_end,
		}

	@staticmethod
	def get_default_layers() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("main", "title_text", "flash")

	def _create_text(self, *lines: str) -> None:
		for line in lines:
			container = TextLine(
				line,
				bold = True,
				color = (255,) * 3,
				y = len(self.text_lines) * 60 + 200,
			)

			container.screen_center(CNST.GAME_DIMENSIONS, y=False)
			self.text_lines.append(container)
			self.add(container, "title_text")

	def _delete_text(self):
		for container in self.text_lines:
			self.remove(container)
		self.text_lines = []

	def _intro_end(self):
		if self._intro_ended:
			return

		self.remove(self.ng_logo)
		self._delete_text()
		self.gf.visible = True
		self.logo.visible = True
		self.title_text.visible = True
		self._intro_ended = True

	def _leave_scene(self):
		if self._leaving_scene:
			return

		self._leaving_scene = True
		self.title_text.animation.play("enter")
		self.sfx_ring.play(self.confirm_sound)

		def _cb(_):
			self.game.set_scene(scenes.MainMenuScene)
		delay = 0.5 if self.game.debug else 2.0
		self.clock.schedule_once(_cb, delay)

		# flash = self.create_object("flash")
		# flash.make_rect(to_rgba_tuple(0xFFFFFFFF), CNST.GAME_WIDTH, CNST.GAME_HEIGHT)
		# flash.opacity = 255
		# flash.start_tween(linear, {"opacity": 0.0}, 1.0)

	def on_beat_hit(self) -> None:
		super().on_beat_hit()

		self.logo.animation.play("bump")
		self.gf_dance_left = not self.gf_dance_left
		self.gf.animation.play("dance_left" if self.gf_dance_left else "dance_right")

		if not self._intro_ended:
			if self.cur_beat in self._BEAT_FUNCS:
				self._BEAT_FUNCS[self.cur_beat]()

	def update(self, dt: float) -> None:
		if self.game.key_handler.just_pressed(CONTROL.ENTER):
			if not self._intro_ended:
				self._intro_end()
			elif not self._leaving_scene:
				self._leave_scene()

		super().update(dt)
