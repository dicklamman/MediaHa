import os
import requests
import shutil

VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.m2ts', '.mpg', '.mpeg'}

def get_alist_token(base_url, username, password):
    url = f"{base_url.rstrip('/')}/api/auth/login"
    data = {"username": username, "password": password}
    resp = requests.post(url, json=data, timeout=15)
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") != 200:
        raise Exception(result.get("message", "Login failed"))
    return result["data"]["token"]

def list_directory(base_url, path, token):
    url = f"{base_url.rstrip('/')}/api/fs/list"
    headers = {"Authorization": token}
    data = {"path": path, "refresh": False, "page": 1, "per_page": 1000}
    resp = requests.post(url, json=data, headers=headers, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    if result["code"] != 200:
        raise Exception(result.get("message"))
    return result["data"]["content"]

def get_file_sign(base_url, path, token):
    url = f"{base_url.rstrip('/')}/api/fs/get"
    headers = {"Authorization": token}
    data = {"path": path}
    try:
        resp = requests.post(url, json=data, headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if result["code"] != 200:
            raise Exception(result.get("message"))
        return result["data"].get("sign", "")
    except Exception:
        return ""

def generate_strm_generator(gist_config):
    api_url = gist_config.get('alist_url', 'http://192.168.1.100:5244')
    public_domain = gist_config.get('public_domain', 'https://alist.example.com')
    remote_root = gist_config.get('remote_path', '/OneDriveShare').rstrip('/')
    local_root = os.path.abspath(gist_config.get('local_dir', '/media/alist'))
    username = gist_config.get('username', 'admin')
    password = gist_config.get('password', '')
    try:
        yield f"Logging into AList URL: {api_url}...\n"
        token = get_alist_token(api_url, username, password)
        yield "Login successful ?\n"

        yield f"Clearing local directory: {local_root}...\n"
        if os.path.exists(local_root):
            shutil.rmtree(local_root)
        os.makedirs(local_root, exist_ok=True)

        yield f"Scanning AList remote path: {remote_root}\n"

        def recurse(current_remote_path, current_local_path):
            try:
                items = list_directory(api_url, current_remote_path, token)
            except Exception as e:
                yield f"? Failed to list {current_remote_path}: {e}\n"
                return

            if not items:
                return
            
            for item in items:
                name = item["name"]
                is_dir = item["is_dir"]
                full_remote = f"{current_remote_path}/{name}".replace('//', '/')
                full_local = os.path.join(current_local_path, name)

                if is_dir:
                    os.makedirs(full_local, exist_ok=True)
                    yield from recurse(full_remote, full_local)
                else:
                    ext = os.path.splitext(name.lower())[1]
                    if ext in VIDEO_EXTS:
                        sign = get_file_sign(api_url, full_remote, token)
                        if not sign:
                            yield f"? No sign for: {full_remote}\n"
                            continue
                        
                        stream_url = f"{public_domain.rstrip('/')}/d{full_remote}?sign={sign}"
                        strm_path = os.path.splitext(full_local)[0] + '.strm'
                        
                        try:
                            with open(strm_path, 'w', encoding='utf-8') as f:
                                f.write(stream_url + '\n')
                            yield f"? Generated: {full_remote} -> {strm_path}\n"
                        except Exception as e:
                            yield f"? Error writing {strm_path}: {e}\n"

        yield from recurse(remote_root, local_root)
        yield "\nAll signed .strm files generated successfully!\n"

    except Exception as e:
        yield f"\n? Error: {e}\n"
