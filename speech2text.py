import whisper
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

whisper_model = None

# 线程数
NUM_THREADS = 3

# 每个线程独立的模型实例
_thread_local = threading.local()
_model_name = "tiny"
_device = None


def is_cuda_available():
    return whisper.torch.cuda.is_available()


def load_whisper(model="tiny"):
    global whisper_model, _model_name, _device
    _device = "cuda" if is_cuda_available() else "cpu"
    _model_name = model
    whisper_model = whisper.load_model(model, device=_device)
    print("Whisper模型：" + model)


def _get_thread_model():
    """获取当前线程的模型实例，如果没有则创建一个"""
    if not hasattr(_thread_local, "model"):
        print(f"[线程 {threading.current_thread().name}] 加载Whisper模型: {_model_name}")
        _thread_local.model = whisper.load_model(_model_name, device=_device)
    return _thread_local.model


def _transcribe_slice(index, fn, filename, prompt, total):
    """转录单个音频切片，返回 (index, text)"""
    model = _get_thread_model()
    print(f"[线程 {threading.current_thread().name}] 正在转换第{index + 1}/{total}个音频... {fn}")
    result = model.transcribe(f"audio/slice/{filename}/{fn}", initial_prompt=prompt)
    text = "".join([seg["text"] for seg in result["segments"] if seg is not None])
    print(f"[线程 {threading.current_thread().name}] 完成第{index + 1}/{total}个音频: {fn}")
    return index, text


def run_analysis(filename, output_filename=None, model="tiny", prompt="以下是普通话的句子。"):
    global whisper_model
    print("正在加载Whisper模型...")
    # 读取列表中的音频文件
    audio_list = os.listdir(f"audio/slice/{filename}")
    print("加载Whisper模型成功！")
    # 添加排序逻辑
    audio_files = sorted(audio_list, key=lambda x: int(os.path.splitext(x)[0]))  # 按文件名数字排序
    # 创建outputs文件夹
    os.makedirs("outputs", exist_ok=True)
    print(f"正在转换文本（{NUM_THREADS}线程并行）...")

    # 如果没有指定output_filename，使用filename
    if output_filename is None:
        output_filename = filename

    # 清空输出文件（如果存在）
    output_file_path = f"outputs/{output_filename}.txt"
    if os.path.exists(output_file_path):
        os.remove(output_file_path)

    total = len(audio_files)
    results = [None] * total  # 预分配结果列表以保持顺序

    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = {executor.submit(_transcribe_slice, i, fn, filename, prompt, total): i for i, fn in enumerate(audio_files)}
        for future in as_completed(futures):
            idx, text = future.result()
            results[idx] = text

    # 按顺序写入输出文件
    with open(output_file_path, "w", encoding="utf-8") as f:
        for text in results:
            f.write(text + "\n")
