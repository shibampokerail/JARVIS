import os
import requests
import zipfile
import subprocess
import re

#THIS PROGRAM MANAGES THE CHROMEDRIVER AND UPDATES THE CHROMEDRIVER TO THE NEWEST VERSION IF REQUIRED

def get_installed_chrome_version():
    """
    Detect installed Chrome version on Windows.
    Works for standard Chrome install.
    """
    try:
        result = subprocess.run(
            ['reg', 'query', r'HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon', '/v', 'version'],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
        )
        output = result.stdout
        match = re.search(r'version\s+REG_SZ\s+([0-9.]+)', output)
        if match:
            return match.group(1)
        raise Exception("Chrome version not found in registry.")
    except Exception as e:
        raise RuntimeError(f"Could not determine Chrome version: {e}")


def check_chromedriver_version(target_dir="driver"):
    """
    Checks if the ChromeDriver in the target_dir matches the installed Chrome version.
    Returns True if the versions match, otherwise False.
    """
    version_file_path = os.path.join(target_dir, "chromedriver_version.txt")

    if not os.path.exists(version_file_path):
        return False  # Version file does not exist, so return False

    with open(version_file_path, 'r') as version_file:
        stored_version = version_file.read().strip()

    installed_version = get_installed_chrome_version()

    if stored_version == installed_version:
        print(f"ChromeDriver version {stored_version} matches the installed Chrome version.")
        return True
    else:
        print(f"Installed Chrome version is {installed_version}. Stored ChromeDriver version is {stored_version}.")
        return False


def download_latest_cft_chromedriver(chrome_version, target_dir="drive"):
    version = chrome_version
    base_url = f"https://storage.googleapis.com/chrome-for-testing-public/{version}/win64/chromedriver-win64.zip"
    zip_path = os.path.join(target_dir, "chromedriver.zip")
    os.makedirs(target_dir, exist_ok=True)

    print(f"Downloading ChromeDriver for version {version}...")
    r = requests.get(base_url, stream=True)
    if r.status_code != 200:
        raise RuntimeError(f"Failed to download: {base_url}\nStatus code: {r.status_code}")

    with open(zip_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

    print("Extracting ChromeDriver...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(target_dir)

    os.remove(zip_path)
    print(f"ChromeDriver is ready in: {target_dir}")

    version_file_path = os.path.join(target_dir, "chromedriver_version.txt")
    with open(version_file_path, 'w') as version_file:
        version_file.write(version)

    print(f"Version {version} has been logged in: {version_file_path}")


def init_chromedriver():
    try:
        chrome_version = get_installed_chrome_version()
        print(f"Detected local Chrome version: {chrome_version}")

        target_dir = "../drive"
        if check_chromedriver_version(target_dir):
            print("ChromeDriver is up-to-date. No download needed.")
        else:
            print("ChromeDriver version mismatch or not found. Downloading the correct version.")
            download_latest_cft_chromedriver(chrome_version, target_dir)

    except Exception as e:
        print(f"[ERROR] {e}")


