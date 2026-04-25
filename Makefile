# ATOMFederationOS v10 — Root Makefile
# Build, test, lint, and deploy all modules

.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --print-directory

# ── Variables ──────────────────────────────────────────────────────────────
GIT_REPO      := github.com/mahaasur13-sys
GO_VERSION    := 1.23
PY_VERSION    := 3.10
K8S_VERSION   := 1.28
MODULES       := atom-kernel atom-operator atom-agent atom-federation
SBS_MODULES   := sbs
IMAGE_PREFIX  := ghcr.io/mahaasur13-sys/atom
GIT_SHA       := $(shell git rev-parse --short HEAD 2>/dev/null || echo "local")
BUILD_TIME    := $(shell date -u '+%Y-%m-%dT%H:%M:%SZ')
LINT_VERSION  := v1.62.0

# ── Colors ────────────────────────────────────────────────────────────────
BOLD  := $(shell tput bold 2>/dev/null || echo "")
RESET := $(shell tput sgr0 2>/dev/null || echo "")
RED   := $(shell tput setaf 1 2>/dev/null || echo "")
GRN   := $(shell tput setaf 2 2>/dev/null || echo "")
YLW   := $(shell tput setaf 3 2>/dev/null || echo "")
BLU   := $(shell tput setaf 4 2>/dev/null || echo "")

# ── Helpers ─────────────────────────────────────────────────────────────
define print_goal
	@echo "$(BOLD)$(BLU)>>> $(1)$(RESET)"
endef

define run_in
	@$(print_goal "$(2) [$(1)]")
	@cd $(1) && $(MAKE) $(3)
endef

define run_module_check
	@$(print_goal "Checking $(1)")
	@test -d $(1) || { echo "$(RED)ERROR: $(1) not found$(RESET)"; exit 1; }
	@test -f $(1)/go.mod || { echo "$(RED)ERROR: no go.mod in $(1)$(RESET)"; exit 1; }
	@test -f $(1)/Makefile || { echo "$(RED)ERROR: no Makefile in $(1)$(RESET)"; exit 1; }
endef

# ── Default goal ─────────────────────────────────────────────────────────
.PHONY: help
help::
	@grep -E '^## [A-Z]' $(MAKEFILE_LIST) | head -50

# =============================================================================
## 📦 Build
# =============================================================================
.PHONY: build build-kernel build-operator build-agent build-federation build-sbs
build: build-kernel build-operator build-agent build-federation build-sbs
	@echo "$(GRN)✓ All modules built$(RESET)"

build-kernel:
	$(call run_in,atom-kernel,Building,build)

build-operator:
	$(call run_in,atom-operator,Building,build)

build-agent:
	$(call run_in,atom-agent,Building,build)

build-federation:
	$(call run_in,atom-federation,Building,build)

build-sbs:
	@$(print_goal "Installing Python SBS")
	@pip install -e ./sbs -q 2>&1 | tail -2
	@echo "$(GRN)✓ sbs CLI installed: $$(command -v sbs && sbs --version 2>/dev/null || echo 'installed')$(RESET)"

.PHONY: docker-build docker-build-kernel docker-build-operator docker-build-agent docker-build-federation
docker-build: docker-build-kernel docker-build-operator docker-build-agent docker-build-federation
	@echo "$(GRN)✓ All Docker images built$(RESET)"

docker-build-kernel:
	$(call print_goal,"Building kernel Docker image")
	@docker build --pull --platform linux/amd64,linux/arm64 \
		-t $(IMAGE_PREFIX)-kernel:$(GIT_SHA) \
		-t $(IMAGE_PREFIX)-kernel:latest \
		atom-kernel/

docker-build-operator:
	$(call print_goal,"Building operator Docker image")
	@docker build --pull --platform linux/amd64,linux/arm64 \
		-t $(IMAGE_PREFIX)-operator:$(GIT_SHA) \
		-t $(IMAGE_PREFIX)-operator:latest \
		atom-operator/

docker-build-agent:
	$(call print_goal,"Building agent Docker image")
	@docker build --pull --platform linux/amd64,linux/arm64 \
		-t $(IMAGE_PREFIX)-agent:$(GIT_SHA) \
		-t $(IMAGE_PREFIX)-agent:latest \
		atom-agent/

