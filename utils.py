import os
import re
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_CONV_DIR = os.path.join(BASE_DIR, "audio", "conv")
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
BILIBILI_VIDEO_DIR = os.path.join(BASE_DIR, "bilibili_video")


def ensure_folders_exist(*dirs):
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def download_video(bv_number):
    """
    使用yt-dlp直接下载B站视频的音频（mp3格式）。
    参数:
        bv_number: 字符串形式的BV号（不含"BV"前缀）或完整BV号
    返回:
        BV号
    """
    if not bv_number.startswith("BV"):
        bv_number = "BV" + bv_number
    video_url = f"https://www.bilibili.com/video/{bv_number}"
    audio_output_dir = AUDIO_CONV_DIR
    ensure_folders_exist(audio_output_dir, OUTPUTS_DIR)
    output_path = os.path.join(audio_output_dir, f"{bv_number}.mp3")
    print(f"使用yt-dlp下载音频: {video_url}")

    # 优先使用项目根目录下的 cookies.txt，用于下载需要登录的视频
    cookies_path = os.path.join(BASE_DIR, "cookies.txt")

    try:
        cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            "-x",  # 提取音频
            "--audio-format",
            "mp3",  # 转为mp3
            "-o",
            output_path,  # 输出路径
            "--no-playlist",  # 不下载播放列表
        ]
        if os.path.exists(cookies_path):
            cmd.extend(["--cookies", cookies_path])
            print(f"检测到cookies，使用: {cookies_path}")
        cmd.append(video_url)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        if result.returncode != 0:
            print("下载失败:", result.stderr)
        else:
            print(result.stdout)
            if os.path.exists(output_path):
                print(f"音频已成功下载到: {output_path}")
            else:
                print("警告：未找到期望的mp3文件，下载可能失败。")
    except Exception as e:
        print("发生错误:", str(e))
    return bv_number


def download_youtube_audio(video_id):
    """
    使用yt-dlp直接下载YouTube视频的音频（mp3格式），输出到 audio/conv/YT_<id>.mp3。
    参数:
        video_id: YouTube视频ID（11位字符）或完整URL
    返回:
        统一标识符 "YT_<video_id>"，与main.py流程其它部分共用文件名
    """
    # 允许传入完整URL或仅ID
    if video_id.startswith("http://") or video_id.startswith("https://"):
        video_url = video_id
        # 从URL中提取11位ID用于命名
        m = re.search(r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})", video_id)
        if m:
            real_id = m.group(1)
        else:
            # 回退方案：使用完整URL的安全形式
            real_id = re.sub(r"[^A-Za-z0-9_-]", "_", video_id)[-11:]
    else:
        real_id = video_id
        video_url = f"https://www.youtube.com/watch?v={video_id}"

    identifier = f"YT_{real_id}"
    audio_output_dir = AUDIO_CONV_DIR
    ensure_folders_exist(audio_output_dir, OUTPUTS_DIR)
    output_path = os.path.join(audio_output_dir, f"{identifier}.mp3")
    print(f"使用yt-dlp下载YouTube音频: {video_url}")

    # 优先使用项目根目录下的 cookies.txt（YouTube会员/限制视频可能需要）
    cookies_path = os.path.join(BASE_DIR, "cookies.txt")

    try:
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
        if os.path.exists(cookies_path):
            cmd.extend(["--cookies", cookies_path])
            print(f"检测到cookies，使用: {cookies_path}")
        cmd.append(video_url)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        if result.returncode != 0:
            print("下载失败:", result.stderr)
        else:
            print(result.stdout)
            if os.path.exists(output_path):
                print(f"音频已成功下载到: {output_path}")
            else:
                print("警告：未找到期望的mp3文件，下载可能失败。")
    except Exception as e:
        print("发生错误:", str(e))
    return identifier


def download_youtube(url, fmt="mp3"):
    """
    Download a YouTube video as MP3 or MP4 using yt-dlp.
    Args:
        url: YouTube URL
        fmt: 'mp3' for audio only, 'mp4' for video
    """
    if fmt == "mp3":
        output_dir = AUDIO_DIR
        ensure_folders_exist(output_dir)
        output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
        cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--remote-components",
            "ejs:github",
            "-x",
            "--audio-format",
            "mp3",
            "-o",
            output_template,
            url,
        ]
    elif fmt == "mp4":
        output_dir = BILIBILI_VIDEO_DIR
        ensure_folders_exist(output_dir)
        output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
        cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--remote-components",
            "ejs:github",
            "-f",
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
            "-o",
            output_template,
            url,
        ]
    else:
        print(f"Unsupported format: {fmt}")
        return

    print(f"Downloading {fmt}: {url}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if result.returncode != 0:
        print("Download failed:", result.stderr)
    else:
        print(result.stdout)
        print(f"Download complete. Saved to: {output_dir}/")
