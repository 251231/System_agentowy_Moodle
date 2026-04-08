"""
Diagnostic: Examine the actual .mbz archive structure and identify issues.
Run: py diagnose_mbz.py <path_to.mbz>
"""
import sys, tarfile, zipfile, re
from pathlib import Path

def check_xml_valid(content: str, name: str):
    """Check if content is valid XML."""
    issues = []
    # Check for unescaped HTML inside non-CDATA tags
    # Find content tags and verify their content is properly wrapped
    for tag in ['content', 'intro', 'summary', 'description', 'text']:
        pattern = rf'<{tag}(?:[^>]*)>(.*?)</{tag}>'
        for m in re.finditer(pattern, content, re.DOTALL):
            inner = m.group(1)
            # Bad: has HTML tags but no CDATA wrapper
            if '<' in inner and '<![CDATA[' not in inner and '{mlang' in inner:
                issues.append(f"  [!] <{tag}> has HTML+mlang but NO CDATA wrapper - INVALID XML!")
            elif '<' in inner and '<![CDATA[' not in inner:
                pass  # might be ok if Moodle uses lenient parser
    return issues

def check_mbz(mbz_path):
    print(f"Analyzing: {mbz_path}\n{'='*60}")
    
    members = []
    if mbz_path.endswith('.zip'):
        with zipfile.ZipFile(mbz_path, 'r') as z:
            members = z.namelist()
            print(f"ZIP archive, {len(members)} entries")
            for name in members[:5]:
                print(f"  {name}")
    else:
        with tarfile.open(mbz_path, 'r:gz') as t:
            all_members = t.getmembers()
            members = [m.name for m in all_members]
            print(f"TAR.GZ archive, {len(members)} entries")
            print(f"First 5 entries:")
            for m in all_members[:5]:
                print(f"  type={m.type} mode={oct(m.mode)} mtime={m.mtime} name={m.name}")
            
            print(f"\nChecking moodle_backup.xml position:")
            for i, m in enumerate(all_members):
                if 'moodle_backup.xml' in m.name:
                    print(f"  Index {i}: {m.name}")
            
            print(f"\nChecking XML file validity (content tags):")
            for m in all_members:
                if not m.isfile() or not m.name.endswith('.xml'):
                    continue
                if m.name.split('/')[-1] in {'moodle_backup.xml', 'inforef.xml', 'roles.xml', 'gradebook.xml'}:
                    continue
                f = t.extractfile(m)
                if not f:
                    continue
                try:
                    content = f.read().decode('utf-8', errors='replace')
                    issues = check_xml_valid(content, m.name)
                    if issues:
                        print(f"\n  FILE: {m.name}")
                        for iss in issues:
                            print(iss)
                        # Show problematic snippet
                        for tag in ['content', 'intro']:
                            pat = rf'<{tag}(?:[^>]*)>(.*?)</{tag}>'
                            mx = re.search(pat, content, re.DOTALL)
                            if mx:
                                inner = mx.group(1)
                                print(f"  <{tag}> inner (first 100 chars): {inner[:100]!r}")
                except Exception as e:
                    print(f"  Error reading {m.name}: {e}")
    
    print(f"\nDone.")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: py diagnose_mbz.py <file.mbz>")
    else:
        check_mbz(sys.argv[1])
