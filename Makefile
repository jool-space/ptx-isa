.PHONY: build validate publish backfill clean

build:
	./scrape.py --out dist

validate: build
	./validate.py dist

publish:
	scripts/publish.sh dist

backfill:
	scripts/backfill.sh

clean:
	rm -rf dist previous
