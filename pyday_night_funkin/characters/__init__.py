
from ._base import Character
from .boyfriend import Boyfriend
from .daddy_dearest import DaddyDearest
from .girlfriend import Girlfriend

# Honestly just doing this so pylance shuts up, star import bad idea
__all__ = ["Character", "Boyfriend", "DaddyDearest", "Girlfriend"]
