"""Builds the graphify knowledge graph for this repo.

Implements the graphify skill's remaining steps once the semantic-docs
extraction lands: B3 cache merge -> Part C (AST+semantic merge) -> Step 4
(build/cluster/report) -> graph.html -> multigraph health check.
Code-only fallback: if the semantic file never appears, builds from AST alone.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "graphify-out"
WAIT_SECONDS = 900

# --- wait for the semantic extraction (subagent output) ----------------------
sem_new = OUT / ".graphify_semantic_new.json"
deadline = time.time() + WAIT_SECONDS
while not sem_new.exists() and time.time() < deadline:
    time.sleep(5)

# --- Part B3: cache (empty on a fresh build) + new semantic ------------------
cached = {"nodes": [], "edges": [], "hyperedges": [], "input_tokens": 0, "output_tokens": 0}
if sem_new.exists():
    new = json.loads(sem_new.read_text(encoding="utf-8"))
    deduped = {n["id"]: n for n in cached["nodes"]}
    for n in new.get("nodes", []):
        deduped.setdefault(n["id"], n)
    all_edges = cached["edges"] + new.get("edges", [])
    merged = {
        "nodes": list(deduped.values()),
        "edges": all_edges,
        "hyperedges": new.get("hyperedges", []),
        "input_tokens": new.get("input_tokens", 0),
        "output_tokens": new.get("output_tokens", 0),
    }
    (OUT / ".graphify_semantic.json").write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Semantic: {len(merged['nodes'])} nodes, {len(all_edges)} edges")
else:
    (OUT / ".graphify_semantic.json").write_text(
        json.dumps({"nodes": [], "edges": [], "hyperedges": [], "input_tokens": 0, "output_tokens": 0}, ensure_ascii=False),
        encoding="utf-8")
    print("Semantic: none (code-only graph)")

# --- Part C: merge AST + semantic -------------------------------------------
ast = json.loads((OUT / ".graphify_ast.json").read_text(encoding="utf-8"))
sem = json.loads((OUT / ".graphify_semantic.json").read_text(encoding="utf-8"))
for n in sem["nodes"]:
    n.setdefault("_origin", "semantic")
for e in sem["edges"]:
    e.setdefault("_origin", "semantic")
seen = {n["id"] for n in ast["nodes"]}
merged_nodes = list(ast["nodes"])
for n in sem["nodes"]:
    if n["id"] not in seen:
        merged_nodes.append(n)
        seen.add(n["id"])
merged = {
    "nodes": merged_nodes,
    "edges": ast["edges"] + sem["edges"],
    "hyperedges": sem.get("hyperedges", []),
    "input_tokens": sem.get("input_tokens", 0),
    "output_tokens": sem.get("output_tokens", 0),
}
(OUT / ".graphify_extract.json").write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Merged: {len(merged_nodes)} nodes, {len(merged['edges'])} edges "
      f"({len(ast['nodes'])} AST + {len(sem['nodes'])} semantic)")

# --- Step 4: build, cluster, analyze, export ---------------------------------
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.analyze import god_nodes, surprising_connections, suggest_questions
from graphify.report import generate
from graphify.export import to_json, generate_html

extraction = json.loads((OUT / ".graphify_extract.json").read_text(encoding="utf-8"))
detection = json.loads((OUT / ".graphify_detect.json").read_text(encoding="utf-8"))

G = build_from_json(extraction, root=str(ROOT), directed=False)
if G.number_of_nodes() == 0:
    print("ERROR: Graph is empty - extraction produced no nodes.")
    raise SystemExit(1)
communities = cluster(G)
cohesion = score_all(G, communities)
tokens = {"input": extraction.get("input_tokens", 0), "output": extraction.get("output_tokens", 0)}
gods = god_nodes(G)
surprises = surprising_connections(G, communities)
labels = {cid: "Community " + str(cid) for cid in communities}
questions = suggest_questions(G, communities, labels)

wrote = to_json(G, communities, str(OUT / "graph.json"), force=True)
if not wrote:
    print("ERROR: graph export refused to write.")
    raise SystemExit(1)
report = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, str(ROOT), suggested_questions=questions)
(OUT / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
generate_html(G, communities, str(OUT / "graph.html"), community_labels=labels)
analysis = {
    "communities": {str(k): v for k, v in communities.items()},
    "cohesion": {str(k): v for k, v in cohesion.items()},
    "gods": gods,
    "surprises": surprises,
    "questions": questions,
}
(OUT / ".graphify_analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(communities)} communities")
print("Build complete.")
