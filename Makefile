PY?=python3
# Prefer project-local venv if present
VENVPY?=$(ROOT)/.venv/bin/python
UVICORN?=$(ROOT)/.venv/bin/uvicorn
ROOT=/Users/alexanderlange/alphamind

.PHONY: miner validator api deps api3 aggregate mint redeem open test lint typecheck e2e-local

deps:
	$(VENVPY) -m pip install -r requirements.txt

miner:
	PYTHONPATH=$(ROOT) $(PY) -m subnet.miner.loop

validator:
	PYTHONPATH=$(ROOT) $(PY) -m subnet.validator.service

api:
	PYTHONPATH=$(ROOT) $(UVICORN) subnet.validator.api:app --host 127.0.0.1 --port 8002

schedule:
	PYTHONPATH=$(ROOT) $(PY) -m subnet.sim.scheduler

# Run API on 8003 (recommended during dev)
api3:
	PYTHONPATH=$(ROOT) $(UVICORN) subnet.validator.api:app --host 127.0.0.1 --port 8003

# Call aggregate endpoint to produce weights.json and (re)initialize vault
aggregate:
	curl -s -X POST http://127.0.0.1:8003/aggregate -H 'content-type: application/json' -d '{"in_dir":"$(ROOT)/subnet/out","out_file":"$(ROOT)/subnet/out/weights.json","top_n":20}' | cat

# Mint via TAO (AMOUNT variable required, e.g., make mint AMOUNT=10)
mint:
	@if [ -z "$(AMOUNT)" ]; then echo "Usage: make mint AMOUNT=10"; exit 1; fi; \
	curl -s -X POST http://127.0.0.1:8003/mint-tao -H 'content-type: application/json' -d '{"in_dir":"$(ROOT)/subnet/out","amount_tao":'"$(AMOUNT)"'}' | cat

# Redeem TAO20 (AMOUNT variable required, e.g., make redeem AMOUNT=5)
redeem:
	@if [ -z "$(AMOUNT)" ]; then echo "Usage: make redeem AMOUNT=5"; exit 1; fi; \
	curl -s -X POST http://127.0.0.1:8003/redeem -H 'content-type: application/json' -d '{"in_dir":"$(ROOT)/subnet/out","amount_tao20":'"$(AMOUNT)"'}' | cat

# Open the dashboard in browser
open:
	open http://127.0.0.1:8003/dashboard || echo "Dashboard: http://127.0.0.1:8003/dashboard"

# QoL one-shot emits
emit-emissions:
	PYTHONPATH=$(ROOT) $(PY) -m subnet.miner.loop --emit-emissions-once

emit-prices:
	PYTHONPATH=$(ROOT) $(PY) -m subnet.miner.loop --emit-prices-once


test:
	PYTHONPATH=$(ROOT) pytest -q

lint:
	$(VENVPY) -m pip install ruff==0.5.6 || true; $(VENVPY) -m ruff check $(ROOT)/subnet || true

typecheck:
	true # placeholder for mypy if types are added

# End-to-end local run on anvil: deploy contracts, run API, emit data, aggregate, publish
e2e-local:
	@echo "Starting anvil..."; \
	anvil --port 8545 --chain-id 31337 --silent & echo $$! > /tmp/anvil.pid; sleep 1; \
	echo "Deploying contracts..."; \
	cd $(ROOT)/contracts && \
	REG_ADDR=$$(forge create src/WeightsetRegistry.sol:WeightsetRegistry --rpc-url http://127.0.0.1:8545 --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 --json | jq -r .deployedTo); \
	VS_ADDR=$$(forge create src/ValidatorSet.sol:ValidatorSet --constructor-args 0x0000000000000000000000000000000000000001 --rpc-url http://127.0.0.1:8545 --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 --json | jq -r .deployedTo); \
	cast send $$VS_ADDR "setRegistry(address)" $$REG_ADDR --rpc-url http://127.0.0.1:8545 --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 >/dev/null; \
	cd $(ROOT); \
	echo "Starting API..."; \
	AM_OUT_DIR=$(ROOT)/subnet/out AM_API_TOKEN=dev AM_CHAIN=1 AM_RPC_URL=http://127.0.0.1:8545 AM_CHAIN_PRIVKEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 AM_REGISTRY_ADDR=$$REG_ADDR AM_VALIDATORSET_ADDR=$$VS_ADDR \
	PYTHONPATH=$(ROOT) $(UVICORN) subnet.validator.api:app --host 127.0.0.1 --port 8003 & echo $$! > /tmp/api.pid; sleep 2; \
	PYTHONPATH=$(ROOT) $(PY) -m subnet.miner.loop --emit-emissions-once; \
	PYTHONPATH=$(ROOT) $(PY) -m subnet.miner.loop --emit-prices-once; \
	make -s aggregate; \
	echo "Publishing weightset..."; \
	curl -s http://127.0.0.1:8003/weightset-publish | jq .; \
	echo "Dashboard: http://127.0.0.1:8003/dashboard"; \
	trap 'kill $$(cat /tmp/api.pid) $$(cat /tmp/anvil.pid) 2>/dev/null || true' EXIT

