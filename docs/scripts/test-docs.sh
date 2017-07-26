#!/usr/bin/env bash

html="make -C docs html"
linkcheck="sphinx-build -b linkcheck docs docs/_build/linkcheck"
grammar="write-good `find ./docs -not \( -path ./docs/drafts -prune \) -name '*.rst'` --passive --so --no-illusion --thereIs --cliches"

if [ $TRAVIS="true" ];
   then OUTPUT_DIR=${TRAVIS_BUILD_DIR}/_build/linkcheck
fi

warn() {
  printf "%s\n" "$*" >&2

  exit 0
}

die()  {
  printf "%s\n" "$*" >&2

  exit 1
}

goodjob() {
  printf "%s\n" "$*" >&2

}

make -C docs clean

echo $TRAVIS

set -e

echo "Building docs with Sphinx"
set -x
$html

echo "Checking grammar and style"
set -x
$grammar
set +x
[[ $grammar = "" ]] || goodjob "CONGRATULATIONS! You are a grammar wizard."

echo "Checking links"
if [[ $linkcheck != "" ]]; then
   sphinx-build -b linkcheck docs docs/_build/linkcheck | grep 'broken'
   warn "WARNING: Link check failed. See output above for errors."
   else echo "Linkcheck succeeded"
fi
