PY?=python3
VENVPY?=/Users/alexanderlange/.venvs/alphamind/bin/python
UVICORN=/Users/alexanderlange/.venvs/alphamind/bin/uvicorn
ROOT=/Users/alexanderlange/alphamind

.PHONY: miner validator api deps api3 aggregate mint redeem open test lint typecheck

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


test:
	PYTHONPATH=$(ROOT) pytest -q

lint:
	$(VENVPY) -m pip install ruff==0.5.6 || true; $(VENVPY) -m ruff check $(ROOT)/subnet || true

typecheck:
	true # placeholder for mypy if types are added

