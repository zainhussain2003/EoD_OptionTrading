"""Tiny dependency-free test harness with clear, readable output.

No pytest needed — just run `python run_tests.py`.
"""
import sys
import traceback


def _tty() -> bool:
    return sys.stdout.isatty()


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _tty() else text


def green(t): return _c(t, '32')
def red(t):   return _c(t, '31')
def yellow(t): return _c(t, '33')
def cyan(t):  return _c(t, '36')
def bold(t):  return _c(t, '1')

CHECK = green('✓')
CROSS = red('✗')
SKIP = yellow('⊘')


class Section:
    """A group of related checks with a header and a running tally."""

    def __init__(self, title: str):
        self.title = title
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.failures = []

    def __enter__(self):
        print()
        print(bold(cyan(f"▶ {self.title}")))
        print(cyan("  " + "─" * 58))
        return self

    def check(self, label: str, condition: bool, detail: str = ""):
        """Assert a condition. Prints ✓ or ✗ with the label."""
        if condition:
            self.passed += 1
            line = f"  {CHECK} {label}"
            if detail:
                line += f"  {detail}"
            print(line)
        else:
            self.failed += 1
            self.failures.append(label)
            line = f"  {CROSS} {label}"
            if detail:
                line += f"  {red(detail)}"
            print(line)
        return condition

    def info(self, label: str, value: str):
        """Print a data point for visual inspection (not a pass/fail)."""
        print(f"    {label}: {bold(str(value))}")

    def skip(self, label: str, reason: str = ""):
        self.skipped += 1
        line = f"  {SKIP} {label}"
        if reason:
            line += f"  {yellow('(' + reason + ')')}"
        print(line)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Unexpected exception inside the section
            self.failed += 1
            self.failures.append(f"EXCEPTION: {exc_val}")
            print(f"  {CROSS} {red('Unhandled exception in section:')}")
            for ln in traceback.format_exception(exc_type, exc_val, exc_tb):
                for sub in ln.rstrip().split("\n"):
                    print(f"      {red(sub)}")
            return True  # suppress so other sections still run

        total = self.passed + self.failed
        status = green("PASS") if self.failed == 0 else red("FAIL")
        extra = f", {self.skipped} skipped" if self.skipped else ""
        print(cyan("  " + "─" * 58))
        print(f"  Section result: {status}  ({self.passed}/{total} passed{extra})")
        return False


class Suite:
    """Top-level collector across all sections."""

    def __init__(self, name: str):
        self.name = name
        self.sections = []

    def section(self, title: str) -> Section:
        s = Section(title)
        self.sections.append(s)
        return s

    def banner(self):
        w = 62
        print(bold("╔" + "═" * w + "╗"))
        print(bold("║" + f"{self.name:^{w}}" + "║"))
        print(bold("╚" + "═" * w + "╝"))

    def summary(self) -> int:
        total_pass = sum(s.passed for s in self.sections)
        total_fail = sum(s.failed for s in self.sections)
        total_skip = sum(s.skipped for s in self.sections)
        total = total_pass + total_fail

        w = 62
        print()
        print(bold("╔" + "═" * w + "╗"))
        if total_fail == 0:
            msg = f"ALL TESTS PASSED   {total_pass}/{total} ✓"
            if total_skip:
                msg += f"   ({total_skip} skipped)"
            print(bold("║" + green(f"{msg:^{w}}") + "║"))
        else:
            msg = f"{total_fail} TEST(S) FAILED   {total_pass}/{total} passed"
            print(bold("║" + red(f"{msg:^{w}}") + "║"))
        print(bold("╚" + "═" * w + "╝"))

        if total_fail:
            print()
            print(red("  Failed checks:"))
            for s in self.sections:
                for f in s.failures:
                    print(red(f"    • [{s.title}] {f}"))

        return 0 if total_fail == 0 else 1
