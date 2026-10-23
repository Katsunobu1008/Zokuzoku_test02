.PHONY: run test check
run:
	python -m app

test:
	python -m unittest discover -s tests -v

check: test
	python -m compileall -q app tests
