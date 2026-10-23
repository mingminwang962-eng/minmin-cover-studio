import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote
from html.parser import HTMLParser

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE/'scripts'))
import asset_library as lib
import generate_openai as api
from PIL import Image

class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.a = self.root/'内容 A'; self.a.mkdir()
        self.b = self.root/'内容 B'; self.b.mkdir()
        self.photo = self.root/'原照片.png'
        Image.new('RGB',(24,32),'red').save(self.photo)
        self.config = self.root/'config.json'
        self.config.write_text(json.dumps({'title':'自己的节奏','title_lines':['自己','的节奏'], 'topic':'生活有自己的节奏','focus_terms':['节奏'], 'reference_path':str(self.photo),'reference_asset_id':'original','output_dir':'unused','styles':[{'id':'wall-27','scene':'Use the original person and environment with large Chinese lettering.'}]}),encoding='utf-8')
    def tearDown(self): self.temp.cleanup()
    def call(self,folder,*args,success=True):
        result=subprocess.run([sys.executable,str(BASE/'scripts/asset_library.py'),'--content-dir',str(folder),*map(str,args)],capture_output=True,text=True,encoding='utf-8',cwd=self.root)
        self.assertEqual(result.returncode==0,success,result.stderr)
        return json.loads(result.stdout) if success else result.stderr
    def prepare(self,folder=None):return Path(self.call(folder or self.a,'prepare',self.config)['run'])
    def test_auto_init_and_dedup(self):
        row=self.call(self.a,'photos',self.photo)[0]
        self.assertEqual(Path(row['path']).read_bytes(),self.photo.read_bytes())
        self.assertEqual(row,self.call(self.a,'photos',self.photo)[0])
        self.assertEqual(self.call(self.a,'status')['photos'],1)
    def test_invalid_image_rejected(self):
        f=self.root/'broken.png';f.write_bytes(b'bad')
        self.call(self.a,'photos',f,success=False)
        self.assertEqual(self.call(self.a,'status')['photos'],0)
    def test_status_does_not_create(self):
        self.call(self.a,'status',success=False)
        self.assertFalse((self.a/'我的封面工作室').exists())
    def test_isolation_and_missing_library(self):
        run=self.prepare();self.prepare(self.b)
        self.call(self.b,'sync',run,success=False)
        store=self.a/'我的封面工作室';store.rename(self.a/'removed')
        self.call(self.a,'photos',self.photo,success=False)
        self.assertFalse(store.exists())
    def test_new_runs_and_no_overwrite(self):
        run=self.prepare();other=self.prepare();self.assertNotEqual(run,other)
        self.call(self.a,'save-cover',run,'wall-27',self.photo)
        different=self.root/'blue.png';Image.new('RGB',(24,32),'blue').save(different)
        self.call(self.a,'save-cover',run,'wall-27',different,success=False)
        self.assertEqual((run/'候选/wall-27.png').read_bytes(),self.photo.read_bytes())
    def test_selected_persists_and_links_work(self):
        run=self.prepare();self.call(self.a,'save-cover',run,'wall-27',self.photo)
        store=self.a/'我的封面工作室'
        row=lib.read(store/'封面索引.json')[0]
        self.call(self.a,'select',row['id']);self.call(self.a,'sync',run)
        self.assertEqual(self.call(self.a,'status')['covers'],1)
        self.assertTrue(lib.read(store/'封面索引.json')[0]['selected'])
        class Parser(HTMLParser):
            links=[]
            def handle_starttag(self,tag,attrs):
                for k,v in attrs:
                    if k in ('src','href'):self.links.append(v)
        for file in (store/'我的封面墙.html',store/'照片集/照片墙.html'):
            parser=Parser();parser.links=[];parser.feed(file.read_text(encoding='utf-8'))
            for link in parser.links:self.assertTrue((file.parent/unquote(link)).is_file(),link)
    def test_concurrent_uploads(self):
        self.call(self.a,'photos',self.photo)
        cmd=[sys.executable,str(BASE/'scripts/asset_library.py'),'--content-dir',str(self.a),'photos',str(self.photo)]
        ps=[subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(3)]
        for p in ps:
            stdout,stderr=p.communicate(timeout=30);self.assertEqual(p.returncode,0,stderr)
        self.assertEqual(self.call(self.a,'status')['photos'],1)
    def test_prompt_tampering_does_not_generate(self):
        run=self.prepare();(run/'prompts/wall-27.txt').write_text('modified',encoding='utf-8')
        with self.assertRaises(ValueError):api.make_payload(run,'wall-27','gpt-image-2')
    def test_api_payload_and_archival(self):
        run=self.prepare();captured=[]
        def fake(request,timeout):
            captured.append(json.loads(request.data))
            return io.BytesIO(json.dumps({'data':[{'b64_json':base64.b64encode(self.photo.read_bytes()).decode()}],'usage':{'total_tokens':1}}).encode())
        with lib.locked(run.parent.parent):
            api.generate(run,'wall-27','gpt-image-2','test-not-real',opener=fake)
        self.assertEqual(captured[0]['size'],'1536x2048')
        self.assertTrue(captured[0]['images'][0]['image_url'].startswith('data:image/png;base64,'))
        self.assertEqual(self.call(self.a,'status')['covers'],1)
        with self.assertRaises(FileExistsError):api.make_payload(run,'wall-27','gpt-image-2')
    def test_api_empty_response_not_success(self):
        run=self.prepare()
        with self.assertRaises(ValueError):api.generate(run,'wall-27','gpt-image-2','test',opener=lambda *a,**kw:io.BytesIO(b'{}'))
        self.assertEqual(self.call(self.a,'status')['covers'],0)
    def test_failed_archive_keeps_received_image(self):
        run=self.prepare()
        response=lambda *a,**kw:io.BytesIO(json.dumps({'data':[{'b64_json':base64.b64encode(self.photo.read_bytes()).decode()}]}).encode())
        with patch.object(api,'save_cover',side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):api.generate(run,'wall-27','gpt-image-2','test',opener=response)
        self.assertEqual(len(list(run.glob('received-*.png'))),1)
    def test_legacy_console_encoding(self):
        result=subprocess.run([sys.executable,str(BASE/'scripts/doctor.py')],capture_output=True,
                              env={**os.environ,'PYTHONIOENCODING':'cp1252'})
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout.decode('utf-8'))['samples'],57)
    def test_written_prompt_matches_hash(self):
        import hashlib
        run=self.prepare()
        candidate=lib.read(run/'plan.json')['candidates'][0]
        self.assertEqual(hashlib.sha256((run/candidate['prompt_file']).read_bytes()).hexdigest(),candidate['prompt_sha256'])
    def test_portable_catalog(self):
        catalog=lib.read(BASE/'references/style-catalog.json')
        self.assertEqual(len(catalog),57)
        for row in catalog:
            self.assertFalse(Path(row['preview']).is_absolute())
            self.assertTrue((BASE/row['preview']).is_file())
        for folder in ('references','scripts'):
            for path in (BASE/folder).glob('*'):
                if path.is_file():self.assertNotIn('/Users/',path.read_text(encoding='utf-8'),str(path))

if __name__=='__main__':unittest.main()
