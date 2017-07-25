#!/usr/bin/env bash

set -x
set -e

echo "Building docs with Sphinx"
make -C docs html

echo "Checking grammar and style"
write-good `find ./docs -not \( -path ./docs/drafts -prune \) -name '*.rst'` --passive --so --no-illusion --thereIs --cliches

set +e
echo "Checking links"
make -C docs linkcheck

echo "The following links are broken:"
grep "broken" docs/_build/linkcheck/output.txt
