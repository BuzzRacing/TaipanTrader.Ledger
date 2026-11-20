@echo off
rem Queues Mrs. Agatha Crane (Hong Kong's warden) walking toward you spinning her keys: 2 NSFW + 2 clean
rem 10-second looping clips from her own warden photos, same movement and seeds, for Compare in the
rem Media Library. Runs on the farm (Wan 2.2 in ComfyUI on BIGBOX). Deploy the video update to the Pi first.
rem Extra options pass through, e.g.  Queue_Warden_Keys_Video_Pair.bat --dry   or   --motion keys_slow
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul || set "PY=py"
%PY% tools\queue_video_pairs.py --who warden_hongkong --motion keys --count 2 %*
echo.
pause
