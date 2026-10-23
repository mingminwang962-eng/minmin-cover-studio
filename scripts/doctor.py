#!/usr/bin/env python3
"""Check the installed package without network requests or image generation."""
import hashlib
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

def main():
    from console_utf8 import configure_output
    configure_output()
    if sys.version_info < (3, 9):
        raise RuntimeError('需要 Python 3.9 或以上版本。')
    import PIL
    from PIL import Image
    catalog = json.loads((BASE / 'references/style-catalog.json').read_text(encoding='utf-8'))
    provenance = json.loads((BASE / 'assets/provenance.json').read_text(encoding='utf-8'))
    expected = {x['file']: x['sha256'] for x in provenance}
    for sample in catalog:
        path = BASE / sample['preview']
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected[sample['preview']]:
            raise ValueError('样例校验失败：' + sample['id'])
        with Image.open(path) as image:
            image.verify()
    assert (BASE / 'assets/style-wall/index.html').is_file(), '缺少风格页'
    print(json.dumps({'status':'ready', 'version':(BASE/'VERSION').read_text(encoding='utf-8').strip(),
                      'python':sys.version.split()[0], 'pillow':PIL.__version__, 'samples':len(catalog),
                      'style_wall':str(BASE/'assets/style-wall/index.html'),
                      'generation':'由 Agent 检查当前生图工具或用户自己的 OpenAI API 配置；此检查不发起生图。'}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, AssertionError, ImportError, RuntimeError) as exc:
        sys.exit('环境检查未通过：' + str(exc))
