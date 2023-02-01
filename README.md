# PydayNightFunkin
 This is a rewrite of (accidentally half of HaxeFlixel and) Friday Night Funkin' in python and some Cython. Why? "Beep boop funny", camelCase looks ugly and as a proof to no-one that the `PlayState.hx` monolith is the worst, that would be why.  
 Not a lot is done, but you can at least click through some menus and partake in a few non-recorded vowel-screaming contests.

## Used libraries:  
  - pyglet ([Github](https://www.github.com/pyglet/pyglet))
  - stb_vorbis ([Github](https://github.com/nothings/stb/blob/master/stb_vorbis.c) | [Homepage](https://nothings.org/stb_vorbis))
  - loguru ([Github](https://github.com/Delgan/loguru))
  - schema ([Github](https://github.com/keleshev/schema))
  - *Cython* ([Homepage](https://cython.org/))
  - *opengl-registry* ([Github](https://github.com/moderngl/opengl-registry))

## How to run?
 I'm honored you want to try this out, because there's really nothing revolutionary in here. Anyways:

 - You will need OpenGL 4.5 support on your system, cause DSA was just too sweet to not use.
 - You will need python (3.11 is recommended due to its speed advantages, but anything starting from 3.8 should work).
 - Ensure that python can build C extensions/you have a C compiler set up.
 - Then, run these commands (which I didn't test and which may look different; e.g. `python3` or `py` instead of `python`):
```bash
# Clone the repo somewhere (could also be done by downloading the repo as #
#    .zip via the Code > Download ZIP button and then extracting that.)   #
cd somewhere/stuff
git clone https://github.com/Square789/PydayNightFunkin.git
cd PydayNightFunkin

#     (Optional, but strongly recommended)     #
# Set up a virtual environment and activate it #
python3 -m venv pnfvenv
pnfvenv/Scripts/activate

# Get the build dependencies and build the needed extensions #
python3 -m pip install -r requirements_build.txt
python setup.py build_ext -i

# Get the other dependencies #
python3 -m pip install -r requirements.txt

# Run #
python3 run.py
```
