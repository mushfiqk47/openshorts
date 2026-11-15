"""AI provider adapters behind the _run_ai_stage dispatch seam.

CLAUDE.md rule 2: stage call sites never import a client module directly —
they go through ai.dispatch._run_ai_stage. Each provider is a thin adapter
over one shared transport (ai/openai_compat.py) or its own (Gemini, via
ai/gemini.py; OpenRouter keeps its own rotation logic in ai/openrouter.py).
"""
