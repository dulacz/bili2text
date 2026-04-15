import os
import re
import subprocess
import sys


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
    audio_output_dir = "audio/conv"
    ensure_folders_exist(audio_output_dir, "outputs")
    output_path = os.path.join(audio_output_dir, f"{bv_number}.mp3")
    print(f"使用yt-dlp下载音频: {video_url}")

    # 优先使用项目根目录下的 cookies.txt，用于下载需要登录的视频
    project_dir = os.path.dirname(os.path.abspath(__file__))
    cookies_path = os.path.join(project_dir, "cookies.txt")

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


def download_youtube(url, fmt="mp3"):
    """
    Download a YouTube video as MP3 or MP4 using yt-dlp.
    Args:
        url: YouTube URL
        fmt: 'mp3' for audio only, 'mp4' for video
    """
    if fmt == "mp3":
        output_dir = "audio"
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
        output_dir = "bilibili_video"
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
