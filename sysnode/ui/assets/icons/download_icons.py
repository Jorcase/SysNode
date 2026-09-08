import urllib.request
import os

icons = {
    "home.png": "https://img.icons8.com/ios-filled/50/ffffff/home.png",
    "settings.png": "https://img.icons8.com/ios-filled/50/ffffff/settings.png",
    "qr.png": "https://img.icons8.com/ios-filled/50/ffffff/qr-code.png",
    "smartphone.png": "https://img.icons8.com/ios-filled/50/ffffff/iphone.png",
    "laptop.png": "https://img.icons8.com/ios-filled/50/ffffff/laptop.png",
    "add.png": "https://img.icons8.com/ios-filled/50/ffffff/plus-math.png",
    "send.png": "https://img.icons8.com/ios-filled/50/ffffff/paper-plane.png",
    "file.png": "https://img.icons8.com/ios-filled/50/ffffff/document.png"
}

os.chdir(os.path.dirname(os.path.abspath(__file__)))
for name, url in icons.items():
    print(f"Downloading {name}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(name, 'wb') as out_file:
            out_file.write(response.read())
    except Exception as e:
        print(f"Failed to download {name}: {e}")
