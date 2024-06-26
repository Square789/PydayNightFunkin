
from itertools import product
from random import randint
import typing as t

from pyday_night_funkin import constants as CNST
from pyday_night_funkin.core.asset_system import load_frames, load_image, load_sound
from pyday_night_funkin.core.pnf_text import TextAlignment, PNFText
from pyday_night_funkin.core.tween_effects.eases import in_out_cubic, out_cubic
from pyday_night_funkin.enums import AnimationTag
from pyday_night_funkin.health_bar import HealthBar
from pyday_night_funkin.note import NoteType, Rating

if t.TYPE_CHECKING:
	from pyday_night_funkin.core.camera import Camera
	from pyday_night_funkin.core.scene import SceneLayer
	from pyday_night_funkin.core.pnf_sprite import PNFSprite
	from pyday_night_funkin.scenes import InGameScene


class HUD:
	"""
	HUD class containing a bunch of HUD sprites and functions
	to modify them.
	"""
	def __init__(self, scene: "InGameScene", camera: "Camera", layer: "SceneLayer") -> None:
		self._scene = scene
		self.camera = camera
		self.layer = layer

		self.lyr_combo = scene.create_layer(True, layer)
		self.lyr_arrows = scene.create_layer(False, layer)
		self.lyr_notes = scene.create_layer(False, layer)
		self.lyr_health_bar = scene.create_layer(True, layer)

		self.countdown_textures = (
			None,
			load_image("shared/images/ready.png"),
			load_image("shared/images/set.png"),
			load_image("shared/images/go.png"),
		)

		self.countdown_sounds = (
			load_sound("shared/sounds/intro3.ogg"),
			load_sound("shared/sounds/intro2.ogg"),
			load_sound("shared/sounds/intro1.ogg"),
			load_sound("shared/sounds/introGo.ogg"),
		)

		self.note_rating_textures = {
			Rating.SICK: load_image("shared/images/sick.png"),
			Rating.GOOD: load_image("shared/images/good.png"),
			Rating.BAD: load_image("shared/images/bad.png"),
			Rating.SHIT: load_image("shared/images/shit.png"),
		}

		self.number_textures = [load_image(f"preload/images/num{i}.png") for i in range(10)]
		note_sprites = load_frames("preload/images/NOTE_assets.xml")

		self.static_arrows: t.List[t.Dict[NoteType, "PNFSprite"]] = [{}, {}]
		for i, note_type in product((0, 1), NoteType):
			atlas_names = note_type.get_atlas_names()
			arrow_sprite = self._scene.create_object(
				self.lyr_arrows,
				self.camera,
				x = 50 + (CNST.GAME_WIDTH // 2) * i + (note_type.get_order() * CNST.NOTE_WIDTH),
				y = CNST.STATIC_ARROW_Y,
			)
			arrow_sprite.frames = note_sprites
			for anim_name, atlas_name, tag in zip(
				("static", "pressed", "confirm"),
				atlas_names,
				(AnimationTag.STATIC, AnimationTag.PRESSED, AnimationTag.CONFIRM),
			):
				arrow_sprite.animation.add_by_prefix(anim_name, atlas_name, 24, False, tags=(tag,))
			arrow_sprite.set_scale_and_repos(.7)
			arrow_sprite.animation.play("static")
			self.static_arrows[i][note_type] = arrow_sprite

		char_reg = self._scene.game.character_registry
		self.health_bar = HealthBar(
			scene,
			self.camera,
			char_reg[self._scene.level_data.opponent_character].get_icon_name(),
			char_reg[self._scene.level_data.player_character].get_icon_name(),
			self.lyr_health_bar,
		)

		self.score_text = scene.create_object(
			self.lyr_combo,
			self.camera,
			PNFText,
			x = self.health_bar.background.x + self.health_bar.background.width - 190,
			y = self.health_bar.background.y + 30,
			text = "",
			font_size = 16,
			font_name = "VCR OSD Mono",
			align = TextAlignment.RIGHT,
		)

	def get_note_layer(self) -> "SceneLayer":
		# TODO ducttape method, will try and separate processing/drawing later
		return self.lyr_notes

	def update_health(self, health: float) -> None:
		self.health_bar.update(health)

	def update_score(self, new_score: int) -> None:
		self.score_text.text = f"Score:{new_score}"

	def combo_popup(self, rating: Rating, combo: int) -> None:
		"""
		Pops up sprites to notify of a combo and a note hit rating.
		"""
		x = int(CNST.GAME_WIDTH * .55)
		scene = self._scene

		combo_sprite = scene.create_object(
			self.lyr_combo,
			self.camera,
			image = self.note_rating_textures[rating],
		)
		combo_sprite.screen_center(CNST.GAME_DIMENSIONS)
		combo_sprite.position = (x - 40, combo_sprite.y - 60)
		combo_sprite.scale = 0.7

		combo_sprite.start_movement((0, -150), (0, 600))

		# NOTE: Maybe get a cleaner way of delaying the removal tween in here
		scene.clock.schedule_once(
			lambda _, combo_sprite=combo_sprite: scene.effects.tween(
				combo_sprite,
				{"opacity": 0},
				0.2,
				out_cubic,
				scene.remove,
			),
			scene.conductor.beat_duration * 0.001,
		)

		for i, digit in enumerate(f"{combo:>03}"):
			sprite = scene.create_object(
				self.lyr_combo,
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
				lambda _, sprite=sprite: scene.effects.tween(
					sprite,
					{"opacity": 0},
					0.2,
					on_complete=scene.remove,
				),
				scene.conductor.beat_duration * 0.002,
			)

	def countdown_popup(self, countdown_stage: int) -> None:
		"""
		Pops up a countdown sprite for the given countdown stage.
		"""
		scene = self._scene
		tex = self.countdown_textures[countdown_stage]
		if tex is not None:
			sprite = scene.create_object(self.lyr_combo, self.camera, image=tex)
			sprite.screen_center(CNST.GAME_DIMENSIONS)
			scene.effects.tween(
				sprite,
				{"opacity": 0},
				scene.conductor.beat_duration * 0.001,
				in_out_cubic,
				scene.remove,
			)

		if self.countdown_sounds[countdown_stage] is not None:
			scene.sfx_ring.play(self.countdown_sounds[countdown_stage])

	def arrow_static(self, type_: NoteType) -> None:
		if not self.static_arrows[1][type_].animation.has_tag(AnimationTag.STATIC):
			self.static_arrows[1][type_].animation.play("static")

	def arrow_pressed(self, type_: NoteType) -> None:
		if self.static_arrows[1][type_].animation.has_tag(AnimationTag.STATIC):
			self.static_arrows[1][type_].animation.play("pressed")

	def arrow_confirm(self, type_: NoteType) -> None:
		self.static_arrows[1][type_].animation.play("confirm", True)
