"""
从 .txt 文件中提取所有 Bilibili BV 号并依次下载音频（mp3），
下载之间加入随机睡眠以避免风控。

不进行切片，不进行语音转文字。

用法:
    python download_songs.py                          # 默认读取 outputs/all_songs.txt
    python download_songs.py path/to/list.txt
    python download_songs.py path/to/list.txt --out audio/songs --min-sleep 3 --max-sleep 8
"""

import argparse
import os
import random
import re
import subprocess
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(BASE_DIR, "outputs", "all_songs.txt")
DEFAULT_OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "songs")
# 故意不使用 cookies.txt / 账号登录，匿名下载以降低被封风险（仅能拿到普通画质音轨，足够）

# 同时识别 data-key="BV..." 和 行内裸的 BV 号 / URL 中的 BV 号
BV_PATTERN = re.compile(r"BV[A-Za-z0-9]{10}")
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


def extract_bv_entries(text):
    """返回 [(bv, title_or_None), ...]。**以 BV 为唯一去重键**，保持首次出现顺序。"""
    titles = {}
    for bv, title in ENTRY_PATTERN.findall(text):
        # HTML 实体反转义最常见几个
        title = title.replace("&amp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
        titles.setdefault(bv, clean_title(title))

    seen = set()
    ordered = []
    for bv in BV_PATTERN.findall(text):
        if bv in seen:
            continue
        seen.add(bv)
        ordered.append((bv, titles.get(bv)))
    return ordered


def collect_existing_bvs(output_dir):
    """扫描输出目录，返回已下载过的 BV 集合。仅依据文件名中的 BV 子串。"""
    existing = set()
    if not os.path.isdir(output_dir):
        return existing
    for fn in os.listdir(output_dir):
        if not fn.lower().endswith(".mp3"):
            continue
        for bv in BV_PATTERN.findall(fn):
            existing.add(bv)
    return existing


def build_output_path(bv, title, output_dir):
    """生成最终路径。始终在文件名末尾附加 [BV...] 以便溯源与避免冲突。"""
    if title:
        base = f"{sanitize_filename(title)} [{bv}]"
    else:
        base = bv
    return os.path.join(output_dir, f"{base}.mp3")


def download_one(bv, title, output_dir):
    """下载单个 BV 的音频为 mp3。"""
    os.makedirs(output_dir, exist_ok=True)
    output_path = build_output_path(bv, title, output_dir)

    video_url = f"https://www.bilibili.com/video/{bv}"
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "-x",
        "--audio-format",
        "mp3",
        "-o",
        output_path,
        "--no-playlist",
    ]
    cmd.append(video_url)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    if result.returncode != 0:
        return False, (result.stderr or "").strip().splitlines()[-1:] or ["未知错误"]
    return os.path.exists(output_path), [output_path]


def main():
    parser = argparse.ArgumentParser(description="批量下载 .txt 中的 Bilibili BV 音频（带睡眠间隔）")
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

    entries = extract_bv_entries(text)
    if args.limit > 0:
        entries = entries[: args.limit]
    if not entries:
        print("错误：未在文件中找到任何 BV 号")
        sys.exit(1)

    print(f"找到 {len(entries)} 个 BV 号，输出目录: {args.out}")
    print(f"下载间隔随机睡眠: {args.min_sleep}~{args.max_sleep} 秒")
    print("-" * 60)

    # 以 BV 为唯一去重键：一次性扫描输出目录，后续动态补充
    existing_bvs = collect_existing_bvs(args.out)
    if existing_bvs:
        print(f"输出目录已有 {len(existing_bvs)} 个 BV 的 mp3，将跳过")

    ok_count = 0
    skip_count = 0
    fail = []
    for i, (bv, title) in enumerate(entries, 1):
        label = f"{bv}" + (f"  {title}" if title else "")
        print(f"\n[{i}/{len(entries)}] {label}")

        if bv in existing_bvs:
            print("  已存在，跳过")
            skip_count += 1
            continue

        ok, info = download_one(bv, title, args.out)
        if ok:
            ok_count += 1
            existing_bvs.add(bv)
            print(f"  OK -> {info[0]}")
        else:
            fail.append((bv, info))
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
        for bv, info in fail:
            print(f"  - {bv}: {info}")


if __name__ == "__main__":
    main()
