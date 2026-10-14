"""Extract the python code block from an LLM transcript (JSONL), save it unmodified, run it in its own folder, and check it.
Usage: python tests/run_llm_output.py TRANSCRIPT.jsonl llm_code/NAME.py [--no-check]"""
import json
import re
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
transcript, dest = sys.argv[1], root / sys.argv[2]
last = None
for line in open(transcript):
    try:
        d = json.loads(line)
    except Exception:
        continue
    m = d.get("message", {})
    if m.get("role") == "assistant":
        c = m.get("content")
        txt = "".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text") if isinstance(c, list) else (c or "")
        if "```python" in txt:
            last = txt
code = re.search(r"```python\n(.*?)```", last, re.S).group(1)
dest.write_text(code)
run_dir = dest.with_suffix("")
run_dir.mkdir(exist_ok=True)
# the saved file stays verbatim; only Colab/IPython magics (lines starting with ! or %) are commented out in the runnable copy
runnable = run_dir / "_runnable.py"
runnable.write_text("\n".join("# " + l if l.lstrip().startswith(("!", "%")) else l for l in code.splitlines()))
res = subprocess.run([str(root / ".venv/bin/python"), str(runnable)], cwd=run_dir, capture_output=True, text=True)
(run_dir / "run.log").write_text(res.stdout + "\n--- STDERR ---\n" + res.stderr)
print(f"{dest.name}: {len(code.splitlines())} lines, run rc={res.returncode}")
if res.returncode:
    print(res.stderr[-1200:])
elif "--no-check" not in sys.argv:
    print(subprocess.run([str(root / ".venv/bin/python"), str(root / "tests/check_llm_results.py"), str(run_dir / "results.json")],
                         capture_output=True, text=True).stdout)
