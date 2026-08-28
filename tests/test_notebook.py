import json
from pathlib import Path


def test_analysis_notebook_code_cells_compile():
    repo_root = Path(__file__).resolve().parents[1]
    notebook_path = repo_root / "notebooks" / "analysis.ipynb"
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))

    code_cells = [
        cell for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code"
    ]
    assert code_cells, "analysis.ipynb should contain code cells"

    for index, cell in enumerate(code_cells):
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        compile(source, f"analysis.ipynb code cell {index}", "exec")