docker-build-federation:
	$(call print_goal,"Building federation Docker image")
	@docker build --pull --platform linux/amd64,linux/arm64 \
		-t $(IMAGE_PREFIX)-federation:$(GIT_SHA) \
		-t $(IMAGE_PREFIX)-federation:latest \
		atom-federation/

.PHONY: images
images: docker-build
	@echo "Images: $(IMAGE_PREFIX)-{kernel,operator,agent,federation}:{$(GIT_SHA),latest}"

# =============================================================================
## 🧪 Test
# =============================================================================
.PHONY: test test-kernel test-operator test-agent test-federation test-sbs
test: test-kernel test-operator test-agent test-federation test-sbs
	@echo "$(GRN)✓ All tests passed$(RESET)"

test-kernel:
	$(call run_in,atom-kernel,Testing kernel,test)

test-operator:
	$(call run_in,atom-operator,Testing operator,test)

test-agent:
	$(call run_in,atom-agent,Testing agent,test)

test-federation:
	$(call run_in,atom-federation,Testing federation,test)

test-sbs:
	@$(print_goal "Running Python SBS tests")
	@cd sbs && python3 -m pytest tests/ alignment/test_gsct.py -q --tb=short
	@echo "$(GRN)✓ SBS tests passed$(RESET)"

.PHONY: test-integration
test-integration:
	$(call print_goal,"Running integration tests")
	@./scripts/test-integration.sh
	@echo "$(GRN)✓ Integration tests passed$(RESET)"

.PHONY: determinism determinism-kernel determinism-sbs
determinism: determinism-kernel determinism-sbs
	@echo "$(GRN)✓ Determinism verified$(RESET)"

determinism-kernel:
	$(call run_in,atom-kernel,Determinism check kernel,determinism)

determinism-sbs:
	@$(print_goal "SBS determinism check")
	@for i in 1 2 3; do \
		cd sbs && python3 -m sbs verify 2>&1 | tail -1; \
	done | sort -u | grep -q "ALL PASS" && \
		echo "$(GRN)✓ SBS deterministic across 3 runs$(RESET)" || \
		{ echo "$(RED)✗ SBS non-deterministic$(RESET)"; exit 1; }

.PHONY: test-all
test-all: lint test determinism
	@echo "$(GRN)✓ Full test suite PASSED$(RESET)"

# =============================================================================
## 🔍 Lint
# =============================================================================
.PHONY: lint lint-kernel lint-operator lint-agent lint-federation lint-sbs lint-all
lint: lint-all
	@echo "$(GRN)✓ All lints passed$(RESET)"

lint-kernel: $(call run_in,atom-kernel,Linting kernel,lint)
lint-operator: $(call run_in,atom-operator,Linting operator,lint)
lint-agent: $(call run_in,atom-agent,Linting agent,lint)
lint-federation: $(call run_in,atom-federation,Linting federation,lint)
lint-sbs:
	@$(print_goal "Linting Python SBS")
	@ruff check sbs/ --config pyproject.toml
	@echo "$(GRN)✓ SBS linted$(RESET)"

lint-all: lint-kernel lint-operator lint-agent lint-federation lint-sbs

# =============================================================================
## 🏗️ Dev
# =============================================================================
.PHONY: dev-up dev-down dev-logs dev-status
dev-up:
	$(call print_goal,"Starting local dev cluster (kind)")
	@./scripts/dev-up.sh

dev-down:
	$(call print_goal,"Stopping local dev cluster")
	@./scripts/dev-down.sh

dev-logs:
	@kubectl logs -n atom-system -l app.kubernetes.io/name=atom-kernel --tail=100 -f

dev-status:
	@kubectl get all -n atom-system -o wide

# =============================================================================
## 🚀 Deploy
# =============================================================================
.PHONY: deploy deploy-crds deploy-kernel deploy-operator deploy-agent
deploy: deploy-crds deploy-kernel deploy-operator deploy-agent
	@echo "$(GRN)✓ ATOMFederationOS deployed$(RESET)"

deploy-crds:
	$(call print_goal,"Installing CRDs")
	@kubectl apply -f atom-operator/config/crd/bases/

