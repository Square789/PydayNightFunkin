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
 You probably don't! Here's some pros and cons:
### Pros and Features
 - **Starts quickly**: Changes to Python files are visible far more quickly than changes
   made to Haxe as Python bytecode typically beats HTML5/C++ compilation times.
 - **Significantly cleaner code** than most engines i have seen so far due to an attempt at
   documentation and logically separating stages instead of mashing them together into a
   5000 line long file.
 - **Smart\* asset eviction**: Most FNF engines' memory management is "wipe all unused assets
   on PlayState creation". PNF unloads unused assets once a memory usage limit overstepped,
   starting with a hybrid of least-recently used and largest.  
   This leads to lower loading times between songs that reuse large background/character
   sheets and tries to strike an okay balance between memory usage and staring at a black screen.  
   *(\* about as smart as a paperclip)*
 - **Homegrown batch implementation**: Fancy sprite batching that deals well with strict
   ordering and gets by with a small amount of draw calls. Strumline, arrows and combo sprites
   only take a single one of those!
### Cons and Disadvantages
 - **Runs slowly**: due to Python's interpreted nature, PNF runs ~20-50 times slower than
   FNF's compiled C++ code and ~1-4 times slower than html5 builds, but still fast enough to
   not scrape the fabled 16ms 60FPS ceiling.
 - **Does not run in a web browser**: The OpenGL variants that can be used in a browser are
   quite different from what i get, and pyglet does not target them. PNF is intended to be run
   directly on your system.
 - This is a **complete hobby project**. In development, rapidly breaks stuff and so on.
 - **Still lacks many many things**: Save data, options, a chart editor (not planned
   tbh, use another engine's), any kind of comprehensive modding frontend, an accuracy system and
   tightly timed input detection that doesn't risk lagging behind by up to 16ms are totally
   missing!

## Boring! Show me a video!
 [Sure thing, here's one](https://www.youtube.com/watch?v=vTG_HHTZ0gk) - [June 17 2023; v0.0.50]

## How to run?
 I'm honored you want to try this out, because there's really nothing too revolutionary in here.
 Anyways:

### 0. Prerequisites
 - OpenGL 4.5 support on your system, cause the Direct State Access mechanism it
   introduced was too sweet to not use.
   - This makes PNF incompatible with apple devices cause they decided OpenGL 4.5 wasn't good
     enough for them anymore. I did create a [4_1-compat branch](https://github.com/Square789/PydayNightFunkin/tree/gl4_1-compat)
     for that, however don't really care much about updating it. It's far behind main, so
     you'll need to try and update it on your own.
 - You will need Python.
   - I recommend getting it from [its official website](https://www.python.org/downloads/). I
     have seen the windows store version cause weird access restriction problems when installing
     packages, though this likely was just a case of a system possessed by some sort of spirit.
   - 3.11 is definitely recommended due to its speed advantages, but anything starting from 3.8
     should work.
 - Ensure that Python can build C extensions; that is: you have a C compiler set up.
   - I am sorry to disappoint if you thought Python meant not having to deal with that. PNF gets
     some of its speed and capabilities from custom C extensions.
     Delivering them prebuilt would eliminate this step, but not as long as this project is in
     this stage of development.
   - If on Windows, you will need Visual Studio; the required packages and versions are difficult
     to pinpoint and unlikely to remain stable over longer time periods. [This wiki entry](https://wiki.python.org/moin/WindowsCompilers#Compilers_Installation_and_configuration)
     seems to have somewhat up-to-date information on what you'll need.

 Now, open a terminal and run the commands below.  
 > [!NOTE]
 > If `python3` fails, try `python` or `py` instead, the name may differ depending on
 > your OS and Python variants.

### 1. (Option A) Clone the repo (Requires [git](https://git-scm.com/))
 Create and/or choose a directory where the project fits well. (`Code/python`,
 `Documents/experiments`, `Games/pnf`, `test`, the possibilities are endless.)  
 Then, open a terminal in it and clone the repository:
```bat
git clone https://github.com/Square789/PydayNightFunkin.git
cd PydayNightFunkin
```

### 1. (Option B) Clone the repo
 Download the source via the Code > Download ZIP button on top of the page and extract that
 somewhere it fits well, then open a terminal inside the directory that contains (among other
 files) `README.md`.

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
 > [!NOTE]
 > The activation command of a venv depends on your OS and shell.
 > [See this page](https://docs.python.org/3/library/venv.html#how-venvs-work) for a few ways
 > of doing it.

### 3. Get the build dependencies and build the C extensions
```bat
python3 -m pip install -r requirements_build.txt
python3 setup.py build_ext -i
```
 > [!NOTE]
 > This step may fail in many unpredictable and nasty ways. If that happens, please
 > [open an issue](https://github.com/Square789/PydayNightFunkin/issues/new).
 > I'll try my best to help with anything.

### 4. Get the runtime dependencies
```bat
python3 -m pip install -r requirements.txt
```

### 5. Run
 ```bat
 python3 run.py
 ```

### 6. Run faster
 You'll notice that by default, the debug mode is active. The debug pane will be shown and an
 error check is made after each OpenGL call. See `python3 run.py --help` for options on disabling
 these. (`--less-debug --less-debug` is equivalent to `-ll`!)  
 Also, you can try and run Python itself in optimized mode, eliminating assert statements:
 ```bat
 python3 -O run.py -g
 ```
