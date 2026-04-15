import sys
from utils import download_youtube


def main():
    url = input("Enter YouTube URL: ").strip()
    if not url:
        print("Error: No URL provided.")
        sys.exit(1)

    print("\nDownload format:")
    print("  1. MP3 (audio only)")
    print("  2. MP4 (video)")
    choice = input("Choose format [1/2]: ").strip()

    if choice == "1":
        download_youtube(url, fmt="mp3")
    elif choice == "2":
        download_youtube(url, fmt="mp4")
    else:
        print("Invalid choice.")
        sys.exit(1)


if __name__ == "__main__":
    main()
