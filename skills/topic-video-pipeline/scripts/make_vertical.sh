#!/bin/bash
# make_vertical.sh —— 单图/单视频 → 竖版短视频（标题+副标题+BGM）
# 用法: bash make_vertical.sh <素材.mp4或.jpg> <标题> <副标题> <输出.mp4> [时长秒=8] [bgm.mp3]
set -e
SRC="$1"; TITLE="$2"; SUB="$3"; OUT="$4"; DUR="${5:-8}"; BGM="$6"
# 两行副标题（带数据）时：SUB_FONTSIZE=60 SUB_LINE_SPACING=20
# 主副标题间距：SUB_Y 为副标题顶部 y 比例（默认 0.156，增大则下移拉开间距）
SUB_FS="${SUB_FONTSIZE:-75}"; SUB_LS="${SUB_LINE_SPACING:-0}"; SUB_Y="${SUB_Y:-0.215}"
TITLE_FS="${TITLE_FS:-86}"; TITLE_Y="${TITLE_Y:-0.106}"
FONT="${FONT:-/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc}"
TMP=$(mktemp -d)
printf '%s' "$TITLE" > "$TMP/t.txt"
printf '%b' "$SUB" > "$TMP/s.txt"

EXT="${SRC##*.}"
if [[ "$EXT" == "jpg" || "$EXT" == "jpeg" || "$EXT" == "png" ]]; then
  LOOP="-loop 1 -i $SRC -t $DUR"
  ZOOM_D=$((DUR*30))   # 图片: 每帧重复成 DUR*30 帧
else
  LOOP="-i $SRC"
  ZOOM_D=1             # 视频: 每帧只处理一次, 保留时间轴(否则会把首帧重复整段变静态!)
fi

fc="split=2[bg][fg];"
fc+="[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=30,eq=brightness=-0.28:saturation=0.85[bgb];"
fc+="[fg]scale=1080:-2[fg2];"
fc+="[bgb][fg2]overlay=(W-w)/2:(H-h)/2[base];"
fc+="[base]zoompan=z='min(zoom+0.0016,1.25)':d=$ZOOM_D:s=1080x1920:fps=30,format=yuv420p,"
fc+="drawtext=fontfile=$FONT:textfile=$TMP/t.txt:fontsize=$TITLE_FS:fontcolor=red@0.95:x=(w-text_w)/2:y=h*$TITLE_Y:borderw=6:bordercolor=white,"
# 副标题黑字 + 黄底框
fc+="drawtext=fontfile=$FONT:textfile=$TMP/s.txt:fontsize=$SUB_FS:fontcolor=black:line_spacing=$SUB_LS:x=(w-text_w)/2:y=h*$SUB_Y:box=1:boxcolor=yellow@0.98:boxborderw=16[v]"

ffmpeg -y $LOOP -filter_complex "$fc" -map "[v]" -t $DUR -c:v libx264 -preset medium -crf 19 -movflags +faststart "$TMP/plain.mp4"
if [ -n "$BGM" ]; then
  ffmpeg -y -i "$TMP/plain.mp4" -i "$BGM" -t $DUR -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest "$OUT"
else
  mv "$TMP/plain.mp4" "$OUT"
fi
rm -rf "$TMP"
echo "✅ $OUT"