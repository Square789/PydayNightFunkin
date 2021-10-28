
import random
import typing as t

from pyglet.media import Player

from pyday_night_funkin.alphabet import create_text_line
from pyday_night_funkin.asset_system import ASSETS, load_asset
from pyday_night_funkin.config import CONTROL
from pyday_night_funkin import constants as CNST
from pyday_night_funkin.scenes.mainmenu import MainMenuScene
from pyday_night_funkin.scenes.music_beat import MusicBeatScene

if t.TYPE_CHECKING:
	from pyday_night_funkin.alphabet import AlphabetCharacter


class TitleScene(MusicBeatScene):
	def __init__(self, *args, **kwargs) -> None:
		super().__init__(*args, **kwargs)

		gf_frames = load_asset(ASSETS.XML.TITLE_GIRLFRIEND)["gfDance"]
		self.gf = self.create_sprite("main", x=CNST.GAME_WIDTH * 0.4, y=CNST.GAME_HEIGHT * 0.07)
		self.gf.animation.add_by_indices("dance_left", gf_frames, [*range(15)], 24, False)
		self.gf.animation.add_by_indices("dance_right", gf_frames, [*range(15, 30)], 24, False)
		self.gf.visible = False

		self.gf_dance_left = False

		logo_frames = load_asset(ASSETS.XML.GAME_LOGO)["logo bumpin"]
		self.logo = self.create_sprite("main", x=-150, y=-100)
		self.logo.animation.add_from_frames("bump", logo_frames)
		self.logo.visible = False

		title_anims = load_asset(ASSETS.XML.TITLE_ENTER)
		self.title_text = self.create_sprite("title_text", x=100, y=CNST.GAME_HEIGHT * 0.8)
		self.title_text.animation.add_from_frames(
			"idle", title_anims["Press Enter to Begin"], 24, True
		)
		self.title_text.animation.add_from_frames(
			"enter", title_anims["ENTER PRESSED"], 24, True
		)
		self.title_text.animation.play("idle")
		self.title_text.visible = False

		ng_logo = load_asset(ASSETS.IMG.NEWGROUNDS_LOGO)
		self.ng_logo = self.create_sprite("main", image=ng_logo, y=CNST.GAME_HEIGHT * 0.52)
		self.ng_logo.scale = 0.8
		self.ng_logo.screen_center(CNST.GAME_DIMENSIONS, y=False)
		self.ng_logo.visible = False

		intro_texts = [*filter(None, load_asset(ASSETS.TXT.INTRO_TEXT).split("\n"))]
		chosen = random.choice(intro_texts).split("--")
		self.intro_text = [chosen[0], ""] if len(chosen) < 2 else chosen

		self.confirm_sound = load_asset(ASSETS.SOUND.MENU_CONFIRM)

		self.conductor.bpm = 102
		self.player = Player()
		self.player.queue(load_asset(ASSETS.MUSIC.MENU))
		self.player.play()

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
				setattr(self.ng_logo, "visible", True)
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
	def get_layer_names() -> t.Sequence[t.Union[str, t.Tuple[str, bool]]]:
		return ("main", "title_text")

	def _create_text(self, *lines: str) -> None:
		for line in lines:
			container = create_text_line(
				line,
				self,
				"main",
				bold = True,
				color = (255, ) * 3,
				y = len(self.text_lines) * 60 + 200,
			)

			container.screen_center(CNST.GAME_DIMENSIONS, y=False)
			self.text_lines.append(container)

	def _delete_text(self):
		for container in self.text_lines:
			for s in container:
				self.remove_sprite(s)
		self.text_lines = []

	def _intro_end(self):
		if self._intro_ended:
			return

		self.remove_sprite(self.ng_logo)
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
			self.player.pause()
			self.game.set_scene(MainMenuScene)

		delay = .5 if self.game.debug else 2.0
		self.clock.schedule_once(_cb, delay)

	def on_beat_hit(self) -> None:
		super().on_beat_hit()

		self.logo.animation.play("bump")
		self.gf_dance_left = not self.gf_dance_left
		self.gf.animation.play("dance_left" if self.gf_dance_left else "dance_right")

		if not self._intro_ended:
			if self.cur_beat in self._BEAT_FUNCS:
				self._BEAT_FUNCS[self.cur_beat]()

	def update(self, dt: float) -> None:
		# NOTE: 5 IQ song tracking
		self.conductor.song_position = self.player.time * 1000

		if self.game.key_handler.just_pressed(CONTROL.ENTER):
			if not self._intro_ended:
				self._intro_end()
			elif not self._leaving_scene:
				self._leave_scene()

		super().update(dt)
