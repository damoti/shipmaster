.PHONY: test clean release

clean:
	rm -rf build dist shipmaster.egg-info

release:
	python setup.py sdist bdist_wheel upload
