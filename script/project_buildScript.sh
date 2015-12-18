#!/bin/sh

#  project_buildScript.sh
#  
#
#  Created by Jodie Putrino on 11/23/15.
#

# see the script run in travis; exit if anything fails
set -ev

# clone the docs source repo into the travis project directory

git clone --verbose --branch=develop https://f5-travisci:$TRAVIS_PATOKEN@github.com/F5Networks/f5-openstack-docs.git

cd doc
cp ../f5-openstack-docs/_includes/footer.html ./_includes
cp ../f5-openstack-docs/_includes/head_for_docs.html ./_includes
cp ../f5-openstack-docs/_includes/head.html ./_includes
cp ../f5-openstack-docs/_includes/header.html ./_includes
cp ../f5-openstack-docs/_includes/tocify.html ./_includes

cp -R ../f5-openstack-docs/_layouts/ ./_layouts/
cp -R ../f5-openstack-docs/css/ ./css/
cp -R ../f5-openstack-docs/js/ ./js/
cp ../f5-openstack-docs/_config.yml ./
cp ../f5-openstack-docs/Gemfile ./
cp ../README.md ./
mv README.md index.md

# build the site with Jekyll

echo "Building site with Jekyll"
bundle exec jekyll build -d ./site_build --config _config.yml,_agentconfig.yml

# check the html and validate links with html-proofer
echo "proofing site with htmlproofer"
bundle exec htmlproof ./site_build

echo "copying site_build to $HOME"
cp -R site_build $HOME/site_build
cd $HOME/site_build
echo "listing contents of $HOME/site_build"
ls -la