install:
	@echo "--- 🚀 Installing project dependencies ---"-e ./agent_ood_gym/
	pip install -e ./browsergym/core -e ./browsergym/miniwob -e ./browsergym/webarena -e ./browsergym/visualwebarena/ -e ./browsergym/experiments -e ./browsergym/assistantbench -e ./browsergym/oodarena -e ./browsergym/
	pip install -e ./embodiedgym/core -e ./embodiedgym/experiments -e ./embodiedgym/alfworld -e ./embodiedgym
	playwright install chromium

install-demo:
	@echo "--- 🚀 Installing demo dependencies ---"
	pip install -r demo_agent/requirements.txt
	playwright install chromium

demo:
	@echo "--- 🚀 Running demo agent ---"
	(set -x && cd demo_agent && python run_demo.py)

test-core:
	@echo "--- 🧪 Running tests ---"
	pytest -n auto ./tests/core
