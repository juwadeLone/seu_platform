# Inject real data JSON into the template -> seu_case.html (single file, offline-openable)
import io, os

BASE = r"C:\hermes\layout_ecc_platform\showcase"
tpl = open(os.path.join(BASE, "seu_case.template.html"), encoding="utf-8").read()
spectra = open(os.path.join(BASE, "spectra.json"), encoding="utf-8").read().strip()
layout = open(os.path.join(BASE, "layout.json"), encoding="utf-8").read().strip()
html = tpl.replace("/*__SPECTRA__*/", spectra).replace("/*__LAYOUT__*/", layout)
out = os.path.join(BASE, "seu_case.html")
with io.open(out, "w", encoding="utf-8") as f:
    f.write(html)
print("written:", out, len(html), "bytes")
assert "__SPECTRA__" not in html and "__LAYOUT__" not in html
