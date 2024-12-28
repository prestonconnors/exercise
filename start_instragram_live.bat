@echo off
SET /p "instagram_url=Instagram Stream URL: " 
SET /p "instagram_key=Instagram Key: "

pause

::SET youtube_url="https://youtube.com/live/Ee5ulUhK8Kw?feature=share"

::python -m pip install -U pip yt-dlp

::yt-dlp %youtube_url% --wait-for-video 10 -f "best[height=720]" -o - | ffmpeg -re -f mpegts -rtbufsize 10M -i pipe: -vf "transpose=1" -f flv -acodec aac -vcodec libx264 %instagram_url%

SET video_dir=C:\Users\Preston Connors\Videos\Pre-Recorded Exercise Stream
del "%video_dir%\*.ts"

SET input_file=
:loop
FOR /F "tokens=* USEBACKQ" %%F IN (`dir /b /a-d /s "%video_dir%\*.ts"`) DO (
SET input_file=%%F
)
timeout 5
IF NOT EXIST "%input_file%" (GOTO loop) ELSE (	ffmpeg -re -f mpegts -rtbufsize 10M -i "%input_file%" -vf "transpose=1" -f flv -acodec aac -vcodec libx264 "%instagram_url%%instagram_key%")