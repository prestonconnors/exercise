#!/usr/bin/env bash

set -e

site="/etc/nginx/sites-available/prestonconnors.com"
current_url="$(grep -oP '(https://youtu.be/\S+|https://youtube.com/\S+)' $site)"
new_url="$(grep -v $current_url /mnt/Stream/Code/Exercise/youtube_urls.txt | shuf -n 1)"
sudo /bin/sed -i "s#rewrite ^/(.*)\$ .* redirect;#rewrite ^/(.*)\$ $new_url redirect;##" $site
sudo service nginx reload
