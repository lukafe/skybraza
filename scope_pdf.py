"""
Relatório PDF do escopo IN 701 (resumo executivo + incisos + prontidão do corpus).
Usa fpdf2 com fontes core Helvetica e codificação cp1252 (Europa ocidental / PT-BR).
"""

from __future__ import annotations

import io
from datetime import date
from typing import Any

from fpdf import FPDF


def _pdf_text(value: Any, *, max_len: int = 4000) -> str:
    if value is None:
        return ""
    s = str(value).replace("\r\n", "\n").replace("\r", "\n")
    if len(s) > max_len:
        s = s[: max_len - 1] + "…"
    return s.encode("cp1252", errors="replace").decode("cp1252")


def _labels(lang: str) -> dict[str, str]:
    en = lang == "en"
    if en:
        return {
            "title": "IN 701 — Scope summary report",
            "subtitle": "CertiK · indicative scope (BCB Instruction 701)",
            "institution": "Institution",
            "track": "Track",
            "date": "Date",
            "matrix_ver": "Matrix version",
            "matrix_upd": "Matrix last updated",
            "summary": "Summary",
            "in_scope": "Clauses in audit scope",
            "mandatory": "Mandatory (matrix)",
            "triggered": "Triggered by answers",
            "out_scope": "Out of audit scope",
            "readiness": "Corpus readiness index (0–100)",
            "corp_counts": "Corpus status counts",
            "complete": "complete",
            "partial": "partial",
            "incomplete": "incomplete",
            "other": "other",
            "sec_in": "Clauses in scope",
            "sec_out": "Clauses out of scope",
            "id": "ID",
            "item": "Item",
            "origin": "Scope origin",
            "why_audit": "Why subject to audit",
            "bcb_hint": "BCB report guidance",
            "why_out": "Why not in this scope",
            "footer": "Indicative result — formal delimitation before the BCB is validated in the official process.",
        }
    return {
        "title": "Relatório de escopo — IN 701",
        "subtitle": "CertiK · escopo orientativo (Instrução Normativa BCB 701)",
        "institution": "Instituição",
        "track": "Trilha",
        "date": "Data",
        "matrix_ver": "Versão da matriz",
        "matrix_upd": "Última atualização da matriz",
        "summary": "Resumo",
        "in_scope": "Incisos no escopo de auditoria",
        "mandatory": "Obrigatórios (matriz)",
        "triggered": "Acionados por respostas",
        "out_scope": "Fora do escopo de auditoria",
        "readiness": "Índice de prontidão do corpus (0–100)",
        "corp_counts": "Contagens de estado do corpus",
        "complete": "completo",
        "partial": "parcial",
        "incomplete": "incompleto",
        "other": "outro",
        "sec_in": "Incisos no escopo",
        "sec_out": "Incisos fora do escopo",
        "id": "ID",
        "item": "Item",
        "origin": "Origem no escopo",
        "why_audit": "Por que será auditado",
        "bcb_hint": "Orientação relatório ao BCB",
        "why_out": "Por que não neste escopo",
        "footer": "Resultado orientativo — a delimitação perante o BCB é validada em processo formal.",
    }


class _ScopePDF(FPDF):
    def __init__(self, lang: str) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.core_fonts_encoding = "cp1252"
        self.set_auto_page_break(auto=True, margin=16)
        self._lang = lang
        self._labels = _labels(lang)

    def header(self) -> None:
        self.set_font("Helvetica", "B", 14)
        self.multi_cell(self.epw, 8, _pdf_text(self._labels["title"]))
        self.set_font("Helvetica", "", 9)
        self.set_text_color(80, 80, 80)
        self.multi_cell(self.epw, 5, _pdf_text(self._labels["subtitle"]))
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(100, 100, 100)
        self.multi_cell(self.epw, 4, _pdf_text(self._labels["footer"], max_len=500))
        self.set_text_color(0, 0, 0)


