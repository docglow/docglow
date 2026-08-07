"""Allow running docglow as ``python -m docglow``.

Equivalent to the ``docglow`` console script, but bound to the invoking
interpreter — useful for source-tree runs (``PYTHONPATH=src python -m docglow``)
and environments where console scripts are not on PATH.
"""

from docglow.cli import cli

if __name__ == "__main__":
    cli()
