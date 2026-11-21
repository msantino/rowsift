from importlib.metadata import version

import rowsift


def test_version_matches_the_installed_metadata() -> None:
    assert rowsift.__version__ == version("rowsift")
