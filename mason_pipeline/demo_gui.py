#!/usr/bin/env python3
"""
demo_gui.py — Gradio demo for the Self-Validating Multi-LLM Pipeline.
Run from the mason_pipeline/ directory:
    python demo_gui.py
"""

import html
import json
import os
import queue
import tempfile
import threading

# Ensure relative imports and outputs work correctly
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import gradio as gr

import llm as llm_module
from config import OUTPUT_MODEL
from pipeline import SelfValidatingPipeline, _result_details, _load_verifier_module
from prompts import SYSTEM_MSG
from utils import timeout as sigalrm_timeout

# ─── Load cases ───────────────────────────────────────────────────────────────

with open("cases/Cases.json") as f:
    _raw = json.load(f)
CASES: list = _raw["cases"]
CASE_CHOICES = [f"Case {c['case_number']}: {c['genre']}" for c in CASES]


# ─── Event-emitting pipeline subclass ────────────────────────────────────────

class DemoPipeline(SelfValidatingPipeline):
    """Subclass that emits structured events to a queue for the GUI to consume."""

    def __init__(self, eq: queue.Queue, **kwargs):
        self._eq = eq
        super().__init__(**kwargs)
        # track data for re-rendering iteration cards
        self._iter_store: dict = {}   # n -> {"output": str, "result": tuple, "repairing": bool}

    def _emit(self, event_type: str, **data):
        self._eq.put({"type": event_type, **data})

    def run(self, problem_file: str):
        problem_data = self.load_problem(problem_file)

        # ── Phase 1: verifier ────────────────────────────────────────────────
        self._emit("phase1_start")
        if self.reuse_verifier:
            with open("outputs/verifier.py") as f:
                verifier_code = f.read()
            self.verifier = _load_verifier_module("outputs/verifier.py")
            self._emit("phase1_done", code=verifier_code, reused=True)
        else:
            verifier_code = self._generate_verifier(problem_data)
            self.verifier = self._load_verifier(verifier_code)
            self._emit("phase1_done", code=verifier_code, reused=False)

        # ── Phase 2: iterative generation ───────────────────────────────────
        self._emit("phase2_start", max_iter=self.max_iterations)
        self.messages = [
            SYSTEM_MSG,
            {
                "role": "user",
                "content": (
                    "Generate a solution that satisfies ALL constraints "
                    "and follows the output format.\n\n"
                    + problem_data["full_content"]
                ),
            },
        ]

        last_output, last_result = None, None

        for iteration in range(self.max_iterations):
            n = iteration + 1
            self._emit("iter_start", n=n, total=self.max_iterations)

            try:
                with sigalrm_timeout(1000):
                    content = llm_module.chat(OUTPUT_MODEL, messages=self.messages)
            except TimeoutError:
                self._emit("error", msg="LLM generation timed out")
                self._emit("done")
                return None, None

            self.messages.append({"role": "assistant", "content": content})
            output = self._parse_output(content)
            last_output = output
            result = self._run_verifier(output)
            last_result = result

            self._save_iteration(n, output, result)
            self._iter_store[n] = {"output": output, "result": result, "repairing": False}
            self._emit("iter_done", n=n, output=output, result=result)

            if result[0]:
                self._emit("success", n=n, output=output, result=result)
                self._save_final(problem_data, output, result, verifier_code, success=True)
                self._emit("done")
                return output, result

            # Generate repair instructions
            self._iter_store[n]["repairing"] = True
            self._emit("repair_start", n=n)
            feedback = self._generate_repair_suggestions(output, result)
            self._log_iteration(n, output, result, feedback)
            self.messages.append({"role": "user", "content": feedback})
            self.messages = self.messages[:2] + self.messages[-2:]
            self._iter_store[n]["repairing"] = False
            self._emit("repair_done", n=n)

        self._emit("max_iter", output=last_output, result=last_result)
        self._save_final(problem_data, last_output, last_result, verifier_code, success=False)
        self._emit("done")
        return last_output, last_result


# ─── HTML rendering helpers ───────────────────────────────────────────────────

CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  .pl-root { font-family: 'Inter', system-ui, sans-serif; display: flex; flex-direction: column; gap: 10px; }

  /* ── Phase card ── */
  .pc {
    border-radius: 12px; padding: 14px 18px;
    border: 1.5px solid #e2e8f0; background: #f8fafc;
  }
  .pc.active  { border-color: #93c5fd; background: #eff6ff; }
  .pc.success { border-color: #6ee7b7; background: #f0fdf4; }
  .pc.fail    { border-color: #fca5a5; background: #fef2f2; }
  .pc h3 { margin: 0 0 6px 0; font-size: 15px; font-weight: 600; color: #1e293b; }
  .pc .status { font-size: 13px; color: #64748b; }

  /* ── Iteration card ── */
  .ic {
    border-radius: 12px; padding: 16px 18px;
    border: 1.5px solid #e2e8f0; background: #ffffff;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
  }
  .ic.pass { border-color: #6ee7b7; }
  .ic.fail { border-color: #fca5a5; }
  .ic-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
  .badge {
    font-size: 11px; font-weight: 700; padding: 3px 10px;
    border-radius: 999px; background: #e2e8f0; color: #475569;
    white-space: nowrap;
  }
  .score-wrap { flex: 1; display: flex; align-items: center; gap: 8px; }
  .score-bg { background: #e2e8f0; border-radius: 999px; height: 8px; flex: 1; overflow: hidden; }
  .score-fill { height: 8px; border-radius: 999px; }
  .score-pct { font-size: 13px; font-weight: 700; min-width: 38px; text-align: right; }
  .verdict { font-size: 12px; font-weight: 700; padding: 3px 10px; border-radius: 999px; white-space: nowrap; }
  .verdict.pass { background: #dcfce7; color: #15803d; }
  .verdict.fail { background: #fee2e2; color: #b91c1c; }

  /* ── Constraint list ── */
  .clist { display: flex; flex-direction: column; gap: 2px; margin-bottom: 8px; }
  .citem { font-size: 12px; display: flex; align-items: flex-start; gap: 6px; line-height: 1.5; }
  .citem.pass { color: #15803d; }
  .citem.fail { color: #b91c1c; }
  .cmark { flex-shrink: 0; font-size: 13px; }

  /* ── Output preview ── */
  .out-prev {
    background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 8px; padding: 10px 12px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 12px;
    color: #334155; white-space: pre-wrap; max-height: 120px;
    overflow-y: auto; line-height: 1.6;
  }

  /* ── Final result card ── */
  .final-card {
    border-radius: 14px; padding: 20px;
    border: 2px solid #34d399; background: #ecfdf5;
    box-shadow: 0 2px 8px rgba(52,211,153,.15);
  }
  .final-card h2 { margin: 0 0 14px 0; font-size: 17px; color: #065f46; }
  .final-out {
    background: white; border-radius: 8px; padding: 14px;
    white-space: pre-wrap; font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 13px; border: 1px solid #6ee7b7;
    max-height: 340px; overflow-y: auto; line-height: 1.7;
  }

  /* ── Spinner ── */
  @keyframes spin { to { transform: rotate(360deg); } }
  .spin { display: inline-block; animation: spin .9s linear infinite; }
</style>
"""


def _score_color(score: float) -> str:
    if score >= 1.0:
        return "#22c55e"
    if score >= 0.6:
        return "#f59e0b"
    return "#ef4444"


def _constraint_rows(passed: list, failed: list) -> str:
    rows = ""
    for c in passed:
        rows += f'<div class="citem pass"><span class="cmark">✓</span><span>{html.escape(c)}</span></div>'
    for c in failed:
        rows += f'<div class="citem fail"><span class="cmark">✗</span><span>{html.escape(c)}</span></div>'
    return f'<div class="clist">{rows}</div>'


def _phase1_card(state: str = "running", code: str = None, reused: bool = False) -> str:
    if state == "running":
        body = '<div class="status"><span class="spin">⟳</span>&nbsp; Generating verifier function from problem spec...</div>'
        cls = "active"
    else:
        src = "Reusing existing verifier" if reused else "Verifier generated successfully"
        body = f'<div class="status" style="color:#16a34a;font-weight:600">✓ {src}</div>'
        if code:
            preview = html.escape(code[:500] + ("…" if len(code) > 500 else ""))
            body += (
                '<details style="margin-top:10px">'
                '<summary style="font-size:12px;cursor:pointer;color:#475569;user-select:none">'
                '▸ Show generated verifier code</summary>'
                f'<pre style="font-size:11px;overflow-x:auto;margin:6px 0 0;padding:8px;background:#f1f5f9;border-radius:6px">{preview}</pre>'
                '</details>'
            )
        cls = "success"
    return f'<div class="pc {cls}"><h3>Phase 1 &mdash; Verifier Generation</h3>{body}</div>'


def _iter_card(n: int, total: int, output: str, result: tuple, repairing: bool = False) -> str:
    details = _result_details(result)
    score = result[1]
    is_valid = result[0]
    color = _score_color(score)
    bar_w = int(score * 100)
    verdict_cls = "pass" if is_valid else "fail"
    verdict_txt = "✓ PASS" if is_valid else "✗ FAIL"
    card_cls = "pass" if is_valid else "fail"

    constraints_html = _constraint_rows(details.get("passed", []), details.get("failed", []))
    preview_text = html.escape((output or "")[:400] + ("…" if len(output or "") > 400 else ""))

    repair_html = ""
    if repairing:
        repair_html = (
            '<div style="margin-top:10px;font-size:12px;color:#2563eb;font-weight:500">'
            '<span class="spin">⟳</span>&nbsp; Generating repair instructions via critic LLM…'
            '</div>'
        )

    return f"""
<div class="ic {card_cls}">
  <div class="ic-header">
    <span class="badge">Iteration {n} / {total}</span>
    <div class="score-wrap">
      <div class="score-bg">
        <div class="score-fill" style="width:{bar_w}%;background:{color}"></div>
      </div>
      <span class="score-pct" style="color:{color}">{score:.0%}</span>
    </div>
    <span class="verdict {verdict_cls}">{verdict_txt}</span>
  </div>
  {constraints_html}
  <div class="out-prev">{preview_text}</div>
  {repair_html}
</div>"""


def _iter_loading_card(n: int, total: int) -> str:
    return (
        f'<div class="ic">'
        f'<div class="ic-header">'
        f'<span class="badge">Iteration {n} / {total}</span>'
        f'<span style="font-size:13px;color:#64748b"><span class="spin">⟳</span>&nbsp; Generating output…</span>'
        f'</div></div>'
    )


def _final_card(output: str, result: tuple) -> str:
    details = _result_details(result)
    score = result[1]
    n_pass = details["num_passed"]
    n_total = n_pass + details["num_failed"]
    preview = html.escape(output or "")
    return (
        '<div class="final-card">'
        f'<h2>🎉 All constraints satisfied — Score {score:.0%} &nbsp;({n_pass}/{n_total} constraints)</h2>'
        f'<div class="final-out">{preview}</div>'
        '</div>'
    )


def _maxiter_card(output: str, result: tuple) -> str:
    details = _result_details(result)
    score = result[1]
    n_pass = details["num_passed"]
    n_total = n_pass + details["num_failed"]
    preview = html.escape((output or "")[:600] + ("…" if len(output or "") > 600 else ""))
    return (
        '<div class="pc fail">'
        f'<h3>Max iterations reached — final score {score:.0%} ({n_pass}/{n_total})</h3>'
        f'<div class="out-prev" style="margin-top:10px">{preview}</div>'
        '</div>'
    )


def _wrap(cards: list) -> str:
    return CSS + f'<div class="pl-root">{"".join(cards)}</div>'


# ─── Gradio callbacks ─────────────────────────────────────────────────────────

def on_case_change(choice: str):
    if not choice:
        return "", ""
    idx = int(choice.split(":")[0].replace("Case", "").strip()) - 1
    case = CASES[idx]
    constraints_md = "\n".join(f"• {c}" for c in case["constraints"])
    return case["prompt"], constraints_md


def run_pipeline(choice: str, max_iter: int):
    if not choice:
        yield _wrap(['<div class="pc fail"><h3>Please select a case.</h3></div>'])
        return

    idx = int(choice.split(":")[0].replace("Case", "").strip()) - 1
    case = CASES[idx]

    # Write a single-case temp file (pipeline.load_problem expects a single JSON object)
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, dir="cases", prefix="_demo_"
    )
    json.dump(case, tmp)
    tmp.close()
    tmp_path = tmp.name

    eq: queue.Queue = queue.Queue()
    pipeline = DemoPipeline(eq, max_iterations=int(max_iter), reuse_verifier=False)

    def _thread():
        try:
            pipeline.run(tmp_path)
        except Exception as e:
            eq.put({"type": "error", "msg": str(e)})
            eq.put({"type": "done"})
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    threading.Thread(target=_thread, daemon=True).start()

    # ── State ────────────────────────────────────────────────────────────────
    phase1_html = _phase1_card("running")
    iter_cards: dict = {}   # n -> html string
    final_html = ""
    max_total = int(max_iter)

    def render() -> str:
        parts = [phase1_html]
        for n in sorted(iter_cards):
            parts.append(iter_cards[n])
        if final_html:
            parts.append(final_html)
        return _wrap(parts)

    yield render()

    # ── Event loop ───────────────────────────────────────────────────────────
    while True:
        try:
            ev = eq.get(timeout=180)
        except queue.Empty:
            yield _wrap(['<div class="pc fail"><h3>Timed out waiting for pipeline event.</h3></div>'])
            return

        etype = ev["type"]

        if etype == "phase1_done":
            phase1_html = _phase1_card("done", code=ev.get("code"), reused=ev.get("reused", False))
            yield render()

        elif etype == "iter_start":
            n, total = ev["n"], ev["total"]
            iter_cards[n] = _iter_loading_card(n, total)
            yield render()

        elif etype == "iter_done":
            n = ev["n"]
            data = pipeline._iter_store.get(n, {})
            iter_cards[n] = _iter_card(n, max_total, ev["output"], ev["result"], repairing=False)
            yield render()

        elif etype == "repair_start":
            n = ev["n"]
            data = pipeline._iter_store.get(n, {})
            if data:
                iter_cards[n] = _iter_card(
                    n, max_total, data["output"], data["result"], repairing=True
                )
                yield render()

        elif etype == "repair_done":
            n = ev["n"]
            data = pipeline._iter_store.get(n, {})
            if data:
                iter_cards[n] = _iter_card(
                    n, max_total, data["output"], data["result"], repairing=False
                )
                yield render()

        elif etype == "success":
            final_html = _final_card(ev["output"], ev["result"])
            yield render()

        elif etype == "max_iter":
            final_html = _maxiter_card(ev["output"], ev["result"])
            yield render()

        elif etype == "error":
            final_html = (
                f'<div class="pc fail"><h3>Error</h3>'
                f'<div class="status">{html.escape(str(ev.get("msg", "unknown error")))}</div></div>'
            )
            yield render()

        elif etype == "done":
            yield render()
            break


# ─── Gradio layout ────────────────────────────────────────────────────────────

HEADER_MD = """
# Self-Validating Multi-LLM Pipeline
Select a problem case and click **Run Pipeline** to watch the system iteratively generate and self-correct its output in real time.

> **Phase 1** — A verifier LLM writes a `verify()` function from the problem spec.
> **Phase 2** — A generator LLM produces candidate outputs; verifier feedback drives self-correction.
"""

with gr.Blocks(
    title="Self-Validating Multi-LLM Pipeline",
    theme=gr.themes.Soft(primary_hue="blue", neutral_hue="slate"),
    css=".gradio-container { max-width: 1200px !important; }",
) as demo:

    gr.Markdown(HEADER_MD)

    with gr.Row(equal_height=False):
        # ── Left panel ────────────────────────────────────────────────────────
        with gr.Column(scale=1, min_width=300):
            case_dd = gr.Dropdown(
                choices=CASE_CHOICES,
                value=CASE_CHOICES[0],
                label="Problem Case",
                interactive=True,
            )
            max_iter_sl = gr.Slider(
                minimum=1, maximum=15, value=5, step=1,
                label="Max Iterations",
                interactive=True,
            )
            run_btn = gr.Button("▶  Run Pipeline", variant="primary", size="lg")

            gr.Markdown("---")
            gr.Markdown("### Problem")
            prompt_box = gr.Textbox(
                label="Prompt", interactive=False, lines=3, max_lines=5,
            )
            constraints_box = gr.Textbox(
                label="Constraints", interactive=False, lines=10, max_lines=15,
            )

        # ── Right panel ───────────────────────────────────────────────────────
        with gr.Column(scale=2):
            gr.Markdown("### Pipeline Progress")
            progress_html = gr.HTML(
                value=_wrap(['<div class="pc"><div class="status">Select a case and click Run to begin.</div></div>']),
            )

    # ── Wire events ───────────────────────────────────────────────────────────
    case_dd.change(
        fn=on_case_change,
        inputs=case_dd,
        outputs=[prompt_box, constraints_box],
    )

    # Populate on load
    demo.load(
        fn=on_case_change,
        inputs=case_dd,
        outputs=[prompt_box, constraints_box],
    )

    run_btn.click(
        fn=run_pipeline,
        inputs=[case_dd, max_iter_sl],
        outputs=progress_html,
    )


if __name__ == "__main__":
    demo.queue()
    demo.launch(share=False, inbrowser=True)
