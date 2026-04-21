"""Tkinter GUI for people who'd rather click than type commands.

Launch with `python -m arboractive gui`. Walks the user through picking a lab
PDF, selecting up to two samples, and saving the report as HTML or PDF via
native file dialogs.
"""

from __future__ import annotations

import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .models import Report, Sample
from .parse import parse_pdf
from .pipeline import build_report, write_pdf
from .render import render


class SoilReportApp:
    MAX_SAMPLES = 2

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("ArborActive Soil Report Generator")
        root.geometry("520x600")
        root.minsize(460, 520)

        self.pdf_path: Path | None = None
        self.samples: tuple[Sample, ...] = ()
        self.checkbox_vars: dict[str, tk.BooleanVar] = {}
        self.checkboxes: dict[str, ttk.Checkbutton] = {}
        # Set by _build_report each save so handlers can append a warning to
        # the success status without re-running the build.
        self._contact_parse_failed: bool = False

        self._build_ui()

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="ArborActive Soil Report", font=("Georgia", 16, "bold")).pack(
            anchor="w"
        )
        ttk.Label(
            main,
            text="Turn a UConn lab PDF into a branded report.",
            foreground="gray",
        ).pack(anchor="w", pady=(0, 14))

        # Step 1 — pick PDF
        ttk.Label(
            main, text="1. Open your UConn lab PDF:", font=("TkDefaultFont", 10, "bold")
        ).pack(anchor="w")
        pdf_row = ttk.Frame(main)
        pdf_row.pack(fill="x", pady=(4, 14))
        ttk.Button(pdf_row, text="Select PDF...", command=self._on_select_pdf).pack(side="left")
        self.pdf_label = ttk.Label(pdf_row, text="(no file selected)", foreground="gray")
        self.pdf_label.pack(side="left", padx=10)

        # Step 2 — samples
        ttk.Label(
            main,
            text=f"2. Choose up to {self.MAX_SAMPLES} samples:",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor="w")
        samples_wrap = ttk.Frame(main, relief="solid", borderwidth=1)
        samples_wrap.pack(fill="both", expand=True, pady=(4, 14))
        self.samples_frame = ttk.Frame(samples_wrap, padding=8)
        self.samples_frame.pack(fill="both", expand=True)
        self.samples_placeholder = ttk.Label(
            self.samples_frame, text="Load a PDF to see samples.", foreground="gray"
        )
        self.samples_placeholder.pack(anchor="w")

        # Optional title override
        title_row = ttk.Frame(main)
        title_row.pack(fill="x", pady=(0, 14))
        ttk.Label(title_row, text="Title (optional):").pack(side="left")
        self.title_var = tk.StringVar()
        ttk.Entry(title_row, textvariable=self.title_var).pack(
            side="left", padx=8, fill="x", expand=True
        )

        # Step 3 — save
        ttk.Label(main, text="3. Save the report:", font=("TkDefaultFont", 10, "bold")).pack(
            anchor="w"
        )
        buttons = ttk.Frame(main)
        buttons.pack(fill="x", pady=(4, 0))
        ttk.Button(buttons, text="Save as HTML...", command=self._on_save_html).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(buttons, text="Save as PDF...", command=self._on_save_pdf).pack(side="left")

        # Status bar
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(main, textvariable=self.status_var, foreground="gray").pack(
            anchor="w", pady=(12, 0)
        )

    # --- event handlers ---

    def _on_select_pdf(self) -> None:
        path_str = filedialog.askopenfilename(
            title="Select UConn lab PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not path_str:
            return
        try:
            samples = parse_pdf(path_str)
        except Exception as e:  # pylint: disable=broad-exception-caught
            messagebox.showerror("Could not read PDF", str(e))
            return
        if not samples:
            messagebox.showerror("No samples", "No samples were found in this PDF.")
            return
        self.pdf_path = Path(path_str)
        self.samples = samples
        self.pdf_label.config(
            text=f"{self.pdf_path.name}  ({len(samples)} samples)", foreground="black"
        )
        self._populate_samples()
        self._set_status(f"Loaded {len(samples)} samples.")

    def _populate_samples(self) -> None:
        for widget in self.samples_frame.winfo_children():
            widget.destroy()
        self.checkbox_vars.clear()
        self.checkboxes.clear()
        for sample in self.samples:
            var = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(
                self.samples_frame, text=sample.name, variable=var, command=self._on_toggle
            )
            cb.pack(anchor="w", pady=1)
            self.checkbox_vars[sample.name] = var
            self.checkboxes[sample.name] = cb

    def _on_toggle(self) -> None:
        checked = [n for n, v in self.checkbox_vars.items() if v.get()]
        at_limit = len(checked) >= self.MAX_SAMPLES
        for name, cb in self.checkboxes.items():
            if not self.checkbox_vars[name].get():
                cb.state(["disabled"] if at_limit else ["!disabled"])

    def _selected_samples(self) -> tuple[Sample, ...]:
        names = {n for n, v in self.checkbox_vars.items() if v.get()}
        return tuple(s for s in self.samples if s.name in names)

    def _build_report(self) -> Report | None:
        selected = self._selected_samples()
        if not selected:
            messagebox.showwarning("Nothing selected", "Select at least one sample first.")
            return None
        result = build_report(selected, self.pdf_path, self.title_var.get())
        self._contact_parse_failed = result.contact_parse_failed
        if result.contact_parse_failed:
            self._set_status(
                "Warning: contact block could not be parsed; contact fields left empty."
            )
        return result.report

    def _save_dialog(self, report: Report, extension: str, label: str) -> Path | None:
        default_name = f"{report.site_name.replace(' ', '_') or 'soil'}_report{extension}"
        path_str = filedialog.asksaveasfilename(
            title=f"Save report as {label}",
            defaultextension=extension,
            filetypes=[(label, f"*{extension}"), ("All files", "*.*")],
            initialfile=default_name,
        )
        return Path(path_str) if path_str else None

    def _on_save_html(self) -> None:
        report = self._build_report()
        if report is None:
            return
        out = self._save_dialog(report, ".html", "HTML")
        if out is None:
            return
        try:
            out.write_text(render(report), encoding="utf-8")
        except Exception as e:  # pylint: disable=broad-exception-caught
            messagebox.showerror("Save failed", f"{e}\n\n{traceback.format_exc()}")
            return
        self._set_status(self._with_contact_warning(f"Saved {out.name}"))
        messagebox.showinfo("Saved", f"HTML report saved:\n{out}")

    def _on_save_pdf(self) -> None:
        report = self._build_report()
        if report is None:
            return
        out = self._save_dialog(report, ".pdf", "PDF")
        if out is None:
            return
        self._set_status("Generating PDF...")
        self.root.update_idletasks()
        try:
            write_pdf(render(report), out)
        except Exception as e:  # pylint: disable=broad-exception-caught
            messagebox.showerror("Save failed", f"{e}\n\n{traceback.format_exc()}")
            return
        self._set_status(self._with_contact_warning(f"Saved {out.name}"))
        messagebox.showinfo("Saved", f"PDF report saved:\n{out}")

    def _set_status(self, msg: str) -> None:
        self.status_var.set(msg)

    def _with_contact_warning(self, msg: str) -> str:
        if self._contact_parse_failed:
            return (
                f"{msg} (warning: contact block could not be parsed; " "contact fields left empty.)"
            )
        return msg


def run_gui() -> None:
    """Open the GUI and block until the window closes."""
    root = tk.Tk()
    SoilReportApp(root)
    root.mainloop()
