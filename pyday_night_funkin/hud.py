
from itertools import product
from random import randint
import re
import typing as t

from pyglet.math import Vec2

from pyday_night_funkin import constants as CNST
from pyday_night_funkin.core.asset_system import load_asset, ASSET
from pyday_night_funkin.core.pnf_text import ALIGNMENT, PNFText
from pyday_night_funkin.core.tweens import TWEEN_ATTR, in_out_cubic, linear, out_cubic
from pyday_night_funkin.enums import ANIMATION_TAG
from pyday_night_funkin.health_bar import HealthBar
from pyday_night_funkin.note import NOTE_TYPE, RATING

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.animation.frames import FrameCollection
	from pyday_night_funkin.core.pnf_sprite import PNFSprite
	from pyday_night_funkin.scenes import InGameScene


class HUD():
	"""
	HUD class containing a bunch of HUD sprites and functions
	to modify them.
	"""
	def __init__(
		self,
		scene: "InGameScene",
		camera: str,
		layer: str,
		arrow_layer: str,
		health_bar_layers: t.Tuple[str, str, str],
		combo_layer: str,
	) -> None:
		self._scene = scene
		self.camera = camera
		self.layer = layer
		self.arrow_layer = arrow_layer
		self.health_bar_layers = health_bar_layers
		self.combo_layer = combo_layer

		self.countdown_textures = (
			None,
			load_asset(ASSET.IMG_READY),
			load_asset(ASSET.IMG_SET),
			load_asset(ASSET.IMG_GO),
		)

		self.countdown_sounds = (
			load_asset(ASSET.SOUND_INTRO_3),
			load_asset(ASSET.SOUND_INTRO_2),
			load_asset(ASSET.SOUND_INTRO_1),
			load_asset(ASSET.SOUND_INTRO_GO),
		)

		self.note_rating_textures = {
			RATING.SICK: load_asset(ASSET.IMG_SICK),
			RATING.GOOD: load_asset(ASSET.IMG_GOOD),
			RATING.BAD: load_asset(ASSET.IMG_BAD),
			RATING.SHIT: load_asset(ASSET.IMG_SHIT),
		}

		self.number_textures = [load_asset(getattr(ASSET, f"IMG_NUM{i}")) for i in range(10)]

		# HACK: This manipulates the cached note asset frame collection, since notes have
		# botched offsets that are fixed with a hardcoded center->subtract in the main loop.
		# Nobody wants that, so we hack in some offsets right here.
		# Both were probably found by trial-and-error, so good enough (TM)
		note_sprites: "FrameCollection" = load_asset(ASSET.XML_NOTES)
		for frame in note_sprites.frames:
			if re.search(r"confirm\d+$", frame.name) is not None:
				frame.offset -= Vec2(39, 39)

		self.static_arrows: t.List[t.Dict[NOTE_TYPE, "PNFSprite"]] = [{}, {}]
		for i, note_type in product((0, 1), NOTE_TYPE):
			atlas_names = note_type.get_atlas_names()
			arrow_sprite = self._scene.create_object(
				self.arrow_layer,
				self.camera,
				x = 50 + (CNST.GAME_WIDTH // 2) * i + (note_type.get_order() * CNST.NOTE_WIDTH),
				y = CNST.STATIC_ARROW_Y,
			)
			arrow_sprite.frames = note_sprites
			for anim_name, atlas_name, tag in zip(
				("static", "pressed", "confirm"),
				atlas_names,
				(ANIMATION_TAG.STATIC, ANIMATION_TAG.PRESSED, ANIMATION_TAG.CONFIRM),
			):
				arrow_sprite.animation.add_by_prefix(anim_name, atlas_name, 24, False, tags=(tag,))
			arrow_sprite.set_scale_and_repos(.7)
			arrow_sprite.animation.play("static")
			self.static_arrows[i][note_type] = arrow_sprite

		self.health_bar = HealthBar(
			scene,
			self.camera,
			self._scene.get_opponent_icon(),
			self._scene.get_player_icon(),
			self.health_bar_layers,
		)

		load_asset(ASSET.FONT_VCR)
		self.score_text = scene.create_object(
			self.health_bar_layers[0],
			self.camera,
			PNFText,
			x = self.health_bar.background.x + self.health_bar.background.width - 190,
			y = self.health_bar.background.y + 30,
			text = "",
			font_size = 16,
			font_name = "VCR OSD Mono",
			align = ALIGNMENT.RIGHT,
		)

	def update_health(self, health: float) -> None:
		self.health_bar.update(health)

	def update_score(self, new_score: int) -> None:
		self.score_text.text = f"Score:{new_score}"

	def combo_popup(self, rating: RATING, combo: int) -> None:
		"""
		Pops up sprites to notify of a combo and a note hit rating.
		"""
		x = int(CNST.GAME_WIDTH * .55)
		scene = self._scene

		combo_sprite = scene.create_object(
			self.combo_layer,
			self.camera,
			image = self.note_rating_textures[rating],
		)
		combo_sprite.screen_center(CNST.GAME_DIMENSIONS)
		combo_sprite.position = (x - 40, combo_sprite.y - 60)
		combo_sprite.scale = 0.7

		combo_sprite.start_movement((0, -150), (0, 600))

		# NOTE: Maybe get a cleaner way of delaying the removal tween in here
		scene.clock.schedule_once(
			lambda _, combo_sprite=combo_sprite: combo_sprite.start_tween(
				tween_func = out_cubic,
				attributes = {TWEEN_ATTR.OPACITY: 0},
				duration = 0.2,
				on_complete = lambda: scene.remove(combo_sprite),
			),
			scene.conductor.beat_duration * 0.001,
		)

		for i, digit in enumerate(f"{combo:>03}"):
			sprite = scene.create_object(
				self.combo_layer,
				self.camera,
				image = self.number_textures[int(digit)],
			)
			sprite.screen_center(CNST.GAME_DIMENSIONS)
			sprite.position = (x + (43 * i) - 90, sprite.y + 80)
			sprite.scale = .5

			sprite.start_movement(
				(randint(-5, 5), -randint(140, 160)), (0, randint(200, 300))
			)

			scene.clock.schedule_once(
				lambda _, sprite=sprite: sprite.start_tween(
					tween_func = linear,
					attributes = {TWEEN_ATTR.OPACITY: 0},
					duration = 0.2,
					on_complete = lambda: scene.remove(sprite),
				),
				scene.conductor.beat_duration * 0.002,
			)

	def countdown_popup(self, countdown_stage: int):
		"""
		Pops up a countdown sprite for the given countdown stage.
		"""
		scene = self._scene
		tex = self.countdown_textures[countdown_stage]
		if tex is not None:
			sprite = scene.create_object(self.combo_layer, self.camera, image=tex)
			sprite.screen_center(CNST.GAME_DIMENSIONS)
			sprite.start_tween(
				in_out_cubic,
				{TWEEN_ATTR.OPACITY: 0},
				scene.conductor.beat_duration * 0.001,
				lambda sprite = sprite: scene.remove(sprite),
			)

		if self.countdown_sounds[countdown_stage] is not None:
			scene.sfx_ring.play(self.countdown_sounds[countdown_stage])

	def arrow_static(self, type_: NOTE_TYPE) -> None:
		if not self.static_arrows[1][type_].animation.has_tag(ANIMATION_TAG.STATIC):
			self.static_arrows[1][type_].animation.play("static")

	def arrow_pressed(self, type_: NOTE_TYPE) -> None:
		if self.static_arrows[1][type_].animation.has_tag(ANIMATION_TAG.STATIC):
			self.static_arrows[1][type_].animation.play("pressed")

	def arrow_confirm(self, type_: NOTE_TYPE) -> None:
		self.static_arrows[1][type_].animation.play("confirm", True)
