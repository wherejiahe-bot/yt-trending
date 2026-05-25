"""
抓取 YouTube 实时热搜榜单 (Trending)
使用 yt-dlp 提取 YouTube Trending 视频数据
输出: data/youtube-trending.json
"""

import json
import os
import subprocess
import sys
from datetime import datetime

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "youtube-trending.json")


def fetch_trending(max_count: int = 30) -> list[dict]:
    """使用 yt-dlp 提取 YouTube Trending 视频列表"""
    url = "https://www.youtube.com/feed/trending"
    
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--flat-playlist",
        "--dump-json",
        "--playlist-end", str(max_count),
        "--no-warnings",
        url,
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        print("yt-dlp 超时")
        return []
    
    if result.returncode != 0:
        print(f"yt-dlp 错误: {result.stderr[:500]}")
        # 备选：用搜索代替 trending
        return fetch_via_search(max_count)
    
    videos = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            video = {
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "url": f"https://www.youtube.com/watch?v={item.get('id', '')}",
                "channel_name": item.get("channel", item.get("uploader", "")),
                "channel_id": item.get("channel_id", item.get("uploader_id", "")),
                "views": item.get("view_count", 0),
                "duration": item.get("duration", 0),
                "description": (item.get("description", "") or "")[:200],
                "categories": [],
            }
            videos.append(video)
        except json.JSONDecodeError:
            continue
    
    return videos


def fetch_via_search(max_count: int = 30) -> list[dict]:
    """备选方案：通过搜索获取热门视频"""
    # 用多个热门搜索词聚合
    queries = ["trending", "viral", "popular now"]
    all_videos = []
    seen_ids = set()
    
    for query in queries:
        if len(all_videos) >= max_count:
            break
        
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--flat-playlist",
            "--dump-json",
            "--playlist-end", str(max_count // 2),
            "--no-warnings",
            f"ytsearch{max_count}:{query}",
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                continue
            
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                    vid = item.get("id", "")
                    if vid and vid not in seen_ids:
                        seen_ids.add(vid)
                        video = {
                            "id": vid,
                            "title": item.get("title", ""),
                            "url": f"https://www.youtube.com/watch?v={vid}",
                            "channel_name": item.get("channel", item.get("uploader", "")),
                            "channel_id": item.get("channel_id", item.get("uploader_id", "")),
                            "views": item.get("view_count", 0),
                            "duration": item.get("duration", 0),
                            "description": (item.get("description", "") or "")[:200],
                            "categories": [],
                        }
                        all_videos.append(video)
                        if len(all_videos) >= max_count:
                            break
                except json.JSONDecodeError:
                    continue
        except subprocess.TimeoutExpired:
            continue
    
    return all_videos


def main():
    print("正在抓取 YouTube 热搜榜单...")
    
    videos = fetch_trending(max_count=30)
    
    if not videos:
        print("主方案失败，尝试备选方案...")
        videos = fetch_via_search(max_count=30)
    
    print(f"抓取完成，共 {len(videos)} 个视频")
    
    # 构建输出
    trending_list = []
    for idx, v in enumerate(videos):
        trending_list.append({
            "rank": idx + 1,
            "id": v["id"],
            "title": v["title"],
            "url": v["url"],
            "channel_name": v["channel_name"],
            "channel_url": f"https://www.youtube.com/channel/{v['channel_id']}" if v.get("channel_id") else "",
            "views": v.get("views", 0),
            "duration_seconds": v.get("duration", 0),
            "description": v.get("description", ""),
        })
    
    output = {
        "source": "YouTube Trending",
        "url": "https://www.youtube.com/feed/trending",
        "description": "YouTube实时热搜榜单",
        "region": "US",
        "scraped_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_count": len(trending_list),
        "data": trending_list,
    }
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"数据已保存到 {OUTPUT_FILE}")
    print(f"榜单前5:")
    for v in trending_list[:5]:
        print(f"  #{v['rank']} {v['title'][:60]} | {v['channel_name']}")


if __name__ == "__main__":
    main()
