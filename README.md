# CertiK VASP Scoping

Ferramenta de scoping regulatório **IN 701 / Resolução BCB nº 520** para prestadores de serviços de ativos virtuais (VASPs) no Brasil.

## Funcionalidades

- **Questionário por trilha** — Intermediária, Custodiante, Corretora
- **Motor de regras** — cruza matriz de cobertura + respostas para determinar incisos no escopo de auditoria
- **Journey 2** — checklist de evidências, smart contract audit e pentest por inciso
- **Exportação** — Excel e PDF com resultados completos
- **Painel Admin** — listagem, pesquisa, filtros, export CSV e detalhe de cada submissão
- **i18n** — Português (padrão) e Inglês

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | FastAPI + Pydantic v2 |
| Regras | PyYAML, pandas, motor declarativo |
| DB | SQLAlchemy 2 (SQLite local, PostgreSQL produção) |
| Auth Admin | Google OAuth ou senha fallback + HMAC session tokens |
| Exports | openpyxl (Excel), fpdf2 (PDF) |
| Frontend | HTML/CSS/JS (ES modules, sem framework) |
| Deploy | Vercel (serverless) |

## Setup Local

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Aceder em `http://localhost:8000` (questionário) e `http://localhost:8000/admin` (painel admin).

Para persistência local, defina:

```bash
export DATABASE_URL="sqlite:///submissions.db"
export ADMIN_SECRET="qualquer-string-secreta"
```

## Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|----------|------------|-----------|
| `DATABASE_URL` | Sim (prod) | `postgresql://user:pass@host/db` para produção, `sqlite:///x.db` para local |
| `ADMIN_SECRET` | Sim | Chave HMAC para tokens de sessão admin (também usada como senha se `ADMIN_PASSWORD` não definida) |
| `ADMIN_PASSWORD` | Não | Senha separada para login admin (fallback: usa `ADMIN_SECRET`) |
| `GOOGLE_CLIENT_ID` | Não | Ativa Google OAuth no admin (restringe a `@certik.com`); sem ele usa login por senha |
| `CERTIK_API_KEY` | Não | Se definida, exige header `X-Certik-Api-Key` em rotas públicas da API |
| `LOG_LEVEL` | Não | `DEBUG`, `INFO` (padrão), `WARNING`, `ERROR` |
| `CORS_ALLOWED_ORIGINS` | Não | Lista CSV de origens; padrão `*` |
| `CERTIK_ENABLE_CUSTODIANTE_TRACK` | Não | `0`/`false`/`off` desativa a trilha |
| `CERTIK_ENABLE_CORRETORA_TRACK` | Não | `0`/`false`/`off` desativa a trilha |

## Deploy na Vercel

1. Conectar o repo ao projeto Vercel
2. Em **Settings > Environment Variables**, definir `DATABASE_URL`, `ADMIN_SECRET` (e opcionalmente `GOOGLE_CLIENT_ID`)
3. Push para `main` — deploy automático

Após editar ficheiros em `public/`, executar antes do commit:

```bash
python scripts/sync_vercel_public.py
```

## Estrutura do Projeto

```
main.py                  # API FastAPI (rotas, middleware, admin)
db.py                    # Persistência SQLAlchemy
rules_engine.py          # Motor de regras IN 701
matrix_loader.py         # COVERAGE_MATRIX.yaml loader
questionnaire_loader.py  # Questionnaire YAML loader
evidence_requests.py     # Journey 2 (evidências por inciso)
scope_narrative.py       # Narrativas + supressão custódia
readiness.py             # Corpus readiness index
excel_export.py          # Export Excel
scope_pdf.py             # Export PDF
rate_limit.py            # Rate limiting (best-effort serverless)
laws/                    # YAML de regras, matrizes, questionários
public/                  # Frontend SPA (HTML, CSS, JS)
vercel_public/           # Espelho de public/ para Vercel
scripts/                 # Utilitários (sync, validação)
tests/                   # Testes pytest
```
