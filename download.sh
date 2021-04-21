#!/bin/sh
rm -rf ./data
wget -r -np -nH --cut-dirs=1 -P ./data -R index.html,robots.txt -A "*wpt.aip" $OPENAIP_URL
find ./data -name "*wpt.aip" -type 'f' -size -1k -delete
rm ./data/*.tmp

