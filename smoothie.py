# from http.server import HTTPServer, SimpleHTTPRequestHandler
from distutils.dir_util import copy_tree
from livereload import Server
from pathlib import Path
import contextlib
import subprocess
import shutil
import glob
import sys
import os

RELEASE_MODE = len(sys.argv) >= 2 and sys.argv[1] == "--release"


def supress_stdout(func):
    def wrapper(*a, **ka):
        with open(os.devnull, 'w') as devnull:
            with contextlib.redirect_stdout(devnull):
                func(*a, **ka)
    return wrapper


def make_required_directories():
    Path("./build/smooth/__target2__").mkdir(exist_ok=True, parents=True)
    Path("./output").mkdir(exist_ok=True, parents=True)


def js_to_py(filename):
    return str(filename).replace(".js", ".py")


def js_to_svelte(filename):
    return str(filename).replace(".js", ".svelte")


def copy_to_svelte_project_dir():
    for f in glob.glob('./src/*.*'):
        shutil.copy(f, './build/src')
    for f in glob.glob('./src/pages/*.svelte'):
        shutil.copy(f, './build/src/pages')


def copy_to_root():
    for f in glob.glob('./src/root/*'):
        shutil.copy(f, './output')


def run_transcrypt():
    for f in glob.glob("./build/smooth/pages/*.py"):
        cmd = f"python ./cryptic/src/__main__.py -b -n -g {f}"
        subprocess.run(cmd, shell=True, stdout=open(os.devnull, "w"))
        copy_tree("./build/smooth/pages/__target__",
                  "./build/smooth/__target2__")


def append_transpiled_python():
    files = glob.glob("./build/smooth/__target2__/*.js")
    for f in files:
        if "org.transcrypt.__runtime__" in f:
            shutil.copy(f, './build/src/pages')
            continue
        with open(f, "r") as reader:
            file_contents = reader.read()
            file_contents = "<script>" + file_contents + "</script>"
            file_name = Path(f).name
            svelte_file_name = js_to_svelte(file_name)
            with open(f"./build/src/pages/{svelte_file_name}", "a") as writer:
                writer.write("")
                writer.write(file_contents)


def rollup():
    if RELEASE_MODE:
        subprocess.run("npm run build-prod", cwd="./build", shell=True)
    else:
        subprocess.run("npm run build-dev", cwd="./build", shell=True)


def run(port=4200):
    server = Server()
    server.watch('src', refresh)
    server.serve(port=port, root='output')


def refresh():
    copy_tree("./src", "./build/smooth")
    make_required_directories()
    run_transcrypt()
    copy_to_svelte_project_dir()
    copy_to_root()
    append_transpiled_python()
    rollup()


if __name__ == "__main__":
    refresh()
    if not RELEASE_MODE:
        run()
