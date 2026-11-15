# Sim helpers for fork C tests: run example scripts directly.
from nc import runner, storage
from nc.apps import python as P


def _run(name):
    P._ensure_examples()
    p = storage.PROGRAMS + "/" + name
    with open(p, "w") as f:
        f.write(P.EXAMPLES[name])
    runner.run_file(p)


def plot():
    _run("plot.py")


def turtle():
    _run("turtle_star.py")


def chart():
    _run("chart.py")


def primes():
    _run("primes.py")


def blink():
    _run("blink.py")
