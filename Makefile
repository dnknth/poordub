clean:
	rm -rf build dist *.egg-info  __pycache__

tidy: clean
	rm -rf .venv

dist: .venv
	uv build
	
pypi: clean dist
	uv publish

.venv:
	uv sync
