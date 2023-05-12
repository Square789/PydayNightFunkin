# PydayNightFunkin
 This is a rewrite of (accidentally half of HaxeFlixel and) Friday Night Funkin' in Python and
 some Cython.

 Why? "Beep boop funny", camelCase looks ugly and as a proof to no-one that the `PlayState.hx`
 monolith is the worst, that would be why.  
 Not a lot is done, but you can at least click through some menus and partake in a few
 non-recorded vowel-screaming contests.

## Used libraries
  - pyglet ([Github](https://www.github.com/pyglet/pyglet))
  - stb_vorbis ([Github](https://github.com/nothings/stb/blob/master/stb_vorbis.c) |
    [Homepage](https://nothings.org/stb_vorbis))
  - loguru ([Github](https://github.com/Delgan/loguru))
  - schema ([Github](https://github.com/keleshev/schema))
  - *Cython* ([Homepage](https://cython.org/))
  - *opengl-registry* ([Github](https://github.com/moderngl/opengl-registry))

## Why would you want this?
 A good question! The answer is: You probably don't! Here's some pros and cons:
### Pros
 - **Starts quickly**; Changes to Python files are visible far more quickly than changes
   made to Haxe as Python bytecode typically beats html5/hxcpp compilation times.
 - **Significantly cleaner code** than most engines i have seen so far due to an attempt at
   documentation and logically separating stages instead of mashing them together into a
   5000 line long PlayState file.
### Cons
 - **Runs slowly**; due to Python's interpreted nature, PNF runs ~20-50 times slower than
   FNF's compiled C++ code and ~1-4 times as slow as html5 builds, though this is still fast
   enough to not scrape the fabled 16ms 60FPS ceiling.
 - **Does not run in a web browser**; The OpenGL variants are quite different from what i get, and
   Pyglet does not target anything else than desktop.
   - There have been experiments, but those will definitely remain experiments for the foreseeable
     future.
 - This is a **complete hobby project** that's still in development and rapidly breaks stuff.
 - **Still lacks many many features** such as: Save data, asset cache clearing, scene transitions,
   a loading screen, options, a chart editor, any kind of comprehensive modding frontend, an
   accuracy system and tightly timed input detection that doesn't risk lagging behind by up to
   16ms.

## Boring! Show me a video!
 Soon™

## How to run?
 I'm honored you want to try this out, because there's really nothing revolutionary in here.
 Anyways:

### 0. Prerequisites
 - You will need OpenGL 4.5 support on your system, cause the Direct State Access mechanism it
   introduced was just too sweet to not use.
   - This makes PNF incompatible with apple devices cause they decided OpenGL 4.5 wasn't good
     enough for them anymore. I did create a [4_1-compat branch](https://github.com/Square789/PydayNightFunkin/tree/gl4_1-compat)
     for that, however don't really care much about updating it, meaning it's likely far behind
     main, so you'll need to update it on your own.
 - You will need Python.
   - I recommend getting it from [its official website](https://www.python.org/downloads/). I
     have seen the windows store version cause weird access restriction problems when installing
     packages, though this likely was just a case of a system possessed by some sort of spirit.
   - 3.11 is definitely recommended due to its speed advantages, but anything starting from 3.8
     should work.
 - Ensure that Python can build C extensions; that is: you have a C compiler set up.
   - I am sorry to disappoint if you thought Python meant not having to deal with that. PNF gets
     some of its speed and capabilities from custom C extensions.
   - If on Windows, you will need Visual Studio; the required packages and versions are difficult
     to pinpoint and unlikely to remain stable over longer time periods. [This wiki entry](https://wiki.python.org/moin/WindowsCompilers#Compilers_Installation_and_configuration)
     seems to have somewhat up-to-date information on what you'll need.

 Now, run the commands below.  
 **NOTE**: If `python3` fails, try `python` or `py` instead, the name may differ depending on
 your OS and Python variants.

### 1A. Clone the repo | Option A (Requires [git](https://git-scm.com/))
 Create and/or choose a directory where the project fits well. (`Code/python`,
 `Documents/experiments`, `Games/pnf`, `test`, the possibilities are endless.)  
 Then, open a terminal in it and clone the repository:
```bat
git clone https://github.com/Square789/PydayNightFunkin.git
cd PydayNightFunkin
```

### 1B. Clone the repo | Option B
 Download the source via the Code > Download ZIP button on top of the page and extract that
 somewhere it fits well, then open a terminal inside the directory containing `README.md` (among
 other files).

### 2. Set up and activate a virtual environment
 This step is optional, but heavily recommended. If you skip it, your global Python installation
 will be cluttered with a bunch of libraries and PNF might break should these ever change by the
 requirements of other projects.  
 You will need to activate this venv every time you want to run PNF. If on Linux,
 [pyenv](https://github.com/pyenv/pyenv) alongside the `pyenv-virtualenv` plugin is my choice to
 automate this, on Windows it's usually IDEs such as Visual Studio Code that will automatically
 run the activation command when opening the project.
```bat
python3 -m venv pnfvenv
pnfvenv/Scripts/activate
```
 **NOTE**: The activation command of a venv depends on your OS and shell.
 [See this page](https://docs.python.org/3/library/venv.html#how-venvs-work) for a few ways
 of doing it.

### 3. Get the build dependencies and build the C extensions
```bat
python3 -m pip install -r requirements_build.txt
python3 setup.py build_ext -i
```
 **NOTE**: This step may fail in many unpredictable and nasty ways. If that happens, please
 send me a friend request on discord at `Square789#0486` (not too sure whether that actually
 works), or [open an issue](https://github.com/Square789/PydayNightFunkin/issues/new).  
 I'll try my best to help with anything.

### 4. Get the runtime dependencies
```bat
python3 -m pip install -r requirements.txt
```

### 5. Run
 ```bat
 python3 run.py
 ```
 **NOTE**: PydayNightFunkin can be run with a few flags. By default, debug mode is active,
 the debug pane will be shown and an error check is made after each OpenGL call. This can be
 deactivated, squeezing out more performance. See `python3 run.py --help` for all available
 options!  
 (**PS**: `--less-debug --less-debug` is equivalent to `-ll`)
