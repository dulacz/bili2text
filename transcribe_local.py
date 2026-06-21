"""将本地音频/视频文件转换为文本（txt）。

默认处理 inputs 目录下指定的会议录像；也可通过命令行传入其它文件路径：
    python transcribe_local.py "C:\\path\\to\\media.mp4"
"""

import os
import shutil
import subprocess
import sys

from exAudio import process_audio_split
from speech2text import load_whisper, run_analysis

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
AUDIO_CONV_DIR = os.path.join(BASE_DIR, "audio", "conv")
AUDIO_SLICE_DIR = os.path.join(BASE_DIR, "audio", "slice")

# 默认要处理的文件
DEFAULT_FILE = os.path.join(
    BASE_DIR,
    "inputs",
    "APRD 健康嘉年华  线上财富智慧课二：健康财富管理进阶课，用系统化投资构筑终身养老财富-20260508_125927-Meeting Recording.mp4",
)


def convert_to_mp3(file_path, conv_audio_path):
    """将任意音视频文件转换为 mp3；若已是 mp3 则直接复制。"""
    os.makedirs(AUDIO_CONV_DIR, exist_ok=True)
    if os.path.exists(conv_audio_path):
        print(f"检测到已存在音频文件: {conv_audio_path}，跳过转换")
        return

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".mp3":
        shutil.copy2(file_path, conv_audio_path)
        print(f"已复制音频文件: {conv_audio_path}")
        return

    print("正在转换音频格式...")
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", file_path, conv_audio_path],
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 转换失败: {result.stderr}")
    print(f"已转换音频文件: {conv_audio_path}")


def cleanup_media_folders():
    """清理 audio/conv 与 audio/slice 下的临时文件。"""
    for folder in [AUDIO_CONV_DIR, AUDIO_SLICE_DIR]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            os.makedirs(folder, exist_ok=True)
            print(f"已清理文件夹: {folder}")


def transcribe_local_media(file_path):
    """处理单个本地音频/视频文件，输出 txt 到 outputs 目录。"""
    file_path = os.path.abspath(file_path)
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    identifier = os.path.splitext(os.path.basename(file_path))[0]

    print("=" * 60)
    print(f"开始处理本地文件: {file_path}")
    print("=" * 60)

    conv_audio_path = os.path.join(AUDIO_CONV_DIR, f"{identifier}.mp3")
    convert_to_mp3(file_path, conv_audio_path)

    foldername = process_audio_split(identifier, folder_name=identifier)
    run_analysis(foldername, output_filename=identifier, prompt="")

    output_path = os.path.join(OUTPUT_DIR, f"{identifier}.txt")
    print(f"\n[OK] 完成处理: {identifier} -> {output_path}")
    return output_path


def main():
    file_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FILE

    load_whisper("medium")
    try:
        output_path = transcribe_local_media(file_path)
        print("转换完成！", output_path)
    except Exception as e:
        print("转换失败：", str(e))
        sys.exit(1)
    finally:
        cleanup_media_folders()


if __name__ == "__main__":
    main()
