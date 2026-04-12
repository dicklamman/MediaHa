import os
import time
import json
import traceback
import sys

def run_sync(sync_target, app_key, app_secret, refresh_token):
    try:
        import dropbox
        from dropbox.exceptions import ApiError, AuthError, HttpError
    except ImportError:
        yield b"Error: 'dropbox' module not installed. Please install it using 'pip install dropbox'.\n"
        return

    FOLDER_PAIRS = []
    if sync_target == 'ebook':
        FOLDER_PAIRS.append(("/media/eBook", "/eBook"))
    elif sync_target == 'music':
        FOLDER_PAIRS.append(("/media/music", "/music"))
    else:
        yield f"Invalid sync target: {sync_target}\n".encode('utf-8')
        return

    if not app_key or not app_secret or not refresh_token:
        yield b"Error: App Key, App Secret, or Refresh Token is missing. Please save settings first.\n"
        return

    try:
        dbx = dropbox.Dropbox(
            app_key=app_key,
            app_secret=app_secret,
            oauth2_refresh_token=refresh_token
        )
        yield b"Connected to Dropbox successfully.\n"
    except Exception as e:
        yield f"Error connecting to Dropbox: {e}\n".encode('utf-8')
        return

    def ensure_dropbox_folder(dbx, folder_path):
        try:
            dbx.files_create_folder_v2(folder_path)
            yield f"Created Dropbox folder: {folder_path}\n".encode('utf-8')
        except dropbox.exceptions.ApiError as e:
            if e.error.is_path() and e.error.get_path().is_conflict():
                yield f"Folder already exists: {folder_path}\n".encode('utf-8')
            else:
                yield f"Error creating folder {folder_path}: {e}\n".encode('utf-8')
                raise

    def list_dropbox_files(folder):
        files = {}
        try:
            yield f"[DEBUG] Listing Dropbox folder: {folder}\n".encode('utf-8')
            result = dbx.files_list_folder(folder)
            yield f"[DEBUG] Got initial response for {folder}\n".encode('utf-8')
            for entry in result.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    files[entry.name] = entry.size
            while result.has_more:
                yield f"[DEBUG] Fetching more entries, cursor: {result.cursor[:20]}...\n".encode('utf-8')
                result = dbx.files_list_folder_continue(result.cursor)
                for entry in result.entries:
                    if isinstance(entry, dropbox.files.FileMetadata):
                        files[entry.name] = entry.size
            yield f"[DEBUG] Listed {len(files)} files in {folder}\n".encode('utf-8')
        except ApiError as e:
            error_msg = f"[ERROR] ApiError listing Dropbox folder {folder}: {type(e).__name__}: {e}\n"
            yield error_msg.encode('utf-8')
            yield f"[ERROR] Traceback: {traceback.format_exc()}\n".encode('utf-8')
        except HttpError as e:
            error_msg = f"[ERROR] HttpError listing Dropbox folder {folder}: {type(e).__name__}: {e}\n"
            yield error_msg.encode('utf-8')
            yield f"[ERROR] Traceback: {traceback.format_exc()}\n".encode('utf-8')
        except Exception as e:
            error_msg = f"[ERROR] Unexpected error listing Dropbox folder {folder}: {type(e).__name__}: {e}\n"
            yield error_msg.encode('utf-8')
            yield f"[ERROR] Traceback: {traceback.format_exc()}\n".encode('utf-8')
        return files

    def upload_file(local_path, dropbox_path):
        try:
            yield f"[DEBUG] Starting upload: {local_path} -> {dropbox_path}\n".encode('utf-8')
            with open(local_path, "rb") as f:
                data = f.read()
                yield f"[DEBUG] Read {len(data)} bytes from local file\n".encode('utf-8')
                result = dbx.files_upload(data, dropbox_path, mode=dropbox.files.WriteMode.overwrite)
                yield f"[DEBUG] Upload completed, id: {result.id}\n".encode('utf-8')
            yield f"Uploaded: {local_path} -> {dropbox_path}\n".encode('utf-8')
        except ApiError as e:
            error_msg = f"[ERROR] ApiError uploading {local_path}: {type(e).__name__}: {e}\n"
            yield error_msg.encode('utf-8')
            yield f"[ERROR] Traceback: {traceback.format_exc()}\n".encode('utf-8')
        except HttpError as e:
            error_msg = f"[ERROR] HttpError uploading {local_path}: {type(e).__name__}: {e}\n"
            yield error_msg.encode('utf-8')
            yield f"[ERROR] Traceback: {traceback.format_exc()}\n".encode('utf-8')
        except Exception as e:
            error_msg = f"[ERROR] Upload failed for {local_path}: {type(e).__name__}: {e}\n"
            yield error_msg.encode('utf-8')
            yield f"[ERROR] Traceback: {traceback.format_exc()}\n".encode('utf-8')

    def delete_file(dropbox_path):
        try:
            dbx.files_delete_v2(dropbox_path)
            yield f"Deleted from Dropbox: {dropbox_path}\n".encode('utf-8')
        except Exception as e:
            yield f"Delete failed for {dropbox_path}: {e}\n".encode('utf-8')

    def sync_pair(local_root, dropbox_root):
        yield f"\n=== Recursive Sync: {local_root} -> {dropbox_root} ===\n".encode('utf-8')
        
        try:
            yield from ensure_dropbox_folder(dbx, dropbox_root)
        except Exception:
            pass
        
        for root, dirs, files in os.walk(local_root):
            rel_path = os.path.relpath(root, local_root)
            
            if rel_path == '.':
                current_dbx_folder = dropbox_root
            else:
                current_dbx_folder = dropbox_root + "/" + rel_path.replace(os.sep, "/")
            
            try:
                yield from ensure_dropbox_folder(dbx, current_dbx_folder)
            except Exception:
                pass
            
            local_files = {
                f: os.path.getsize(os.path.join(root, f))
                for f in files
            }
            
            dropbox_files = yield from list_dropbox_files(current_dbx_folder)

            for fname, fsize in local_files.items():
                dbx_path = f"{current_dbx_folder}/{fname}"
                if fname not in dropbox_files or dropbox_files[fname] != fsize:
                    yield from upload_file(os.path.join(root, fname), dbx_path)
                else:
                    yield f"Skipped (already exists with same size): {fname}\n".encode('utf-8')
        yield f"Sync completed: {local_root} -> {dropbox_root}\n".encode('utf-8')

    for local_folder, dropbox_folder in FOLDER_PAIRS:
        if os.path.exists(local_folder):
            yield from sync_pair(local_folder, dropbox_folder)
        else:
            yield f"Warning: Local folder not found: {local_folder}\n".encode('utf-8')

    yield b"\nAll syncs completed.\n"
