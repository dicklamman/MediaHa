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

    # For Scoped App (App Folder), paths must be relative to the app folder
    # The app folder is /Sync 2026, so we sync to /Sync 2026/eBook, /Sync 2026/music
    yield f"[INFO] Using App Folder: /Sync 2026\n".encode('utf-8')
    for i, (local, remote) in enumerate(FOLDER_PAIRS):
        FOLDER_PAIRS[i] = (local, f"/Sync 2026{remote}")

    if not app_key or not app_secret or not refresh_token:
        yield b"Error: App Key, App Secret, or Refresh Token is missing. Please save settings first.\n"
        return

    try:
        yield f"[DEBUG] Initializing Dropbox client...\n".encode('utf-8')

        # Always use access token mode (simpler, works with generated tokens)
        yield f"[DEBUG] Using access token authentication\n".encode('utf-8')
        dbx = dropbox.Dropbox(
            app_key=app_key,
            app_secret=app_secret,
            oauth2_access_token=refresh_token
        )

        yield f"[DEBUG] Dropbox client initialized\n".encode('utf-8')
        yield b"Connected to Dropbox successfully.\n"

        # Test the connection by getting account info
        try:
            account = dbx.users_get_current_account()
            yield f"[DEBUG] Connected as: {account.name.display_name} ({account.email})\n".encode('utf-8')
        except AuthError as e:
            error_detail = f"[AUTH_ERROR] Access token is invalid or expired: {e}\n"
            yield error_detail.encode('utf-8')
            yield b"\n[IMPORTANT] Your Access Token has expired. Please regenerate a new one from:\n"
            yield b"   https://www.dropbox.com/developers/apps -> Your App -> OAuth2 -> Generate\n"
            yield b"   Then update the token in MediaHa and save.\n"
            return
        except Exception as e:
            yield f"[DEBUG] Warning: Could not get account info: {type(e).__name__}: {e}\n".encode('utf-8')

    except Exception as e:
        error_detail = f"Error connecting to Dropbox: {type(e).__name__}: {e}\n"
        yield error_detail.encode('utf-8')
        yield f"[ERROR] Full traceback:\n{traceback.format_exc()}\n".encode('utf-8')
        return

    def ensure_dropbox_folder(dbx, folder_path):
        try:
            yield f"[DEBUG] Creating/verifying Dropbox folder: {folder_path}\n".encode('utf-8')
            result = dbx.files_create_folder_v2(folder_path)
            yield f"Created Dropbox folder: {folder_path}\n".encode('utf-8')
        except ApiError as e:
            if e.error.is_path() and e.error.get_path().is_conflict():
                yield f"[DEBUG] Folder already exists (conflict): {folder_path}\n".encode('utf-8')
            else:
                yield f"[ERROR] ApiError creating folder {folder_path}: {type(e).__name__}: {e}\n".encode('utf-8')
                yield f"[ERROR] Traceback: {traceback.format_exc()}\n".encode('utf-8')
                raise
        except Exception as e:
            yield f"[ERROR] Unexpected error creating folder {folder_path}: {type(e).__name__}: {e}\n".encode('utf-8')
            yield f"[ERROR] Traceback: {traceback.format_exc()}\n".encode('utf-8')
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
            yield f"[DEBUG] Deleting from Dropbox: {dropbox_path}\n".encode('utf-8')
            result = dbx.files_delete_v2(dropbox_path)
            yield f"[DEBUG] Deleted, id: {result.metadata.id}\n".encode('utf-8')
            yield f"Deleted from Dropbox: {dropbox_path}\n".encode('utf-8')
        except ApiError as e:
            error_msg = f"[ERROR] ApiError deleting {dropbox_path}: {type(e).__name__}: {e}\n"
            yield error_msg.encode('utf-8')
            yield f"[ERROR] Traceback: {traceback.format_exc()}\n".encode('utf-8')
        except HttpError as e:
            error_msg = f"[ERROR] HttpError deleting {dropbox_path}: {type(e).__name__}: {e}\n"
            yield error_msg.encode('utf-8')
            yield f"[ERROR] Traceback: {traceback.format_exc()}\n".encode('utf-8')
        except Exception as e:
            error_msg = f"[ERROR] Delete failed for {dropbox_path}: {type(e).__name__}: {e}\n"
            yield error_msg.encode('utf-8')
            yield f"[ERROR] Traceback: {traceback.format_exc()}\n".encode('utf-8')

    def sync_pair(local_root, dropbox_root):
        yield f"\n=== Recursive Sync: {local_root} -> {dropbox_root} ===\n".encode('utf-8')

        # Configure Dropbox client with timeout
        try:
            dbx._timeout = 60  # 60 second timeout
            yield f"[DEBUG] Dropbox timeout set to 60 seconds\n".encode('utf-8')
        except:
            yield f"[DEBUG] Could not set custom timeout\n".encode('utf-8')

        try:
            yield from ensure_dropbox_folder(dbx, dropbox_root)
        except Exception as e:
            yield f"[ERROR] Failed to ensure root folder exists: {e}\n".encode('utf-8')
            yield f"[ERROR] Traceback: {traceback.format_exc()}\n".encode('utf-8')

        try:
            for root, dirs, files in os.walk(local_root):
                rel_path = os.path.relpath(root, local_root)

                if rel_path == '.':
                    current_dbx_folder = dropbox_root
                else:
                    current_dbx_folder = dropbox_root + "/" + rel_path.replace(os.sep, "/")

                yield f"[DEBUG] Processing local folder: {root}\n".encode('utf-8')
                yield f"[DEBUG] Target Dropbox folder: {current_dbx_folder}\n".encode('utf-8')

                try:
                    yield from ensure_dropbox_folder(dbx, current_dbx_folder)
                except Exception as e:
                    yield f"[ERROR] Failed to ensure folder {current_dbx_folder}: {e}\n".encode('utf-8')
                    continue

                local_files = {
                    f: os.path.getsize(os.path.join(root, f))
                    for f in files
                }
                yield f"[DEBUG] Found {len(local_files)} local files\n".encode('utf-8')

                dropbox_files = yield from list_dropbox_files(current_dbx_folder)
                yield f"[DEBUG] Found {len(dropbox_files)} Dropbox files\n".encode('utf-8')

                for fname, fsize in local_files.items():
                    dbx_path = f"{current_dbx_folder}/{fname}"
                    if fname not in dropbox_files or dropbox_files[fname] != fsize:
                        yield from upload_file(os.path.join(root, fname), dbx_path)
                    else:
                        yield f"Skipped (already exists with same size): {fname}\n".encode('utf-8')
        except Exception as e:
            yield f"[ERROR] Sync failed with exception: {type(e).__name__}: {e}\n".encode('utf-8')
            yield f"[ERROR] Traceback: {traceback.format_exc()}\n".encode('utf-8')

        yield f"Sync completed: {local_root} -> {dropbox_root}\n".encode('utf-8')

    for local_folder, dropbox_folder in FOLDER_PAIRS:
        if os.path.exists(local_folder):
            yield from sync_pair(local_folder, dropbox_folder)
        else:
            yield f"Warning: Local folder not found: {local_folder}\n".encode('utf-8')

    yield b"\nAll syncs completed.\n"
