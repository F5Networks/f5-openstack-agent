#!/usr/bin/env sh

#  docScript.sh
#  
#
#  Created by Jodie Putrino on 10/27/15.
#

#install gems in Gemfile
#bundle install

# remove the temp directory if it currently exists
#rm -rf ./temp_site

# create new jekyll site framework in $HOME
echo "creating new jekyll site in temp_site directory"
bundle exec jekyll new temp_site

# copy content of doc directory into new temp folder
echo "copying doc directory into ~/temp_site"
cp -R ./$TRAVISREPOSLUG/doc ./temp_site/doc

# build site
echo "building site with jekyll"
bundle exec jekyll build -s ./temp_site/ -d ./site_build

#echo "proofing site with htmlproofer"
#bundle exec htmlproof ./site_build

echo "copying docs to $HOME"
cp -R ./site_build/doc $HOME/site_build

echo "listing contents of $HOME/site_build"
ls -a $HOME/site_build
