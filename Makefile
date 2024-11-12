install:
	@echo "--- 🚀 Installing project dependencies ---"-e ./agent_ood_gym/
	pip install -e ./agent_ood_gym/core -e ./agent_ood_gym/miniwob -e ./agent_ood_gym/webarena -e ./agent_ood_gym/visualwebarena/ -e ./agent_ood_gym/experiments -e ./agent_ood_gym/assistantbench 
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
