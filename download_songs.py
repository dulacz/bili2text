"""
从 .txt 文件中提取所有 Bilibili BV 号 / YouTube 链接并依次下载音频（mp3），
下载之间加入随机睡眠以避免风控。

不进行切片，不进行语音转文字。

用法:
    python download_songs.py                          # 默认读取 outputs/songs.txt
    python download_songs.py path/to/list.txt
    python download_songs.py path/to/list.txt --out audio/songs --min-sleep 3 --max-sleep 8
"""

import argparse
import glob
import os
import random
import re
import shutil
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(BASE_DIR, "inputs", "songs.txt")
DEFAULT_OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "songs")
# 故意不使用 cookies.txt / 账号登录，匿名下载以降低被封风险（仅能拿到普通画质音轨，足够）

# 同时识别 data-key="BV..." 和 行内裸的 BV 号 / URL 中的 BV 号
BV_PATTERN = re.compile(r"BV[A-Za-z0-9]{10}")
YT_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{11}")
# 抓取 BV 对应的 title="..."（用于命名，可选）
ENTRY_PATTERN = re.compile(
    r'data-key="(BV[A-Za-z0-9]{10})"[\s\S]*?title="([^"]*)"',
    re.IGNORECASE,
)

# Windows 文件名非法字符
_INVALID_FNAME_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')

# 常见推广短语，命名时剔除
_PROMO_PATTERNS = [
    re.compile(r"在?百万豪装录音棚大声听"),
    re.compile(r"【Hi-?res】", re.IGNORECASE),
    re.compile(r"\[Hi-?res\]", re.IGNORECASE),
    re.compile(r"（Hi-?res）", re.IGNORECASE),
]


def clean_title(title):
    """去掉推广短语并修剪空白。"""
    if not title:
        return ""
    for pat in _PROMO_PATTERNS:
        title = pat.sub(" ", title)
    # 折叠多余空白
    title = re.sub(r"\s+", " ", title).strip()
    return title


def sanitize_filename(name, max_len=120):
    name = _INVALID_FNAME_CHARS.sub(" ", name)
    # 折叠多余空白；保留中文空格分词
    name = re.sub(r"\s+", " ", name).strip().strip(".")
    if len(name) > max_len:
        name = name[:max_len].rstrip()
    return name or "untitled"


def extract_youtube_id(url_or_id):
    """从 YouTube URL 中提取 11 位视频 ID；若传入的是 ID 则原样返回。"""
    url_or_id = url_or_id.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_id):
        return url_or_id
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})", url_or_id)
    if m:
        return m.group(1)
    return None


def extract_entries(text):
    """返回 [(platform, vid, title_or_None, source_url_or_None), ...]，按首次出现去重。"""
    titles = {}
    for bv, title in ENTRY_PATTERN.findall(text):
        # HTML 实体反转义最常见几个
        title = title.replace("&amp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
        titles.setdefault(bv, clean_title(title))

    seen_keys = set()
    ordered = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # 1) Bilibili BV
        bv_match = BV_PATTERN.search(line)
        if bv_match:
            bv = bv_match.group(0)
            key = f"bilibili:{bv}"
            if key not in seen_keys:
                seen_keys.add(key)
                ordered.append(("bilibili", bv, titles.get(bv), None))
            continue

        # 2) YouTube URL / ID
        if re.search(r"(?:youtube\.com|youtu\.be)", line, re.IGNORECASE) or YT_ID_PATTERN.fullmatch(line):
            yt_id = extract_youtube_id(line)
            if yt_id:
                key = f"youtube:{yt_id}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    source_url = line if line.startswith("http://") or line.startswith("https://") else None
                    ordered.append(("youtube", yt_id, None, source_url))

    return ordered


def collect_existing_ids(output_dir):
    """扫描输出目录，返回已下载标识集合：bilibili:<BV> / youtube:<id>。"""
    existing = set()
    if not os.path.isdir(output_dir):
        return existing
    for fn in os.listdir(output_dir):
        if not fn.lower().endswith(".mp3"):
            continue
        for bv in BV_PATTERN.findall(fn):
            existing.add(f"bilibili:{bv}")
        for m in re.findall(r"\[([A-Za-z0-9_-]{11})\]", fn):
            existing.add(f"youtube:{m}")
        for m in re.findall(r"YT_([A-Za-z0-9_-]{11})", fn):
            existing.add(f"youtube:{m}")
    return existing


def build_output_path(platform, vid, title, output_dir):
    """生成最终路径。B站附加 [BV...]；YouTube 使用 YT_<id>。"""
    if platform == "bilibili":
        if title:
            base = f"{sanitize_filename(title)} [{vid}]"
        else:
            base = vid
    else:
        if title:
            base = f"{sanitize_filename(title)} [{vid}]"
        else:
            base = f"[{vid}]"
    return os.path.join(output_dir, f"{base}.mp3")


def get_ffmpeg_location():
    """返回可用于 yt-dlp 的 ffmpeg 可执行文件路径。"""
    ffmpeg_exe = shutil.which("ffmpeg")
    if ffmpeg_exe:
        return ffmpeg_exe

    # 尝试使用 imageio-ffmpeg 提供的内置二进制
    try:
        import imageio_ffmpeg  # type: ignore

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg_exe and os.path.exists(ffmpeg_exe):
            return ffmpeg_exe
    except Exception:
        pass

    return None


def download_one(platform, vid, title, output_dir, source_url=None):
    """下载单个视频音频为 mp3。"""
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "-x",
        "--audio-format",
        "mp3",
        "--no-playlist",
    ]

    if platform == "bilibili":
        video_url = f"https://www.bilibili.com/video/{vid}"
        output_path = build_output_path(platform, vid, title, output_dir)
        cmd.extend(["-o", output_path])
    else:
        video_url = source_url or f"https://www.youtube.com/watch?v={vid}"
        # 让 yt-dlp 直接用元数据命名：<YouTube标题> [<id>].mp3
        output_template = os.path.join(output_dir, "%(title)s [%(id)s].%(ext)s")
        cmd.extend(["-o", output_template])

    ffmpeg_loc = get_ffmpeg_location()
    if ffmpeg_loc:
        cmd.extend(["--ffmpeg-location", ffmpeg_loc])
    cmd.append(video_url)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )

    # YouTube 常见 403：切换 player client 再重试一次
    if platform == "youtube" and result.returncode != 0:
        err_text = (result.stderr or "") + "\n" + (result.stdout or "")
        if "403" in err_text or "Forbidden" in err_text:
            retry_cmd = cmd[:-1] + [
                "--extractor-args",
                "youtube:player_client=android,web",
                cmd[-1],
            ]
            result = subprocess.run(
                retry_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )

    if result.returncode != 0:
        return False, (result.stderr or "").strip().splitlines()[-1:] or ["未知错误"]

    if platform == "bilibili":
        return os.path.exists(output_path), [output_path]

    # YouTube：按 [<id>].mp3 在输出目录中定位最终文件（避免解码 CJK 路径的编码问题）
    matches = glob.glob(os.path.join(output_dir, f"*[[]{vid}[]].mp3"))
    if matches:
        return True, [matches[0]]
    return False, ["未找到下载后的 mp3 文件"]


