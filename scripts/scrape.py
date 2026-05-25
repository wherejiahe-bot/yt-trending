"""
抓取 YouTube 实时热搜榜单 (Trending)
直接从 YouTube Trending 页面提取内嵌 JSON 数据 (ytInitialData)
输出: data/youtube-trending.json
"""

import json
import os
import re
import requests
from datetime import datetime

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "youtube-trending.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_trending_page(region: str = "US") -> str:
    """获取 YouTube Trending 页面 HTML"""
    url = f"https://www.youtube.com/feed/trending"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def extract_initial_data(html: str) -> dict:
    """从 HTML 中提取 ytInitialData JSON"""
    # 尝试匹配 ytInitialData = {...};
    match = re.search(r"ytInitialData\s*=\s*({.*?});\s*\n", html, re.DOTALL)
    if not match:
        # 再试一种匹配模式
        match = re.search(r"window\.ytInitialData\s*=\s*({.*?});", html, re.DOTALL)
    if not match:
        raise Exception("无法从页面提取 ytInitialData")
    
    data = json.loads(match.group(1))
    return data


def parse_trending_videos(data: dict, max_count: int = 30) -> list[dict]:
    """从 ytInitialData 中解析 Trending 视频列表"""
    videos = []
    
    try:
        # 导航到 trending 视频列表
        contents = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]
        
        for tab in contents:
            if "tabRenderer" not in tab:
                continue
            tab_renderer = tab["tabRenderer"]
            if tab_renderer.get("title") != "Trending":
                # "Now" tab might be the first one
                if "content" not in tab_renderer:
                    continue
            
            section_list = tab_renderer.get("content", {}).get(
                "sectionListRenderer", {}
            ).get("contents", [])
            
            for section in section_list:
                if "itemSectionRenderer" not in section:
                    continue
                items = section["itemSectionRenderer"].get("contents", [])
                
                for item in items:
                    if "videoWithContextRenderer" not in item:
                        continue
                    v = item["videoWithContextRenderer"]
                    
                    video_id = v.get("videoId", "")
                    title_runs = v.get("title", {}).get("runs", [])
                    title = "".join(r.get("text", "") for r in title_runs)
                    
                    # 频道信息
                    channel_runs = (
                        v.get("ownerText", {})
                        .get("runs", [])
                    )
                    channel_name = ""
                    channel_id = ""
                    if channel_runs:
                        channel_name = channel_runs[0].get("text", "")
                        channel_id = (
                            channel_runs[0]
                            .get("navigationEndpoint", {})
                            .get("browseEndpoint", {})
                            .get("browseId", "")
                        )
                    
                    # 观看数 / 发布时间
                    short_view_count_text = (
                        v.get("shortViewCountText", {})
                        .get("simpleText", "")
                        or v.get("shortViewCountText", {})
                        .get("runs", [{}])[0]
                        .get("text", "")
                    )
                    
                    # 时长
                    length_text = (
                        v.get("lengthText", {})
                        .get("simpleText", "")
                        or v.get("lengthText", {})
                        .get("runs", [{}])[0]
                        .get("text", "")
                    )
                    
                    # 缩略图
                    thumbnail_url = ""
                    thumbnails = (
                        v.get("thumbnail", {})
                        .get("thumbnails", [])
                    )
                    if thumbnails:
                        thumbnail_url = thumbnails[-1].get("url", "")
                    
                    # 描述
                    description = ""
                    desc_runs = (
                        v.get("detailedMetadataSnippets", [{}])[0]
                        .get("snippetText", {})
                        .get("runs", [])
                    ) if v.get("detailedMetadataSnippets") else []
                    if not desc_runs:
                        desc_runs = (
                            v.get("descriptionSnippet", {})
                            .get("runs", [])
                        )
                    description = "".join(r.get("text", "") for r in desc_runs)
                    
                    videos.append({
                        "id": video_id,
                        "title": title,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "channel_name": channel_name,
                        "channel_id": channel_id,
                        "channel_url": f"https://www.youtube.com/channel/{channel_id}" if channel_id else "",
                        "thumbnail_url": thumbnail_url,
                        "views_text": short_view_count_text,
                        "duration_text": length_text,
                        "description": description,
                    })
                    
                    if len(videos) >= max_count:
                        break
                if len(videos) >= max_count:
                    break
            if len(videos) >= max_count:
                break
    except (KeyError, IndexError, TypeError) as e:
        print(f"解析时出错 (部分数据可能已提取): {e}")
    
    return videos


def get_category_tags(title: str, description: str) -> list[str]:
    """根据标题简单分类"""
    text = (title + " " + description).lower()
    categories = []
    
    if any(w in text for w in ["news", "breaking", "报道", "新闻", "update"]):
        categories.append("新闻")
    if any(w in text for w in ["music", "song", "mv", "audio", "专辑", "歌手", "official"]):
        categories.append("音乐")
    if any(w in text for w in ["game", "gaming", "gameplay", "游戏", "直播", "minecraft", "fortnite"]):
        categories.append("游戏")
    if any(w in text for w in ["sport", "football", "basketball", "nba", "soccer", "比赛", "nfl"]):
        categories.append("体育")
    if any(w in text for w in ["movie", "trailer", "film", "电影", "预告", "teaser"]):
        categories.append("影视")
    if any(w in text for w in ["tech", "ai", "iphone", "android", "科技", "手机", "computer"]):
        categories.append("科技")
    if any(w in text for w in ["comedy", "funny", "搞笑", "prank"]):
        categories.append("搞笑")
    if any(w in text for w in ["education", "tutorial", "学习", "教程", "教学", "how to"]):
        categories.append("教育")
    
    if not categories:
        categories.append("综合")
    
    return categories


def main():
    print("正在抓取 YouTube 热搜榜单...")
    
    html = fetch_trending_page()
    print("页面获取成功，正在解析...")
    
    initial_data = extract_initial_data(html)
    print("ytInitialData 提取成功，正在提取视频列表...")
    
    videos = parse_trending_videos(initial_data, max_count=30)
    print(f"解析完成，共 {len(videos)} 个视频")
    
    # 构建输出
    trending_list = []
    for idx, v in enumerate(videos):
        trending_list.append({
            "rank": idx + 1,
            "id": v["id"],
            "title": v["title"],
            "url": v["url"],
            "channel_name": v["channel_name"],
            "channel_url": v["channel_url"],
            "thumbnail_url": v["thumbnail_url"],
            "views_text": v["views_text"],
            "duration_text": v["duration_text"],
            "description": v["description"][:200],
            "categories": get_category_tags(v["title"], v.get("description", "")),
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
