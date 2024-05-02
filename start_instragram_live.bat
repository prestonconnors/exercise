set youtube_url="https://youtube.com/live/shwdztRTWRQ?feature=share"
set instagram_url="rtmps://edgetee-upload-lga3-1.xx.fbcdn.net:443/rtmp/17896903961919158?s_bl=1&s_fbp=bos5-1&s_prp=lga3-1&s_spl=1&s_sw=0&s_tids=1&s_vt=ig&a=AbzUWP5V_1Q0RvaM"

pip3 install -U yt-dlp

yt-dlp %youtube_url% --wait-for-video 10 -f "best[height=720]" -o - | ffmpeg -re -f mpegts -rtbufsize 10M -i pipe: -vf "transpose=1" -f flv -acodec aac -vcodec libx264 %instagram_url%