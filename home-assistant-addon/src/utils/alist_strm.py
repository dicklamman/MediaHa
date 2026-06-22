import os
import requests
import shutil

VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.m2ts', '.mpg', '.mpeg'}
SUBTITLE_EXTS = {'.srt', '.ass', '.ssa', '.vtt', '.sub'}

def download_to_disk(download_url, dest_path, chunk_size=64 * 1024):
    """Stream a remote file directly to local disk in chunks."""
    with requests.get(download_url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)

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

def refresh_directory(base_url, path, token, timeout=300, retries=2):
    """Force AList to re-fetch the directory listing from the underlying cloud storage."""
    url = f"{base_url.rstrip('/')}/api/fs/refresh"
    headers = {"Authorization": token}
    data = {"path": path}
    
    last_error = None
    for attempt in range(retries):
        try:
            resp = requests.post(url, json=data, headers=headers, timeout=timeout)
            
            # Debug: log response info
            resp_text = resp.text if resp.text else ""
            if not resp_text or resp_text.strip() == '':
                last_error = f"Empty response (status={resp.status_code})"
                if attempt < retries - 1:
                    continue
                raise Exception(f"refresh failed for {path}: {last_error}")
            
            try:
                result = resp.json()
                if result.get("code") != 200:
                    last_error = f"API error - {result.get('message', 'unknown')}"
                    if attempt < retries - 1:
                        continue
                    raise Exception(f"refresh failed for {path}: {last_error}")
                return  # Success
            except ValueError as e:
                # JSON decode error
                last_error = f"Invalid JSON (status={resp.status_code}, body={resp_text[:200]})"
                if attempt < retries - 1:
                    continue
                raise Exception(f"refresh failed for {path}: {last_error}")
                
        except requests.exceptions.Timeout:
            last_error = f"Server timeout after {timeout}s"
            if attempt < retries - 1:
                continue
            raise Exception(f"refresh timeout for {path}: {last_error}")
        except requests.exceptions.ConnectionError as e:
            last_error = f"Connection error: {e}"
            if attempt < retries - 1:
                continue
            raise Exception(f"refresh connection error for {path}: {last_error}")
        except Exception as e:
            if "refresh" in str(e).lower():
                raise
            last_error = str(e)
            if attempt < retries - 1:
                continue
            raise Exception(f"refresh failed for {path}: {last_error}")
    
    # If we get here, all retries failed
    raise Exception(f"refresh failed for {path}: {last_error} (after {retries} attempts)")

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
        yield f"Refreshing AList remote path from cloud storage: {remote_root}...\n"
        try:
            refresh_directory(api_url, remote_root, token)
            yield f"? Refreshed: {remote_root}\n"
        except Exception as e:
            yield f"? {e} (continuing with cached listing)\n"

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
                    try:
                        refresh_directory(api_url, full_remote, token)
                        yield f"? Refreshed: {full_remote}\n"
                    except Exception as e:
                        yield f"? {e} (continuing with cached listing)\n"
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
                    elif ext in SUBTITLE_EXTS:
                        sign = get_file_sign(api_url, full_remote, token)
                        if not sign:
                            yield f"? No sign for: {full_remote}\n"
                            continue

                        download_url = f"{public_domain.rstrip('/')}/d{full_remote}?sign={sign}"

                        try:
                            download_to_disk(download_url, full_local)
                            yield f"? Downloaded: {full_remote} -> {full_local}\n"
                        except Exception as e:
                            yield f"? Error downloading {full_remote}: {e}\n"

        yield from recurse(remote_root, local_root)
        yield "\nAll signed .strm and downloaded subtitle files generated successfully!\n"

    except Exception as e:
        yield f"\n? Error: {e}\n"
