import argparse
import re
import os
import shutil
from utils import download_video
from exAudio import *
from speech2text import *

# Main文件是作者用来测试的，请运行window.py


def cleanup_media_folders():
    """清理 audio 文件夹下的所有文件和子文件夹"""
    for folder in ["audio/conv", "audio/slice"]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            os.makedirs(folder, exist_ok=True)
            print(f"已清理文件夹: {folder}")


def extract_bv_from_url(url_or_bv):
    """从URL或BV号中提取BV号"""
    # 匹配BV号的正则表达式
    bv_pattern = r"BV[a-zA-Z0-9]+"
    match = re.search(bv_pattern, url_or_bv)
    if match:
        return match.group(0)
    return None


def process_single_video(bv_number):
    """处理单个视频"""
    try:
        # 移除BV前缀
        av = bv_number[2:] if bv_number.startswith("BV") else bv_number

        print(f"\n{'='*60}")
        print(f"开始处理: {bv_number}")
        print(f"{'='*60}")

        # 检查是否已有转换后的音频文件
        conv_audio_path = f"audio/conv/{bv_number}.mp3"
        if os.path.exists(conv_audio_path):
            print(f"检测到已存在音频文件: {conv_audio_path}")
            print("跳过视频下载，直接使用已有音频")
            filename = f"BV{av}"  # 使用BV号作为filename
        else:
            filename = download_video(av)

        foldername = process_audio_split(filename, folder_name=bv_number)

        run_analysis(foldername, output_filename=bv_number, prompt="以下是普通话的句子。")
        output_path = f"outputs/{bv_number}.txt"

        print(f"\n✓ 完成处理: {bv_number} -> {output_path}")
        return (bv_number, True, output_path)
    except Exception as e:
        print(f"\n✗ 处理失败: {bv_number} - 错误: {str(e)}")
        return (bv_number, False, str(e))


def process_batch_file(file_path):
    """批量处理文件中的视频（顺序处理）"""
    if not os.path.exists(file_path):
        print(f"错误：文件不存在 {file_path}")
        return

    # 读取文件并提取所有BV号
    bv_numbers = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                bv = extract_bv_from_url(line)
                if bv and bv not in bv_numbers:  # 去重
                    bv_numbers.append(bv)

    if not bv_numbers:
        print("错误：文件中没有找到有效的BV号")
        return

    print(f"\n找到 {len(bv_numbers)} 个视频待处理")
    print("-" * 60)

    # 顺序处理所有视频
    results = []
    for i, bv in enumerate(bv_numbers, 1):
        print(f"\n进度: [{i}/{len(bv_numbers)}]")
        result = process_single_video(bv)
        results.append(result)

    # 打印汇总
    print("\n" + "=" * 60)
    print("批量处理完成汇总")
    print("=" * 60)
    successful = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]

    print(f"\n成功: {len(successful)}/{len(results)}")
    for bv, _, output in successful:
        print(f"  ✓ {bv} -> {output}")

    if failed:
        print(f"\n失败: {len(failed)}/{len(results)}")
        for bv, _, error in failed:
            print(f"  ✗ {bv}: {error}")


parser = argparse.ArgumentParser(description="将B站视频转换为文本")
parser.add_argument("bv", nargs="?", help="BV号（例如：BV1dDyyBwEDr）或包含URL的txt文件路径（例如：inputs/sales.txt）")
args = parser.parse_args()

if args.bv:
    input_arg = args.bv
else:
    input_arg = input("请输入BV号[默认读取input.txt]：").strip()
    if not input_arg:
        # 用户按下Enter，使用默认的input.txt
        default_input = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inputs", "input.txt")
        if os.path.exists(default_input):
            input_arg = default_input
        else:
            print("错误：默认输入文件不存在：", default_input)
            exit(1)

# 检查是否是文件路径
if input_arg.endswith(".txt") or os.path.exists(input_arg):
    # 批量处理模式（顺序处理）
    # 加载Whisper模型一次，供所有视频使用
    load_whisper("medium")
    process_batch_file(input_arg)
    cleanup_media_folders()
else:
    # 单个视频处理模式
    av = input_arg
    # 如果输入包含完整的BV号，处理它；否则假设已经是正确格式
    if av.startswith("BV"):
        av = av[2:]

    bv_number = f"BV{av}"
    conv_audio_path = f"audio/conv/{bv_number}.mp3"

    # 检查是否已有转换后的音频文件
    if os.path.exists(conv_audio_path):
        print(f"检测到已存在音频文件: {conv_audio_path}")
        print("跳过视频下载，直接使用已有音频")
        filename = bv_number
    else:
        filename = download_video(av)

    foldername = process_audio_split(filename, folder_name=bv_number)

    load_whisper("medium")
    run_analysis(foldername, output_filename=bv_number, prompt="以下是普通话的句子。")
    output_path = f"outputs/{bv_number}.txt"
    print("转换完成！", output_path)
    cleanup_media_folders()
