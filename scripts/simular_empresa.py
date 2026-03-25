"""
Simulação: uma VASP intermediária responde ao questionário IN 701 (console).
Execute: python scripts/simular_empresa.py
"""

from __future__ import annotations

import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from questionnaire_loader import get_blocks
from rules_engine import compute_scope, questions_by_block  # noqa: E402

# Perfil fictício: intermediária com LP no exterior, nuvem, ramp fiat/crypto, sem staking próprio.
EMPRESA = "CryptoBridge Intermediação Ltda. (exemplo fictício)"

RESPOSTAS_EMPRESA: dict = {
    "P1": True,
    "P2": True,
    "P3": True,
    "P_arch": "mpc_mixed",
    "P4": True,
    "P5": True,
    "P6": False,
    "P_tp": ["lp", "cloud_infra", "fiat_bank"],
    "P7": True,
    "P8": False,
    "P9": True,
    "P_list": "own_committee",
    "P_narr": (
        "Cliente deposita via PIX (IF parceira); saldo interno em BRL; ordem roteada a LP no exterior; "
        "saque para carteira on-chain do cliente após liquidação."
    ),
    "P_reserves": False,
    "P_surveillance": True,
}

COMENTARIOS_AUDITOR: dict[str, str] = {
    "P1": "Sim — endereços por cliente; MPC com papéis operacionais da plataforma.",
    "P2": "Sim — trânsito por omnibus antes do destino final.",
    "P3": "Sim — saldo em reais até execução da ordem.",
    "P_arch": "MPC misto — VASP e terceiros com papéis de controle.",
    "P4": "Sim — liquidez de provedor no exterior / sem autorização BCB direta.",
    "P5": "Sim — ledger e motor em nuvem de terceiro com cláusulas de auditoria.",
    "P6": "Não — sem outro terceiro estrangeiro relevante além do LP.",
    "P_tp": "Liquidez, nuvem e IF fiat como terceiros materiais.",
    "P7": "Sim — stablecoins e ativos referenciados a fiat.",
    "P8": "Não — sem staking/rendimento.",
    "P9": "Sim — APIs com IF para on/off-ramp.",
    "P_list": "Critérios próprios de listagem (comitê interno).",
    "P_narr": "Narrativa alinhada ao desenho operacional apresentado.",
    "P_reserves": "Não — sem programa público de proof of reserves neste recorte.",
    "P_surveillance": "Sim — processos documentados (pergunta só para relatório).",
}


def _fmt_answer(q: dict, raw: object) -> str:
    t = q.get("type", "yes_no")
    if t == "yes_no":
        return "Sim" if raw else "Não"
    if t == "single_choice":
        if not raw:
            return "(não selecionado)"
        for o in q.get("options") or []:
            if o["id"] == raw:
                return str(o["label"])
        return str(raw)
    if t == "multi_choice":
        if not raw:
            return "(nenhum)"
        ids = raw if isinstance(raw, list) else []
        labels = []
        for i in ids:
            for o in q.get("options") or []:
                if o["id"] == i:
                    labels.append(str(o["label"]))
                    break
            else:
                labels.append(str(i))
        return "; ".join(labels)
    if t == "text_short":
        s = (raw or "").strip() if isinstance(raw, str) else str(raw or "")
        return s[:200] + ("…" if len(s) > 200 else "") if s else "(vazio)"
    return str(raw)


def main() -> None:
    print("=" * 72)
    print("CertiK — Simulação de respostas (VASP intermediária)")
    print("=" * 72)
    print(f"\nInstituição: {EMPRESA}\n")

    by_block = questions_by_block()
    for mb in get_blocks():
        bid = str(mb["id"])
        title = mb.get("title", bid)
        print("-" * 72)
        print(f"Bloco {bid} — {title}")
        print("-" * 72)
        for q in by_block.get(bid, []):
            rid = q["id"]
            raw = RESPOSTAS_EMPRESA.get(rid, _default_for_type(q))
            resp = _fmt_answer(q, raw)
            print(f"\n[{rid}] {q.get('text', '')}")
            print(f"    Resposta (simulada): **{resp}**")
            print(f"    Comentário: {COMENTARIOS_AUDITOR.get(rid, '')}")

    df, meta = compute_scope(RESPOSTAS_EMPRESA)

    print("\n" + "=" * 72)
    print("Resultado — Dashboard de escopo (simulado)")
    print("=" * 72)
    total = meta["total_count"]
    mand = meta["mandatory_count"]
    cond = meta["conditional_count"]
    print(
        f"\nCom base nas respostas, a auditoria focará em {total} itens de controle, "
        f"sendo {mand} obrigatórios e {cond} baseados em resposta.\n"
    )
    opts = {"display.max_columns": None, "display.width": 200, "display.max_colwidth": 60}
    old = {k: pd.get_option(k) for k in opts}
    try:
        for k, v in opts.items():
            pd.set_option(k, v)
        print(df.to_string(index=False))
    finally:
        for k, v in old.items():
            pd.set_option(k, v)


def _default_for_type(q: dict):
    t = q.get("type")
    if t == "yes_no":
        return False
    if t == "single_choice":
        return None
    if t == "multi_choice":
        return []
    if t == "text_short":
        return ""
    return None


if __name__ == "__main__":
    main()