def build_scope_pdf_bytes(
    scope_response: dict[str, Any],
    *,
    lang: str = "pt",
    matrix_version: str | None = None,
    matrix_last_updated: str | None = None,
) -> io.BytesIO:
    """
    Monta PDF a partir do mesmo dicionário usado em excel_export (institution, track,
    incisos_*, resumo, corpus_readiness).
    """
    lang = "en" if lang == "en" else "pt"
    L = _labels(lang)
    pdf = _ScopePDF(lang)
    pdf.add_page()
    pdf.set_font("Helvetica", "", 10)
    epw = pdf.epw

    inst = _pdf_text(scope_response.get("institution", ""))
    track = _pdf_text(scope_response.get("track", ""))
    pdf.multi_cell(epw, 6, f"{L['institution']}: {inst or '—'}")
    pdf.multi_cell(epw, 6, f"{L['track']}: {track or '—'}")
    pdf.multi_cell(epw, 6, f"{L['date']}: {_pdf_text(date.today().isoformat())}")
    if matrix_version:
        pdf.multi_cell(epw, 6, f"{L['matrix_ver']}: {_pdf_text(matrix_version)}")
    if matrix_last_updated:
        pdf.multi_cell(epw, 6, f"{L['matrix_upd']}: {_pdf_text(matrix_last_updated)}")

    pdf.ln(3)
    resumo = scope_response.get("resumo") or {}
    na = resumo.get("total_sujeitos_auditoria", 0)
    mand = resumo.get("obrigatorios_matriz", 0)
    cond = resumo.get("acionados_por_respostas", 0)
    nf = resumo.get("total_fora_escopo_auditoria", 0)

    pdf.set_font("Helvetica", "B", 11)
    pdf.multi_cell(epw, 7, L["summary"])
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(epw, 5, f"{L['in_scope']}: {na}")
    pdf.multi_cell(epw, 5, f"{L['mandatory']}: {mand}")
    pdf.multi_cell(epw, 5, f"{L['triggered']}: {cond}")
    pdf.multi_cell(epw, 5, f"{L['out_scope']}: {nf}")

    cr = scope_response.get("corpus_readiness") or {}
    idx = cr.get("readiness_index_0_100")
    counts = cr.get("counts") or {}
    if idx is not None:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(epw, 6, f"{L['readiness']}: {idx}")
        pdf.set_font("Helvetica", "", 9)
        c0 = counts.get("completo", 0)
        c1 = counts.get("parcial", 0)
        c2 = counts.get("incompleto", 0)
        c3 = counts.get("outro", 0)
        pdf.multi_cell(
            epw,
            5,
            f"{L['corp_counts']}: {L['complete']}={c0}, {L['partial']}={c1}, "
            f"{L['incomplete']}={c2}, {L['other']}={c3}",
        )

    sujeitos = scope_response.get("incisos_sujeitos_auditoria") or []
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.multi_cell(epw, 7, f"{L['sec_in']} ({len(sujeitos)})")
    pdf.set_font("Helvetica", "", 8)

    for row in sujeitos:
        if not isinstance(row, dict):
            continue
        iid = _pdf_text(row.get("inciso_id", ""))
        item = _pdf_text(row.get("item", ""), max_len=500)
        orig = _pdf_text(row.get("origem_escopo", ""), max_len=200)
        why = _pdf_text(row.get("por_que_sera_auditado", ""), max_len=1200)
        hint = _pdf_text(row.get("orientacao_relatorio_bcb", ""), max_len=800)
        pdf.set_font("Helvetica", "B", 8)
        pdf.multi_cell(epw, 4, f"{L['id']}: {iid}")
        pdf.set_font("Helvetica", "", 8)
        pdf.multi_cell(epw, 4, f"{L['item']}: {item}")
        pdf.multi_cell(epw, 4, f"{L['origin']}: {orig}")
        pdf.multi_cell(epw, 4, f"{L['why_audit']}: {why}")
        if hint.strip():
            pdf.multi_cell(epw, 4, f"{L['bcb_hint']}: {hint}")
        pdf.ln(1)

    fora = scope_response.get("incisos_fora_escopo_auditoria") or []
    pdf.add_page()
    epw = pdf.epw
    pdf.set_font("Helvetica", "B", 11)
    pdf.multi_cell(epw, 7, f"{L['sec_out']} ({len(fora)})")
    pdf.set_font("Helvetica", "", 8)

    for row in fora:
        if not isinstance(row, dict):
            continue
        iid = _pdf_text(row.get("inciso_id", ""))
        item = _pdf_text(row.get("item", ""), max_len=400)
        why = _pdf_text(row.get("por_que_nao_neste_escopo", ""), max_len=900)
        pdf.set_font("Helvetica", "B", 8)
        pdf.multi_cell(epw, 4, f"{L['id']}: {iid}")
        pdf.set_font("Helvetica", "", 8)
        pdf.multi_cell(epw, 4, f"{L['item']}: {item}")
        pdf.multi_cell(epw, 4, f"{L['why_out']}: {why}")
        pdf.ln(1)

    out = io.BytesIO()
    pdf.output(out)
    out.seek(0)
    return out


__all__ = ["build_scope_pdf_bytes"]
