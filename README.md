# smooth.py
Svelte, but with Python instead of Javascript

## Installation
All of the magic happens in the build folder. cd into this folder and run npm install to install all of the JS dependencies you need to make this project run. Similarly, ./build/package.json is where you'll keep track of and update your JS dependencies.

## Cryptic
Cryptic is a fork of Transcrypt, a Python-to-JS transpiler. We forked Transcrypt because of differing design philosophies. The Transcrypt team seems to put more emphasis on speed than purity/usability. We would rather have a feature complete Python implementation than a fast implementation. Performance can be tuned at a later point - for now, we want to make sure no one is surprised by missing features or inconsistent implementations. As Guido van Rossum said, "for most of what you're doing, the speed of the language is irrelevant".

Additionally, the Pystone benchmarks show Transcrypt produces Javascript code that performs twice as well as native Python 3.8.6 code. We can afford taking a significant speed hit in order to provide consistency, and we would still have a performant implementation.