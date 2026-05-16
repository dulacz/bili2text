import argparse
import re
import os
import shutil
import subprocess
from utils import download_video, download_youtube_audio
from exAudio import *
from speech2text import *

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

# Main文件是作者用来测试的，请运行window.py

# 各平台默认的Whisper提示词
PROMPT_BY_PLATFORM = {
    "bilibili": "以下是普通话的句子。",
    "youtube": "",
}


LOCAL_MEDIA_EXTENSIONS = {".mp3", ".m4a", ".mp4", ".wav", ".flac", ".ogg", ".aac", ".mkv", ".flv", ".avi", ".webm"}


def is_local_media_file(path):
    ext = os.path.splitext(path)[1].lower()
    return ext in LOCAL_MEDIA_EXTENSIONS and os.path.isfile(path)


def process_local_media_file(file_path):
    """处理本地音频/视频文件"""
    file_path = os.path.abspath(file_path)
    identifier = os.path.splitext(os.path.basename(file_path))[0]
    try:
        print(f"\n{'='*60}")
        print(f"开始处理本地文件: {file_path}")
        print(f"{'='*60}")

        conv_audio_path = f"audio/conv/{identifier}.mp3"
        os.makedirs("audio/conv", exist_ok=True)

        if not os.path.exists(conv_audio_path):
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".mp3":
                shutil.copy2(file_path, conv_audio_path)
                print(f"已复制音频文件: {conv_audio_path}")
            else:
                print("正在转换音频格式...")
                result = subprocess.run(
                    ["ffmpeg", "-y", "-i", file_path, conv_audio_path],
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if result.returncode != 0:
                    raise RuntimeError(f"ffmpeg 转换失败: {result.stderr}")
                print(f"已转换音频文件: {conv_audio_path}")
        else:
            print(f"检测到已存在音频文件: {conv_audio_path}，跳过转换")

        foldername = process_audio_split(identifier, folder_name=identifier)
        run_analysis(foldername, output_filename=identifier, prompt="")
        output_path = os.path.join(OUTPUT_DIR, f"{identifier}.txt")

        print(f"\n[OK] 完成处理: {identifier} -> {output_path}")
        return (identifier, True, output_path)
    except Exception as e:
        print(f"\n[FAIL] 处理失败: {identifier} - 错误: {str(e)}")
        return (identifier, False, str(e))


def cleanup_media_folders():
    """清理 audio 文件夹下的所有文件和子文件夹"""
    for folder in ["audio/conv", "audio/slice"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            os.makedirs(folder, exist_ok=True)
            print(f"已清理文件夹: {folder}")


def extract_bv_from_url(url_or_bv):
    """从URL或BV号中提取BV号"""
    bv_pattern = r"BV[a-zA-Z0-9]+"
    match = re.search(bv_pattern, url_or_bv)
    if match:
        return match.group(0)
    return None


def extract_youtube_id(url_or_id):
    """从YouTube URL中提取11位视频ID；若传入的就是11位ID则直接返回。"""
    # 已经是11位ID
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_id):
        return url_or_id
    # 从常见YouTube URL格式中提取
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})", url_or_id)
    if m:
        return m.group(1)
    return None


def detect_platform(text):
    """识别输入是 bilibili 还是 youtube。
    返回 (platform, identifier)：
        platform: "bilibili" / "youtube" / None
        identifier: 用于命名/去重的统一ID（BV... 或 YT_<id>）
    """
    text = text.strip()
    # YouTube 优先匹配（URL中含明确域名特征）
    if re.search(r"(youtube\.com|youtu\.be)", text, re.IGNORECASE):
        yt_id = extract_youtube_id(text)
        if yt_id:
            return "youtube", f"YT_{yt_id}"
    # Bilibili BV
    bv = extract_bv_from_url(text)
    if bv:
        return "bilibili", bv
    # 裸的YouTube ID（11位）作为兜底
    yt_id = extract_youtube_id(text)
    if yt_id:
        return "youtube", f"YT_{yt_id}"
    return None, None


