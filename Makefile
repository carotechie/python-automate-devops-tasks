# Atajos del repo. En Windows sin make, mira los comandos equivalentes en docs/.
PYTHON ?= python3
VENV   := .venv
BIN    := $(VENV)/bin
CLUSTER := pyladies-lab
KCTX   := kind-$(CLUSTER)
ENDPOINT := http://localhost:4566

.PHONY: help setup test lint format lab-up lab-down lab-aws-up lab-k8s-up lab-status demo

help: ## Muestra esta ayuda
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

setup: ## Crea el entorno virtual e instala dependencias
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements-dev.txt
	@echo "Listo. Activa el entorno con: source $(VENV)/bin/activate"

test: ## Corre los tests
	$(BIN)/pytest

lint: ## Revisa el código con ruff
	$(BIN)/ruff check .

format: ## Corrige lo que ruff pueda arreglar solo
	$(BIN)/ruff check --fix .

lab-up: lab-aws-up lab-k8s-up ## Levanta LocalStack + kind y carga datos de ejemplo
	@echo ""
	@echo "Laboratorio listo. Ahora ejecuta: source lab/lab.env"

lab-aws-up:
	docker compose -f lab/docker-compose.yml up -d --wait
	AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test $(BIN)/python lab/seed_localstack.py --endpoint-url $(ENDPOINT)

lab-k8s-up:
	@kind get clusters 2>/dev/null | grep -qx $(CLUSTER) || kind create cluster --config lab/kind-config.yaml
	kubectl --context $(KCTX) apply -f lab/k8s-broken/
	kubectl --context $(KCTX) -n lab rollout status deployment/checkout --timeout=180s
	kubectl --context $(KCTX) apply -f lab/k8s-broken/incident/
	@echo "Los CrashLoopBackOff tardan 1-2 minutos en aparecer."

demo: ## Corre los scripts 02 a 05 contra el laboratorio
	@set -a; . lab/lab.env; set +a; \
	echo "\n### 02 · find_ec2.py --tag env=staging"; $(BIN)/python 02-buscar-recursos/find_ec2.py --tag env=staging; \
	echo "\n### 03 · pods_check.py"; $(BIN)/python 03-pods-con-fallas/pods_check.py || true; \
	echo "\n### 04 · triage.py --namespace lab --app checkout"; $(BIN)/python 04-triage-incidentes/triage.py --namespace lab --app checkout --output-dir reports; \
	echo "\n### 05 · weekly_report.py --env staging"; $(BIN)/python 05-reportes/weekly_report.py --env staging

lab-status: ## Muestra el estado del laboratorio
	docker compose -f lab/docker-compose.yml ps
	kubectl --context $(KCTX) -n lab get pods

lab-down: ## Destruye LocalStack y el cluster kind
	-docker compose -f lab/docker-compose.yml down -v
	-kind delete cluster --name $(CLUSTER)
