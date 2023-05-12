
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin.core.tween_effects.eases import in_out_elastic
from pyday_night_funkin.scenes.in_game import CharacterAnchor, InGameSceneKernel
from pyday_night_funkin.stages.common import BaseGameBaseStage


class TutorialStage(BaseGameBaseStage):
	def __init__(self, kernel: InGameSceneKernel, *args, **kwargs) -> None:
		from pyday_night_funkin.scenes.in_game import CharacterAnchor
		super().__init__(
			kernel.fill(opponent_anchor=CharacterAnchor(Vec2(400, 130), None, "girlfriend")),
			*args,
			**kwargs,
		)

		self.spawn_default_base_game_arena()

	def ready(self) -> None:
		super().ready()
		# This behavior makes no sense whatsoever, but replicating it anyways!
		# Coordinates reconstructed from arcane float kung-fu in PlayState.hx
		if self.in_story_mode:
			self.main_cam.x += 500.0
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
