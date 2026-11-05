PYTHON ?= python3
export PYTHONPATH := $(CURDIR)/src:$(PYTHONPATH)

DEMO_DIR := out

.PHONY: all test lint check demo clean

all: check

test:
	$(PYTHON) -m unittest discover -s tests -t . -p "test_*.py" -v

lint:
	$(PYTHON) tools/check_style.py

check: lint test

demo:
	mkdir -p $(DEMO_DIR)
	for package in A B C; do \
		./run.sh --package $$package --repository examples/visual.txt \
			--mode test --output $(DEMO_DIR)/visual-$$package.svg \
			--ascii tree; \
	done
	./run.sh --package A --repository examples/simple.txt --mode test \
		--output $(DEMO_DIR)/simple.svg --ascii tree
	./run.sh --package A --repository examples/cycles.txt --mode test \
		--output $(DEMO_DIR)/cycles.svg --load-order
	./run.sh --package A --repository examples/complex.txt --mode test \
		--output $(DEMO_DIR)/complex.svg --ascii tree
	./run.sh --package serde_json --repository https://crates.io \
		--mode cargo --output $(DEMO_DIR)/serde_json.svg --ascii tree

clean:
	rm -rf $(DEMO_DIR)
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
