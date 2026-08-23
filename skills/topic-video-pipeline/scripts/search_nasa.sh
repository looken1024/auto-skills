#!/bin/bash
# search_nasa.sh —— NASA 素材搜索 + 下载
# 用法:
#   bash search_nasa.sh search "earth from moon" video
#   bash search_nasa.sh asset NASA_ID
#   bash search_nasa.sh download NASA_ID out.mp4 medium
set -e
Q="$2"
case "$1" in
  search)
    curl -s "https://images-api.nasa.gov/search?q=$(echo "$Q" | sed 's/ /%20/g')&media_type=$3&page_size=8" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for it in d.get('collection',{}).get('items',[]):
    data=it.get('data',[{}])[0]
    print('-', data.get('nasa_id',''), '|', data.get('title','')[:60]) "
    ;;
  asset)
    curl -s "https://images-api.nasa.gov/asset/$Q" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for it in d.get('collection',{}).get('items',[]):
    h=it.get('href','')
    if '~orig' in h or '~large' in h or '~medium' in h:
        print(h)" "
    ;;
  download)
    ID="$Q"; OUT="$3"; SIZE="${4:-medium}"
    URL=$(curl -s "https://images-api.nasa.gov/asset/$ID" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for it in d.get('collection',{}).get('items',[]):
    h=it.get('href','')
    if '~$SIZE' in h and '~${SIZE}.mp4' not in h and '.mp4' not in h:
        print(h); break
    if '~$SIZE.mp4' in h or '~$SIZE.jpg' in h:
        print(h); break" | head -1)
    curl -sL -o "$OUT" "$URL"
    echo "✅ $OUT"
    ;;
esac