# Scan the vault: nodes = all .md files, edges = [[wikilinks]] between them.
# Output: graph.json for the 3D galaxy page.
import os, re, json, collections

VAULT = r"C:\hermes\fpgahorizons-journal"
OUT = r"C:\hermes\layout_ecc_platform\showcase\graph.json"

LINK_RE = re.compile(r"\[\[([^\[\]|#]+)(?:#[^\[\]|]*)?(?:\|[^\[\]]*)?\]\]")

nodes = {}   # id = relative path without .md
edges = set()

for dirpath, dirnames, filenames in os.walk(VAULT):
    dirnames[:] = [d for d in dirnames if d not in (".obsidian", ".trash", ".git")]
    for fn in filenames:
        if not fn.lower().endswith(".md"):
            continue
        full = os.path.join(dirpath, fn)
        rel = os.path.relpath(full, VAULT)[:-3].replace(os.sep, "/")
        with open(full, encoding="utf-8", errors="replace") as f:
            text = f.read()
        m = re.match(r"^---\n(.*?)\n---", text, re.S)
        fm = m.group(1) if m else ""
        cat = re.search(r"^category:\s*(.+)$", fm, re.M)
        typ = re.search(r"^type:\s*(.+)$", fm, re.M)
        top = rel.split("/")[0]
        if top == "articles":
            group = "articles/" + rel.split("/")[1]
        elif top in ("wiki", "raw", "templates", "lab-notes"):
            group = top if top != "wiki" else "wiki/" + (rel.split("/")[1] if len(rel.split("/")) > 2 else "root")
        else:
            group = "root"
        nodes[rel] = {
            "name": os.path.basename(rel),
            "group": group,
            "category": (cat.group(1).strip().strip('"') if cat else ""),
            "type": (typ.group(1).strip().strip('"') if typ else ""),
            "links": [l.strip() for l in LINK_RE.findall(text)],
        }

# resolve links: try exact rel path, then basename match
by_base = collections.defaultdict(list)
for rel in nodes:
    by_base[os.path.basename(rel)].append(rel)

unresolved = collections.Counter()
for rel, n in nodes.items():
    for link in n["links"]:
        for cand in (link, link.rstrip("\\/"), re.sub(r"\.md$", "", link.rstrip("\\/"))):
            target = None
            if cand in nodes:
                target = cand
            elif cand in by_base:
                target = by_base[cand][0]
            elif "MOC-" + cand in nodes:
                target = "MOC-" + cand
            if target:
                break
        if target and target != rel:
            edges.add((rel, target))
        elif not target:
            unresolved[link] += 1

deg = collections.Counter()
for a, b in edges:
    deg[a] += 1; deg[b] += 1

graph = {
    "nodes": [{"id": r, "name": n["name"], "group": n["group"], "category": n["category"],
               "type": n["type"], "deg": deg[r]} for r, n in nodes.items()],
    "edges": [{"a": a, "b": b} for a, b in sorted(edges)],
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(graph, f, ensure_ascii=False, separators=(",", ":"))

print("nodes:", len(graph["nodes"]), "edges:", len(graph["edges"]))
print("density: %.4f" % (2 * len(edges) / (len(nodes) * (len(nodes) - 1))))
print("top hubs:", deg.most_common(8))
print("orphans:", sum(1 for r in nodes if deg[r] == 0))
print("unresolved link names (top):", unresolved.most_common(10))