def main():
    parser = argparse.ArgumentParser(description="批量下载 .txt 中的 Bilibili / YouTube 音频（带睡眠间隔）")
    parser.add_argument("input", nargs="?", default=DEFAULT_INPUT, help=f"输入 .txt 文件（默认: {DEFAULT_INPUT}）")
    parser.add_argument("--out", default=DEFAULT_OUTPUT_DIR, help=f"输出目录（默认: {DEFAULT_OUTPUT_DIR}）")
    parser.add_argument("--min-sleep", type=float, default=20.0, help="每次下载之间最小睡眠秒数（默认 20）")
    parser.add_argument("--max-sleep", type=float, default=60.0, help="每次下载之间最大睡眠秒数（默认 60）")
    parser.add_argument("--limit", type=int, default=0, help="只下载前 N 个（0 表示全部）")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"错误：输入文件不存在 {args.input}")
        sys.exit(1)
    if args.max_sleep < args.min_sleep:
        args.max_sleep = args.min_sleep

    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()

    entries = extract_entries(text)
    if args.limit > 0:
        entries = entries[: args.limit]
    if not entries:
        print("错误：未在文件中找到任何可识别的 Bilibili BV 号或 YouTube 链接")
        sys.exit(1)

    print(f"找到 {len(entries)} 个条目，输出目录: {args.out}")
    print(f"下载间隔随机睡眠: {args.min_sleep}~{args.max_sleep} 秒")
    print("-" * 60)

    # 以平台+ID为唯一去重键：一次性扫描输出目录，后续动态补充
    existing_ids = collect_existing_ids(args.out)
    if existing_ids:
        print(f"输出目录已有 {len(existing_ids)} 个已下载标识的 mp3，将跳过")

    ok_count = 0
    skip_count = 0
    fail = []
    for i, (platform, vid, title, source_url) in enumerate(entries, 1):
        key = f"{platform}:{vid}"
        label = f"{platform}:{vid}" + (f"  {title}" if title else "")
        print(f"\n[{i}/{len(entries)}] {label}")

        if key in existing_ids:
            print("  已存在，跳过")
            skip_count += 1
            continue

        ok, info = download_one(platform, vid, title, args.out, source_url=source_url)
        if ok:
            ok_count += 1
            existing_ids.add(key)
            print(f"  OK -> {info[0]}")
        else:
            fail.append((f"{platform}:{vid}", info))
            print(f"  FAIL: {info}")

        # 最后一个不必再睡
        if i < len(entries):
            delay = random.uniform(args.min_sleep, args.max_sleep)
            print(f"  睡眠 {delay:.1f}s ...")
            time.sleep(delay)

    print("\n" + "=" * 60)
    print(f"完成：成功 {ok_count}，跳过 {skip_count}，失败 {len(fail)}，共 {len(entries)}")
    if fail:
        print("失败列表：")
        for key, info in fail:
            print(f"  - {key}: {info}")


if __name__ == "__main__":
    main()
