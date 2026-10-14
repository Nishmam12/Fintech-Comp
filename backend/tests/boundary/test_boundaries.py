"""Static trust-boundary checks (ADR-0001, ADR-0005 'single writer path'). No database needed."""
import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "budget_kernel"
FORBIDDEN_FOR_KERNEL = {"providers", "routing", "proposals", "naive_baseline", "simulation", "api"}


def py_files(sub: str = ""):
    return [p for p in (SRC / sub).rglob("*.py")]


def imported_packages(path: Path) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level == 0 and mod.startswith("budget_kernel."):
                out.add(mod.split(".")[1])
            elif node.level >= 2:  # from ..pkg import x
                out.add(mod.split(".")[0] if mod else "")
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("budget_kernel."):
                    out.add(a.name.split(".")[1])
    return out


def test_kernel_does_not_import_model_or_edge_code():
    """The authorization core must be unable to call a model, router or the web layer."""
    bad = {str(p.relative_to(SRC)): imported_packages(p) & FORBIDDEN_FOR_KERNEL for p in py_files("kernel")}
    assert {k: v for k, v in bad.items() if v} == {}


def test_only_kernel_writes_money_tables():
    """No module outside kernel/ (or the migration runner) may INSERT/UPDATE/DELETE money tables."""
    pat = re.compile(r"\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+(\w+\.)?(grants|transactions|ledger_movements|mandates)\b", re.I)
    offenders = []
    for p in py_files():
        rel = p.relative_to(SRC)
        if rel.parts[0] == "kernel" or rel.name == "migrate.py":
            continue
        if pat.search(p.read_text(encoding="utf-8")):
            offenders.append(str(rel))
    assert offenders == []


def test_naive_baseline_is_only_reachable_from_simulation():
    """The intentionally unsafe baseline must never be used by the secure path."""
    importers = []
    for p in py_files():
        rel = p.relative_to(SRC)
        if rel.parts[0] in ("naive_baseline", "simulation"):
            continue
        if "naive_baseline" in imported_packages(p):
            importers.append(str(rel))
    assert importers == []


def test_no_float_money_in_kernel():
    """Money is integer minor units: no float() / float literals in kernel code."""
    for p in py_files("kernel"):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            assert not (isinstance(node, ast.Constant) and isinstance(node.value, float)), f"float literal in {p.name}"
            assert not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "float"), f"float() in {p.name}"


def test_no_secrets_in_tracked_source():
    """A 64-hex string next to a private-key name must never be committed (ADR-0007 key custody)."""
    pat = re.compile(r"(PRIVATE_KEY|SECRET_KEY)\s*[=:]\s*['\"]?(0x)?[0-9a-fA-F]{64}")
    root = SRC.parents[1]
    hits = [str(p) for p in list(root.rglob("*.py")) + list(root.rglob("*.md")) + list(root.rglob("*.sql"))
            if ".venv" not in p.parts and pat.search(p.read_text(encoding="utf-8", errors="ignore"))]
    assert hits == []
