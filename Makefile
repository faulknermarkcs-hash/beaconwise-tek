.PHONY: demo verify

verify:
	pytest -q tests

demo:
	python examples/run_demo.py