def process_single_video(identifier, platform=None):
    """处理单个视频。identifier 形如 'BV...' 或 'YT_<id>'。"""
    try:
        # 若未显式给出platform，根据identifier前缀推断
        if platform is None:
            platform = "youtube" if identifier.startswith("YT_") else "bilibili"

        print(f"\n{'='*60}")
        print(f"开始处理 [{platform}]: {identifier}")
        print(f"{'='*60}")

        # 检查是否已有转换后的音频文件（命名统一为 audio/conv/<identifier>.mp3）
        conv_audio_path = f"audio/conv/{identifier}.mp3"
        if os.path.exists(conv_audio_path):
            print(f"检测到已存在音频文件: {conv_audio_path}")
            print("跳过视频下载，直接使用已有音频")
            filename = identifier
        else:
            if platform == "bilibili":
                av = identifier[2:] if identifier.startswith("BV") else identifier
                filename = download_video(av)
            elif platform == "youtube":
                yt_id = identifier[3:] if identifier.startswith("YT_") else identifier
                filename = download_youtube_audio(yt_id)
            else:
                raise ValueError(f"未知平台: {platform}")

        foldername = process_audio_split(filename, folder_name=identifier)

        prompt = PROMPT_BY_PLATFORM.get(platform, "")
        run_analysis(foldername, output_filename=identifier, prompt=prompt)
        output_path = os.path.join(OUTPUT_DIR, f"{identifier}.txt")

        print(f"\n✓ 完成处理: {identifier} -> {output_path}")
        return (identifier, True, output_path)
    except Exception as e:
        print(f"\n✗ 处理失败: {identifier} - 错误: {str(e)}")
        return (identifier, False, str(e))


def process_batch_file(file_path):
    """批量处理文件中的视频（顺序处理），同时支持 Bilibili BV 与 YouTube 链接。"""
    if not os.path.exists(file_path):
        print(f"错误：文件不存在 {file_path}")
        return

    # 读取文件并提取所有视频标识（去重，保持顺序）
    items = []  # [(platform, identifier), ...]
    seen = set()
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            platform, identifier = detect_platform(line)
            if identifier and identifier not in seen:
                items.append((platform, identifier))
                seen.add(identifier)
            elif not identifier:
                print(f"跳过无法识别的行: {line}")

    if not items:
        print("错误：文件中没有找到有效的Bilibili BV号或YouTube链接")
        return

    print(f"\n找到 {len(items)} 个视频待处理")
    print("-" * 60)

    # 顺序处理所有视频
    results = []
    for i, (platform, identifier) in enumerate(items, 1):
        print(f"\n进度: [{i}/{len(items)}]")
        result = process_single_video(identifier, platform=platform)
        results.append(result)

    # 打印汇总
    print("\n" + "=" * 60)
    print("批量处理完成汇总")
    print("=" * 60)
    successful = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]

    print(f"\n成功: {len(successful)}/{len(results)}")
    for ident, _, output in successful:
        print(f"  ✓ {ident} -> {output}")

    if failed:
        print(f"\n失败: {len(failed)}/{len(results)}")
        for ident, _, error in failed:
            print(f"  ✗ {ident}: {error}")


parser = argparse.ArgumentParser(description="将B站/YouTube视频转换为文本")
parser.add_argument(
    "bv",
    nargs="?",
    help="BV号、YouTube链接，或包含URL的txt文件路径（例如：inputs/sales.txt）",
)
args = parser.parse_args()

if args.bv:
    input_arg = args.bv
else:
    input_arg = input("请输入BV号或YouTube链接[默认读取input.txt]：").strip()
    if not input_arg:
        # 用户按下Enter，使用默认的input.txt
        default_input = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inputs", "input.txt")
        if os.path.exists(default_input):
            input_arg = default_input
        else:
            print("错误：默认输入文件不存在：", default_input)
            exit(1)

# 检查是否是本地媒体文件
if is_local_media_file(input_arg):
    load_whisper("medium")
    _, ok, info = process_local_media_file(input_arg)
    if ok:
        print("转换完成！", info)
    else:
        print("转换失败：", info)
    cleanup_media_folders()
# 检查是否是文件路径
elif input_arg.endswith(".txt") or os.path.exists(input_arg):
    # 批量处理模式（顺序处理）
    # 加载Whisper模型一次，供所有视频使用
    load_whisper("medium")
    process_batch_file(input_arg)
    cleanup_media_folders()
else:
    # 单个视频处理模式
    platform, identifier = detect_platform(input_arg)
    if not identifier:
        print("错误：无法从输入中识别出 Bilibili BV号 或 YouTube 视频ID/链接")
        exit(1)

    load_whisper("medium")
    _, ok, info = process_single_video(identifier, platform=platform)
    if ok:
        print("转换完成！", info)
    else:
        print("转换失败：", info)
    cleanup_media_folders()