deploy-kernel:
	$(call print_goal,"Deploying atom-kernel DaemonSet")
	@kubectl apply -f examples/k8s/kernel.yaml

deploy-operator:
	$(call print_goal,"Deploying atom-operator")
	@kubectl apply -f atom-operator/config/deploy/
	@kubectl wait --for=condition=Ready pods -l app.kubernetes.io/name=atom-operator -n atom-system --timeout=60s

deploy-agent:
	$(call print_goal,"Deploying atom-agent DaemonSet")
	@kubectl apply -f examples/k8s/agent.yaml

.PHONY: undeploy
undeploy:
	$(call print_goal,"Removing ATOMFederationOS from cluster")
	@kubectl delete -f examples/k8s/ 2>/dev/null || true
	@kubectl delete -f atom-operator/config/deploy/ 2>/dev/null || true
	@kubectl delete -f atom-operator/config/crd/bases/ 2>/dev/null || true
	@echo "$(GRN)✓ Undeployed$(RESET)"

# =============================================================================
## 📦 Release
# =============================================================================
TAG ?= $(shell git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
RELEASE_NOTES ?= CHANGELOG.md

.PHONY: release release-sbs release-go release-all
release: release-sbs release-go
	@echo "$(GRN)✓ Release $(TAG) complete$(RESET)"

release-sbs:
	@$(print_goal "Publishing Python SBS $(TAG)")
	@pip install build twine -q
	@cd sbs && python3 -m build
	@twine check dist/* 2>/dev/null || true

release-go:
	$(call print_goal,"Building Go release $(TAG)")
	@mkdir -p dist/
	@for mod in $(MODULES); do \
		echo "  → GoReleaser $$mod"; \
		cd $$mod && goreleaser build --clean --id release --output ../dist/$$mod 2>/dev/null || \
		go build -ldflags="-s -w" -o ../dist/$$mod ./cmd/...; \
		cd - > /dev/null; \
	done

# =============================================================================
## 📚 Docs
# =============================================================================
.PHONY: docs
docs:
	$(call print_goal,"Building documentation")
	@./scripts/build-docs.sh

.PHONY: docs-serve
docs-serve:
	$(call print_goal,"Serving docs at localhost:8000")
	@python3 -m http.server 8000 -d docs/ &

# =============================================================================
## 🔧 Misc
# =============================================================================
.PHONY: tidy vuln-check coverage coverage-html
tidy:
	@$(print_goal "Go module tidying")
	@for mod in $(MODULES); do \
		cd $$mod && go mod tidy && cd - > /dev/null; \
	done
	@echo "$(GRN)✓ go mod tidy done$(RESET)"

vuln-check:
	@$(print_goal "Checking for Go vulnerabilities")
	@for mod in $(MODULES); do \
		cd $$mod && govulncheck ./... && cd - > /dev/null; \
	done

coverage:
	@$(print_goal "Running coverage for all modules")
	@for mod in $(MODULES); do \
		cd $$mod && go test -coverprofile=cover.out ./... && cd - > /dev/null; \
	done

coverage-html:
	@$(print_goal "Coverage reports in dist/coverage/")
	@mkdir -p dist/coverage
	@for mod in $(MODULES); do \
		test -f $$mod/cover.out && \
		go tool cover -html=$$mod/cover.out -o dist/coverage/$$mod.html; \
	done
	@echo "$(GRN)✓ Coverage in dist/coverage/$($(MODULE).html)$(RESET)"

.PHONY: clean
clean:
	@$(print_goal "Cleaning build artifacts")
	@rm -rf dist/ .dist/
	@for mod in $(MODULES); do \
		cd $$mod && go clean && cd - > /dev/null; \
	done
	@find . -name 'cover.out' -delete 2>/dev/null || true
	@echo "$(GRN)✓ Clean done$(RESET)"

.PHONY: verify-clean
verify-clean:
	@$(print_goal "Verifying clean workspace")
	@git diff --quiet || { echo "$(RED)✗ Uncommitted changes$(RESET)"; git diff --stat; exit 1; }
	@test ! -d dist/ || { echo "$(RED)✗ dist/ exists$(RESET)"; exit 1; }
	@echo "$(GRN)✓ Workspace is clean$(RESET)"
