test:
	python3 tests.py

build: $(LOCALE:.po=.mo) $(POT)
	python3 setup.py build

clean:
	rm -rf build *.egg-info
