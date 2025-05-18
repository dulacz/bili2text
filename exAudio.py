from moviepy.editor import VideoFileClip
from pydub import AudioSegment
import os
import time
import glob
import math

def convert_flv_to_mp3(name, target_name=None, folder='bilibili_video'):
    # 提取视频中的音频并保存为 MP3 到 audio/conv/{时间} 目录
    video_files = glob.glob(os.path.join(f"{folder}/{name}", "*.mp4"))
    for i in range(len(video_files)):
        clip = VideoFileClip(video_files[i])
        audio = clip.audio
        os.makedirs(f"audio/conv/{target_name}", exist_ok=True)
        output_name = target_name if target_name else name
        audio.write_audiofile(f"audio/conv/{target_name}/{output_name}_{i}.mp3") # 命名为 时间_序号.mp3

def split_mp3(filename, folder_name, slice_length=45000, target_folder="audio/slice"):
    audio_files = glob.glob(os.path.join(filename, "*.mp3"))
    cnt = 0 # 切片序号，防止生成的文本乱序
    for audio_file in audio_files:
        print(f"Slicing {audio_file}")
        audio = AudioSegment.from_mp3(audio_file)
        total_slices = math.ceil(len(audio) / slice_length)
        target_dir = os.path.join(target_folder, folder_name)
        os.makedirs(target_dir, exist_ok=True)
        for i in range(total_slices):
            cnt += 1
            start = i * slice_length
            if i == total_slices - 1:
                end = -1 # 最后一段长度不足 slice_length
            else:
                end = start + slice_length
            slice_audio = audio[start:end]
            slice_path = os.path.join(target_dir, f"{cnt}.mp3")
            slice_audio.export(slice_path, format="mp3")
            print(f"Slice {cnt} saved: {slice_path}")

def process_audio_split(name):
    # 生成唯一文件夹名，并依次调用转换和分割函数
    folder_name = time.strftime('%Y%m%d%H%M%S')
    convert_flv_to_mp3(name, target_name=folder_name)
    conv_dir = f"audio/conv/{folder_name}"
    split_mp3(conv_dir, folder_name)
    return folder_name

