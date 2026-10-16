PY ?= python

.PHONY: install all report export test clean

install:
	$(PY) -m pip install -e ".[dev]"

all:            ## generate data, build model, analyse, report, export for Power BI, refresh README images
	$(PY) -m asi.cli all --docs
	$(PY) scripts/publish_powerbi.py

report:         ## regenerate the Excel pack and one-pager only
	$(PY) -m asi.cli report

export:
	$(PY) -m asi.cli export

test:
	$(PY) -m pytest -q

clean:
	rm -rf output
