
from random import randint
import typing as t

from pyglet.math import Vec2
from pyglet.window.key import (
	C, E, F, J, K, L, O, P, W, A, S, D, I, M, PLUS, MINUS, LEFT, DOWN, UP, RIGHT, X, Z
)
from pyday_night_funkin.base_game_pack import Boyfriend
from pyday_night_funkin.character import CharacterData
from pyday_night_funkin.core.asset_system import load_frames
from pyday_night_funkin.core.pnf_text import PNFText
from pyday_night_funkin.core.tween_effects.eases import out_cubic
from pyday_night_funkin.core.utils import to_rgba_tuple
from pyday_night_funkin.note import NoteType
from pyday_night_funkin.scenes.music_beat import MusicBeatScene

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.scene import SceneKernel
	from pyday_night_funkin.core.pnf_sprite import PNFSprite


class TestScene(MusicBeatScene):
	def __init__(self, kernel: "SceneKernel") -> None:
		super().__init__(kernel)

		self.lyr_background = self.create_layer()
		self.lyr_foreground = self.create_layer()
		self.lyr_forestground = self.create_layer()

		self.main_cam = self.create_camera()
		self.second_cam = self.create_camera(
			427, 240, self.game.dimensions[0] - 427, self.game.dimensions[1] - 240
		)
		center = Vec2(*self.game.dimensions) / 2.0
		self.second_cam.focus_center = center
		self.second_cam.zoom = 1/3
		self.second_cam.look_at(center)

		self.scroll_factor_tests = []
		for i in range(5):
			spr = self.create_object(
				self.lyr_background,
				(self.main_cam, self.second_cam),
				x = 800 + i*25,
				y = 100,
			)
			spr.make_rect(to_rgba_tuple((int(0xFFFFFF * (0.2 + i*0.15))) << 8 | 0xFF), 25, 25)
			spr.scroll_factor = (0.25 * i, 0.25 * i)
			self.scroll_factor_tests.append(spr)

		self.test_sprite = self.create_object(self.lyr_background, y=200)
		self.test_sprite.scale = 4

		self.conductor.bpm = 123

		note_sprites = load_frames("preload/images/NOTE_assets.xml")
		self.arrows: t.List["PNFSprite"] = []
		for i, note_type in enumerate(NoteType):
			atlas_names = note_type.get_atlas_names()
			s = self.create_object(self.lyr_background, x=300, y=50 + i*200)
			s.frames = note_sprites
			for anim_name, atlas_name in zip(("static", "pressed", "confirm"), atlas_names):
				s.animation.add_by_prefix(anim_name, atlas_name, 24, False)
			s.scale = 1.25 - i * .25
			s.animation.play("static")
			self.arrows.append(s)

		self._bf_camera = 1
		self.boyfriend = self.create_object(
			self.lyr_background,
			self.main_cam,
			Boyfriend,
			self,
			CharacterData(Boyfriend, "bf", "BOYFRIEND"),
			x = 770,
			y = 250,
		)
		self.boyfriend.animation._animations["idle"].loop = True # HACK
		self.boyfriend.animation.play("idle")
		# from pyday_night_funkin.core.animation import Animation
		# self.boyfriend.animation.delete_animations()
		# self.boyfriend.animation.add("ok", Animation([*range(len(self.boyfriend.frames.frames))], 24))
		# self.boyfriend.animation.play("ok")

		self.label = self.create_object(
			self.lyr_background,
			object_class = PNFText,
			x = 10,
			y = 200,
			text = "Cool FNF facts: Arrow animations are broken and require hardcoded offsets!",
			font_name = "Consolas",
			font_size = 12,
		)

		self.speen = self.create_object(self.lyr_background, x=256, y=386)
		self.wheee = self.create_object(self.lyr_background, (self.main_cam, self.second_cam))
		self.wheee.scale = 3.0
		self._wheee()

		self.instruction_label = self.create_object(
			self.lyr_foreground,
			object_class = PNFText,
			x = 8,
			y = 500,
			text = (
				"WASD+- to interact with the test sprite\n"
				"Hold C to spam smaller test sprites\n"
				"Hold P and WASDFMI to interact with Boyfriend\n"
				"           O to jump through cameras\n"
				"Arrow keys and ZX to move/zoom camera\n"
				"Arrow keys will push down strumline arrows. Hold E to make them glow instead\n"
				"JKL to interact with text\n"
			),
			multiline = True,
			font_name = "Consolas",
			font_size = 10,
		)

		self.live_reaction_w = self.create_object(self.lyr_background, self.second_cam)
		self.live_reaction_r = self.create_object(self.lyr_foreground, self.second_cam)
		self.live_reaction_t = self.create_object(
			self.lyr_forestground,
			self.second_cam,
			PNFText,
			text = "Live 2ND CAMERA reaction",
			font_name = "Consolas",
			font_size = 42,
		)
		self.live_reaction_w.make_rect(to_rgba_tuple(0xDFDFD3FF), 1280, 96)
		self.live_reaction_r.make_rect(to_rgba_tuple(0xA4051EFF), 1260, 84)
		self.live_reaction_r.position = (10, 6)
		self.live_reaction_t.position = (18, 8)
		self.live_reaction_t.scale_x = 1.5

	def _wheee(self) -> None:
		d = randint(30, 100) / 100
		self.effects.tween(
			self.wheee,
			{"x": randint(0, 1260)},
			d,
			out_cubic,
			lambda _: self.clock.schedule_once((lambda _: self._wheee()), randint(20, 50) / 50),
		)
		self.effects.tween(self.wheee, {"y": randint(0, 700)}, d, out_cubic)

	def update(self, dt: float) -> None:
		super().update(dt)

		self.speen.rotation += 0.6

		rkh = self.game.raw_key_handler

		if rkh[PLUS]:
			self.test_sprite.scale += 0.04
		if rkh[MINUS]:
			self.test_sprite.scale -= 0.04
		if rkh[W]:
			self.test_sprite.y -= 1
		if rkh[A]:
			self.test_sprite.x -= 1
		if rkh[S]:
			self.test_sprite.y += 1
		if rkh[D]:
			self.test_sprite.x += 1

		if rkh[P]:
			if rkh[F]:
				self.boyfriend.flip_x = not self.boyfriend.flip_x
			if rkh[W]:
				self.boyfriend.animation.play("sing_up")
			if rkh[A]:
				self.boyfriend.animation.play("sing_left")
			if rkh[S]:
				self.boyfriend.animation.play("sing_down")
			if rkh[D]:
				self.boyfriend.animation.play("sing_right")
			if rkh[M]:
				self.boyfriend.animation.play("miss_down")
			if rkh[I]:
				self.boyfriend.animation.play("idle")
			if rkh.just_pressed(O):
				c = []
				self._bf_camera = (self._bf_camera + 1) % 4
				if self._bf_camera & 1:
					c.append(self.main_cam)
				if self._bf_camera & 2:
					c.append(self.second_cam)
				self.boyfriend.set_context_cameras(c)

		confirm = rkh[E]
		for k, i in ((LEFT, 0), (DOWN, 1), (UP, 2), (RIGHT, 3)):
			self.arrows[i].animation.play(
				("confirm" if confirm else "pressed")
				if rkh[k] else "static"
			)

		if rkh[C]:
			sprite = self.create_object(self.lyr_foreground, x=randint(0, 100), y=randint(0, 100))
			sprite.start_movement(Vec2(10, 5))
			self.effects.tween(sprite, {"opacity": 0}, 2.0, on_complete=self.remove)

		if rkh[LEFT]:
			self.main_cam.x -= 10
		if rkh[RIGHT]:
			self.main_cam.x += 10
		if rkh[DOWN]:
			self.main_cam.y += 10
		if rkh[UP]:
			self.main_cam.y -= 10
		if rkh[Z]:
			self.main_cam.zoom += .01
		if rkh[X]:
			self.main_cam.zoom -= .01

		if rkh[J]:
			self.label.rotation += .1
		if rkh[K]:
			self.label.x -= 1
			# self.label.text = self.label.text[:-1]
		if rkh[L]:
			self.label.x += 1
			# self.label.text += "!"
