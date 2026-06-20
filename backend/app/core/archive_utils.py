import os
import io
import copy
import shutil
import html as _html

def replace_links_in_archive(archive_path: str, replacements: list) -> int:
    by_file = {}
    for r in replacements:
        ap = r["archive_path"]
        if ap not in by_file:
            by_file[ap] = []
        by_file[ap].append(r)
        
    temp_out = archive_path + ".tmp"
    processed = 0
    
    if archive_path.lower().endswith('.zip'):
        import zipfile
        with zipfile.ZipFile(archive_path, 'r') as zip_in, \
             zipfile.ZipFile(temp_out, 'w', zipfile.ZIP_DEFLATED) as zip_out:
            for info in zip_in.infolist():
                data = zip_in.read(info.filename)
                if info.filename in by_file:
                    try:
                        content = data.decode('utf-8', errors='replace')
                        modified = False
                        for r in by_file[info.filename]:
                            old_url = r["url"]
                            new_url = r["suggested_url"]
                            if old_url in content:
                                content = content.replace(old_url, new_url)
                                modified = True
                            old_url_esc = _html.escape(old_url)
                            new_url_esc = _html.escape(new_url)
                            if old_url_esc in content:
                                content = content.replace(old_url_esc, new_url_esc)
                                modified = True
                        if modified:
                            data = content.encode('utf-8')
                            processed += 1
                    except Exception as e:
                        print(f"Error replacing in {info.filename}: {e}")
                zip_out.writestr(info, data)
    else:
        import tarfile
        with tarfile.open(archive_path, 'r:gz') as tar_in:
            with tarfile.open(temp_out, 'w:gz', format=tar_in.format) as tar_out:
                for member in tar_in:
                    if not member.isfile():
                        tar_out.addfile(member)
                        continue
                    
                    fh = tar_in.extractfile(member)
                    if fh is None:
                        tar_out.addfile(member)
                        continue
                        
                    original_bytes = fh.read()
                    
                    if member.name in by_file:
                        try:
                            content = original_bytes.decode('utf-8', errors='replace')
                            modified = False
                            for r in by_file[member.name]:
                                old_url = r["url"]
                                new_url = r["suggested_url"]
                                if old_url in content:
                                    content = content.replace(old_url, new_url)
                                    modified = True
                                old_url_esc = _html.escape(old_url)
                                new_url_esc = _html.escape(new_url)
                                if old_url_esc in content:
                                    content = content.replace(old_url_esc, new_url_esc)
                                    modified = True
                            if modified:
                                new_bytes = content.encode('utf-8')
                                new_info = copy.copy(member)
                                new_info.size = len(new_bytes)
                                tar_out.addfile(new_info, io.BytesIO(new_bytes))
                                processed += 1
                            else:
                                tar_out.addfile(member, io.BytesIO(original_bytes))
                        except Exception as e:
                            print(f"Error replacing in {member.name}: {e}")
                            tar_out.addfile(member, io.BytesIO(original_bytes))
                    else:
                        tar_out.addfile(member, io.BytesIO(original_bytes))
                        
    if os.path.exists(temp_out):
        shutil.move(temp_out, archive_path)
    return processed
