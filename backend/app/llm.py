import ast
import json
import math
import operator
import re

import anthropic

from .config import settings

_client = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)
    return _client


TEACHER_SYSTEM = r"""You are Dr. Asha, a warm and patient chemistry teacher for Class {grade} students following the NCERT-aligned higher secondary syllabus. You are speaking aloud to a student, so write the way a good teacher talks: short paragraphs, plain sentences, no tables, no emoji.

Ground rules
- Facts, definitions, data and reactions must come from the numbered CONTEXT excerpts. Cite them inline like [1] or [2]. Never invent page numbers, data or sources.
- If the CONTEXT does not cover the question, say so plainly. You may add one or two cautious sentences of general chemistry if you are sure of them, and suggest the student check their textbook or ask their class teacher.
- Use the calculator tool for every numerical calculation; never do arithmetic in your head. Show the steps and units.
- Write formulas in LaTeX: inline $...$, and reactions as $\ce{...}$ (mhchem), for example $\ce{2H2 + O2 -> 2H2O}$.
- Be encouraging, never condescending. If the student seems confused, try a different analogy rather than repeating yourself.
- Stay on chemistry and the student's studies.
"""


def teacher_system(grade: str) -> str:
    return TEACHER_SYSTEM.replace("{grade}", grade)


def lesson_prompt(topic_title: str, unit_title: str, context: str) -> str:
    return (
        f"CONTEXT:\n{context}\n\n"
        f"Teach the topic \"{topic_title}\" (unit: {unit_title}) to the student now. "
        "Structure it as: a one-sentence hook, a clear explanation of the core idea, "
        "one worked example, and finish with ONE short question to check understanding. "
        "Keep it under 350 words and speakable."
    )


def doubt_prompt(question: str, context: str, topic_title: str) -> str:
    return (
        f"CONTEXT:\n{context}\n\n"
        f"The student is currently studying \"{topic_title}\" and asks:\n{question}"
    )


# ---------- calculator tool (safe arithmetic only) ----------

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg,
    ast.UAdd: operator.pos, ast.Mod: operator.mod,
}
_FUNCS = {
    "sqrt": math.sqrt, "log": math.log, "ln": math.log, "log10": math.log10,
    "exp": math.exp, "sin": math.sin, "cos": math.cos, "tan": math.tan, "abs": abs,
}
_CONSTS = {"pi": math.pi, "e": math.e}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError("exponent too large")
        return _OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    raise ValueError("unsupported expression")


def calculate(expression: str) -> str:
    try:
        expr = expression.replace("^", "**").replace("×", "*").replace("÷", "/")
        value = _eval(ast.parse(expr, mode="eval"))
        return f"{value:.6g}"
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


TOOLS = [{
    "name": "calculator",
    "description": (
        "Evaluate an arithmetic expression exactly. Supports + - * / ** %, parentheses, "
        "sqrt, log (natural), log10, exp, sin, cos, tan, and constants pi and e. "
        "Use scientific notation like 6.022e23."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
    },
}]


def stream_answer(system: str, messages: list[dict], max_tokens: int = 1500):
    """Yield text deltas; transparently runs calculator tool calls."""
    messages = list(messages)
    for _ in range(6):  # bounded tool loop
        with client().messages.stream(
            model=settings.model, max_tokens=max_tokens,
            system=system, messages=messages, tools=TOOLS,
        ) as stream:
            for text in stream.text_stream:
                yield text
            final = stream.get_final_message()
        if final.stop_reason != "tool_use":
            return
        messages.append({"role": "assistant", "content": final.content})
        results = []
        for block in final.content:
            if block.type == "tool_use":
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": calculate(block.input.get("expression", "")),
                })
        messages.append({"role": "user", "content": results})
        yield " "  # keep the stream alive between tool rounds


def make_quiz(grade: str, topic_title: str, context: str, n: int = 3) -> list[dict]:
    prompt = (
        f"CONTEXT:\n{context}\n\n"
        f"Write {n} multiple-choice questions on \"{topic_title}\" for a Class {grade} student, "
        "based only on the CONTEXT. Mix recall and application. "
        "Reply with ONLY a JSON array; each item: "
        '{"q": str, "options": [4 strings], "answer": 0-3 index, "explanation": str}. '
        "Use $...$ LaTeX for formulas."
    )
    resp = client().messages.create(
        model=settings.model, max_tokens=2000,
        system="You write accurate, unambiguous chemistry quiz questions.",
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    match = re.search(r"\[.*\]", text, re.S)
    items = json.loads(match.group(0)) if match else []
    return [
        i for i in items
        if isinstance(i.get("options"), list) and len(i["options"]) == 4
        and isinstance(i.get("answer"), int) and 0 <= i["answer"] < 4
    ][:n]
