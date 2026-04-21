"""Smoke tests for the GUI module.

We can't meaningfully exercise a Tk window without a display, so these tests
verify the module imports cleanly and exposes the expected symbols.
"""

from __future__ import annotations


def test_gui_module_imports() -> None:
    from arboractive import gui  # pylint: disable=import-outside-toplevel

    assert callable(gui.run_gui)
    assert hasattr(gui, "SoilReportApp")
    assert gui.SoilReportApp.MAX_SAMPLES == 2


def test_gui_subcommand_registered() -> None:
    from arboractive.cli import _build_parser  # pylint: disable=import-outside-toplevel

    parser = _build_parser()
    # argparse keeps subparsers on its list of actions.
    subparsers_action = next(
        a
        for a in parser._actions  # pylint: disable=protected-access
        if a.__class__.__name__ == "_SubParsersAction"
    )
    choices = subparsers_action.choices
    assert choices is not None
    assert "gui" in choices
    assert "report" in choices
