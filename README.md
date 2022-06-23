# PydayNightFunkin
 This is a rewrite of (accidentally half of HaxeFlixel and) Friday Night Funkin' in python and some Cython. Why? "Beep boop funny", camelCase looks ugly and as a proof to no-one that the `PlayState.hx` monolith is the worst, that would be why.  
 Not a lot is done, but you can at least click through some menus and partake in a few non-recorded, non-penalized vowel-screaming contests.

## Used libraries:  
  - pyglet ([Github](https://www.github.com/pyglet/pyglet))
  - stb_vorbis ([Github](https://github.com/nothings/stb/blob/master/stb_vorbis.c) | [Homepage](https://nothings.org/stb_vorbis))
  - loguru ([Github](https://github.com/Delgan/loguru))
  - schema ([Github](https://github.com/keleshev/schema))
  - *Cython* ([Homepage](https://cython.org/))
  - *opengl-registry* ([Github](https://github.com/moderngl/opengl-registry))

## How to run?
 I'm honored you want to try this out, because there's really nothing revolutionary in here. Anyways:

 First of all, ensure that python can build C extensions/you have a C compiler set up.  
 Then, run these commands (whose correctness I didn't test):
```bash
# Clone the repo somewhere #
cd somewhere/stuff
git clone https://github.com/Square789/PydayNightFunkin.git
cd PydayNightFunkin

# (Optional, but recommended) Set up a virtual environment and activate it #
python -m venv pnfvenv
pnfvenv/Scripts/activate

# Get the build dependencies #
python -m pip install -r requirements_build.txt

# Build the needed extensions #
python setup.py build_ext -i

# Get the other dependencies #
python -m pip install -r requirements.txt

# Run #
python run.py
```
