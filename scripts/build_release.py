#!/usr/bin/env python3
"""Build a complete install ZIP and an independent /covers/ static site."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
BASE=Path(__file__).resolve().parents[1]

def main():
    version=(BASE/'VERSION').read_text(encoding='utf-8').strip()
    out=BASE/'.build';out.mkdir(exist_ok=True)
    archive=out/f'minmin-cover-studio-{version}.zip'
    members=[]
    for name in ('SKILL.md','INSTALL.md','README.md','LICENSE','ASSET-LICENSE.md','CHANGELOG.md','VALIDATION.md','VERSION','requirements.txt','scripts','references','assets','tests'):
        path=BASE/name
        members.extend([path] if path.is_file() else [p for p in path.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'])
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for path in sorted(members):
            info=zipfile.ZipInfo('minmin-cover-studio/'+path.relative_to(BASE).as_posix(),date_time=(2026,10,24,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644 << 16
            z.writestr(info,path.read_bytes())
    meta={'name':'minmin-cover-studio','version':version,'download_url':f'https://tools.minmin11538.cn/covers/downloads/{archive.name}',
          'github_download_url':f'https://github.com/mingminwang962-eng/minmin-cover-studio/releases/download/v{version}/{archive.name}',
          'archive_root':'minmin-cover-studio','skill_entry':'SKILL.md','instructions_url':'https://tools.minmin11538.cn/covers/install.md',
          'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'samples':57,'minimum_python':'3.9',
          'generation':'Host image tool or own OpenAI API configuration','released_at':'2026-10-24'}
    text=json.dumps(meta,ensure_ascii=False,indent=2)+'\n'
    (BASE/'website/release.json').write_text(text,encoding='utf-8')
    site=out/'site';site.mkdir(exist_ok=True)
    shutil.copytree(BASE/'website',site,dirs_exist_ok=True)
    shutil.copytree(BASE/'assets',site/'assets',dirs_exist_ok=True)
    shutil.copyfile(BASE/'ASSET-LICENSE.md',site/'ASSET-LICENSE.md')
    (site/'downloads').mkdir(exist_ok=True)
    shutil.copyfile(archive,site/'downloads'/archive.name)
    (site/'downloads/SHA256SUMS').write_text(meta['sha256']+'  '+archive.name+'\n',encoding='utf-8')
    home=(site/'index.html').read_text(encoding='utf-8').replace('__PACKAGE_MB__',str(round(meta['bytes']/1024/1024)))
    (site/'index.html').write_text(home,encoding='utf-8')
    print(text)

if __name__=='__main__':main()
