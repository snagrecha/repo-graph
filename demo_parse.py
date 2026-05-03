#!/usr/bin/env python3
"""
Quick smoke-test: parse a directory with the current ingestion layer
and print a summary of what was extracted.

Usage:
    python demo_parse.py [path-to-repo]   (defaults to this repo)
"""
import os
import sys
from collections import Counter

from codenexus.graph.schema import EdgeType, NodeType
from codenexus.ingestion.parser import parse_file

repo_root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(__file__)

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".mypy_cache", ".ruff_cache", "dist", "build", ".pytest_cache",
}

all_nodes = []
all_edges = []
files_parsed = 0
files_skipped = 0

for dirpath, dirnames, filenames in os.walk(repo_root):
    dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
    for fname in filenames:
        fpath = os.path.join(dirpath, fname)
        result = parse_file(fpath, repo_root)
        if result is None:
            files_skipped += 1
            continue
        nodes, edges = result
        all_nodes.extend(nodes)
        all_edges.extend(edges)
        files_parsed += 1

# Summary
node_counts = Counter(n.type for n in all_nodes)
edge_counts = Counter(e.type for e in all_edges)

print(f"\n{'='*50}")
print(f"  codenexus parse summary")
print(f"  root: {repo_root}")
print(f"{'='*50}")
print(f"\nFiles:  {files_parsed} parsed,  {files_skipped} skipped (unsupported/too large)\n")
print("Nodes:")
for nt in NodeType:
    print(f"  {nt.value:<12}  {node_counts[nt]:>5}")
print(f"  {'TOTAL':<12}  {len(all_nodes):>5}")
print("\nEdges:")
for et in EdgeType:
    print(f"  {et.value:<16}  {edge_counts[et]:>5}")
print(f"  {'TOTAL':<16}  {len(all_edges):>5}")

# Sample: show first 10 functions found
funcs = [n for n in all_nodes if n.type == NodeType.FUNCTION][:10]
if funcs:
    print(f"\nSample functions (first {len(funcs)}):")
    for n in funcs:
        rel = os.path.relpath(n.file_path, repo_root)
        print(f"  {n.name:<30}  {rel}:{n.start_line}")

# Sample: show a few call edges
calls = [e for e in all_edges if e.type == EdgeType.CALLS][:5]
if calls:
    node_by_id = {n.id: n for n in all_nodes}
    print(f"\nSample calls (first {len(calls)}):")
    for e in calls:
        src = node_by_id.get(e.source_id)
        tgt = node_by_id.get(e.target_id)
        if src and tgt:
            print(f"  {src.name}  ->  {tgt.name}")

print()
