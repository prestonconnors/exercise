:loop

timeout /t 1
call "%userprofile%\Code\Exercise\play_sound.bat"
del "%userprofile%\Code\Exercise\play_sound.bat"
goto loop