
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.core.tween_effects.eases import in_out_elastic
from pyday_night_funkin.stages.common import BaseGameBaseStage

if t.TYPE_CHECKING:
	from pyday_night_funkin.character import Character


class TutorialStage(BaseGameBaseStage):
	def setup(self) -> None:
		super().setup()
		self.setup_default_base_game_arena()

	def create_opponent(self, char_cls: t.Type["Character"]) -> "Character":
		return self.create_object("girlfriend", "main", char_cls, scene=self, x=400, y=130)

	def ready(self) -> None:
		super().ready()
		# This behavior makes no sense whatsoever, but replicating it anyways!
		# Coordinates reconstructed from arcane float kung-fu in PlayState.hx
		x_orig = 600.0 if self.in_story_mode else 100.0
		self.main_cam.look_at(Vec2(
			x_orig + self.opponent.width * 0.5,
			100.0 + self.opponent.height * 0.5
		))
		if self.in_story_mode:
			self._tween_camera(1.3)

	def update(self, dt: float) -> None:
		# observe whether gf/bf focus changed and then run this goofy elastic tween
		_singer = self._last_followed_singer

		super().update(dt)

		if self._last_followed_singer != _singer:
			self._tween_camera(1.3 if self._last_followed_singer == 0 else 1.0)

	def _tween_camera(self, zoom: float) -> None:
		self.effects.remove_of(self.main_cam) # be safe
		self.effects.tween(
			self.main_cam,
			{"zoom": zoom},
			self.conductor.beat_duration / 1000.0,
			in_out_elastic,
		)

	def on_beat_hit(self) -> None:
		super().on_beat_hit()
		# The og game has the rules (16 < self.cur_beat < 48 and self.cur_beat and
		# self.cur_beat % 16 == 15) here, but that has gf fire a beat too late.
		# i'm gonna do this, watch:
		if self.cur_beat == 30 or self.cur_beat == 46:
			self.opponent.animation.play("cheer", True)
		elif self.cur_beat == 31 or self.cur_beat == 47:
			self.boyfriend.animation.play("hey", True)

	# The tutorial stage never ever zooms its cameras to not interfere with that godforsaken
	# elastic tween.
	# `process_input` is the only method setting that bool to `True`, so always disable it after.
	def process_input(self, dt: float) -> None:
		super().process_input(dt)
		self.zoom_cams = False
