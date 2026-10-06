# How to build Executable

1. First install PyInstaller if you haven't already
2. Use this command for Windows to create the executable:
```shell
PyInstaller
--windowed
--add-binary "%appdata%\Local\Programs\Python\Python312\Lib\site-packages\glfw\glfw3.dll;."
--name "EcoVis"
src\python\main.py
```
- `py -3.12 -m` prefix may need to be added to this command
- glfw3.dll location may vary
Or this command for Linux:
```bash
PROJECT_ROOT = $(git rev-parse --show-toplevel)

pyinstaller \
  --windowed \
  --collect-all glfw \
  --collect-all OpenGL \
  --name "EcoVis" \
  --workpath "../build/linux" \
  --distpath "../dist/linux" \
  ../src/python/main.py
```
3. Add `default_config.json` and `resources` folder to the root folder
Command for linux:
```bash
    cp "../default_config.json" "../dist/linux/EcoVis/"
    cp -r "../resources" "../dist/linux/EcoVis/"
```
