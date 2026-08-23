#!/bin/bash
# make_vertical.sh —— 单图/单视频 → 竖版短视频（标题+副标题+BGM）
# 用法: bash make_vertical.sh <素材.mp4或.jpg> <标题> <副标题> <输出.mp4> [时长秒=8] [bgm.mp3]
set -e
SRC="$1"; TITLE="$2"; SUB="$3"; OUT="$4"; DUR="${5:-8}"; BGM="$6"
FONT=/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc
TMP=$(mktemp -d)
printf '%s' "$TITLE" > "$TMP/t.txt"
printf '%s' "$SUB" > "$TMP/s.txt"

EXT="${SRC##*.}"
if [[ "$EXT" == "jpg" || "$EXT" == "jpeg" || "$EXT" == "png" ]]; then
  LOOP="-loop 1 -i $SRC -t $DUR"
else
  LOOP="-i $SRC"
fi

fc="split=2[bg][fg];"
fc+="[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=30,eq=brightness=-0.28:saturation=0.85[bgb];"
fc+="[fg]scale=1080:-2[fg2];"
fc+="[bgb][fg2]overlay=(W-w)/2:(H-h)/2[base];"
fc+="[base]zoompan=z='min(zoom+0.0016,1.25)':d=$((DUR*30)):s=1080x1920:fps=30,format=yuv420p,"
fc+="drawtext=fontfile=$FONT:textfile=$TMP/t.txt:fontsize=86:fontcolor=red@0.95:x=(w-text_w)/2:y=h*0.106:borderw=6:bordercolor=white,"
fc+="drawtext=fontfile=$FONT:textfile=$TMP/s.txt:fontsize=75:fontcolor=black:x=(w-text_w)/2:y=h*0.156:box=1:boxcolor=yellow@0.98:boxborderw=16[v]"

ffmpeg -y $LOOP -filter_complex "$fc" -map "[v]" -t $DUR -c:v libx264 -preset medium -crf 19 -movflags +faststart "$TMP/plain.mp4"
if [ -n "$BGM" ]; then
  ffmpeg -y -i "$TMP/plain.mp4" -i "$BGM" -t $DUR -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest "$OUT"
else
  mv "$TMP/plain.mp4" "$OUT"
fi
rm -rf "$TMP"
echo "✅ $OUT")