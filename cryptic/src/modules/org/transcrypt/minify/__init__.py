import os
import subprocess
import shutil

from .. import utils

p = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
closureCompilerPath = f'{p}/compiler.jar'

# Minifier has to accept JavaScript 6 input code, it is there in the autotest, even if not executed.


def run(targetDir, sourceFileName, targetFileName, mapFileName=None, prettify=False):
    params = [
        'java', '-jar',
        closureCompilerPath,
        '--language_out=ECMASCRIPT6_STRICT',
        '--compilation_level', 'WHITESPACE_ONLY',
        '--js', sourceFileName,
        '--js_output_file', targetFileName
    ]
    # cmd = f"npx swc {sourceFileName} -o {targetFileName}"

    if prettify:
        params += ['--formatting', 'PRETTY_PRINT']

    if utils.commandArgs.map and not prettify:
        params += [
            '--create_source_map', mapFileName,
            '--source_map_format=V3'
        ]

    origDir = os.getcwd()
    # So the map will store sourcePath and targetPath as filenames rather than full paths
    # os.chdir(targetDir)
    # subprocess.run(params)
    from pathlib import Path
    source = Path(targetDir) / sourceFileName
    target = Path(targetDir) / targetFileName
    print(origDir)
    print(source)
    print(target)
    # shutil.copy(source, )

    # cmd = f"npx swc {source} -o {target}"
    # subprocess.run(cmd)
    # os.chdir(origDir)
