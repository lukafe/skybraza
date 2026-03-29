"""Verificação rápida de ficheiros corpus ausentes em todas as trilhas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from readiness import validate_corpus_files

for track in ("intermediaria", "custodiante", "corretora"):
    warnings = validate_corpus_files(track)
    if warnings:
        print(f"\n[{track.upper()}] FICHEIROS AUSENTES:")
        for w in warnings:
            iid = w["inciso_id"]
            status = w["corpus_status_yaml"]
            missing = w["ficheiros_ausentes"]
            print(f"  [{iid}] status_yaml={status} | ausentes={missing}")
    else:
        print(f"[{track.upper()}] OK — todos os ficheiros referenciados existem em laws/")
