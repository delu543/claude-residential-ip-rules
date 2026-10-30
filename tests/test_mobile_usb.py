import asyncio
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, AsyncMock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import mobile_usb as usb


class Documents:
    def __init__(self):self.files={};self.writes=[];self.corrupt=False
    async def stat(self,path):
        if path=='/Documents':return {'st_ifmt':'S_IFDIR'}
        return {'st_ifmt':'S_IFREG','st_size':len(self.files[path])}
    async def listdir(self,path):return [Path(x).name for x in self.files]
    async def get_file_contents(self,path):return b'bad' if self.corrupt else self.files[path]
    async def set_file_contents(self,path,data):self.files[path]=data;self.writes.append(path)


class USBTests(unittest.TestCase):
    def test_usb_only_and_ambiguous_selection(self):
        ds=[SimpleNamespace(serial='a',is_usb=True),SimpleNamespace(serial='b',is_usb=False)]
        self.assertEqual(usb.select_device(ds).serial,'a')
        ds.append(SimpleNamespace(serial='c',is_usb=True))
        with self.assertRaises(ValueError):usb.select_device(ds)
        self.assertEqual(usb.select_device(ds,usb.fingerprint('c')).serial,'c')
        with self.assertRaises(ValueError):usb.select_device(ds,usb.fingerprint('b'))

    def test_traversal_and_non_documents_refused(self):
        for name in ['../Library/secret.json','/private/secret.conf','a/../../a.conf','a\\x.json','a//x.conf','a.key','a\nx.conf']:
            with self.subTest(name=name),self.assertRaises(ValueError):usb.document_path(name)
        self.assertEqual(usb.document_path('exports/config.conf'),'/Documents/exports/config.conf')

    def test_refuse_symlink_and_large_document(self):
        d=Documents()
        async def bad(path):return {'st_ifmt':'S_IFLNK','st_size':1}
        d.stat=bad
        with self.assertRaises(ValueError):asyncio.run(usb.checked_read(d,'file.conf'))
        with self.assertRaises(ValueError):asyncio.run(usb.checked_read(d,'dir/file.conf'))
        async def large(path):return {'st_ifmt':'S_IFREG','st_size':usb.LIMIT+1}
        d.stat=large
        with self.assertRaises(ValueError):asyncio.run(usb.checked_read(d,'file.conf'))

    def trial(self, corrupt=False, version='2.2.93'):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t)/'.private';base.mkdir()
            settings=base/'settings.json';settings.write_text(json.dumps({'iosVersion':'26.1','shadowrocketVersion':'2.2.93 (3488)'}))
            (base/'shadowrocket.conf').write_text('private fixture')
            d=Documents();d.corrupt=corrupt
            target={'device':'fake-fingerprint','iosVersion':'26.1','shadowrocketVersion':version,'shadowrocketBuild':'3488'}
            with patch.object(usb.mobile,'check',return_value={'offlineIntegrity':'pass'}):
                if corrupt or version!='2.2.93':
                    with self.assertRaises(ValueError):asyncio.run(usb.stage(d,settings,base,target))
                    self.assertEqual(len(d.writes),1 if corrupt else 0)
                    self.assertFalse((base/'usb-readback.json').exists())
                else:
                    r=asyncio.run(usb.stage(d,settings,base,target))
                    self.assertEqual(r['status'],'transferred-readback-matched')
                    self.assertFalse(r['activated']);self.assertFalse(r['networkVerified'])
                    self.assertEqual(len(d.writes),1)
                    with self.assertRaises(ValueError):asyncio.run(usb.stage(d,settings,base,target))
                    self.assertEqual(len(d.writes),1)
    def test_transfer_readback_and_no_repeat(self):self.trial()
    def test_partial_failure_retains_intent_not_success(self):self.trial(corrupt=True)
    def test_version_drift_stops_before_write(self):self.trial(version='2.2.94')

    def test_no_container_fallback_when_app_denies_sharing(self):
        device=SimpleNamespace(serial='private-serial',is_usb=True)
        mux=SimpleNamespace(list_devices=AsyncMock(return_value=[device]))
        lockdown=SimpleNamespace(all_values={'DeviceClass':'iPhone','ProductVersion':'26.1'},close=AsyncMock())
        connect=AsyncMock(return_value=lockdown)
        installation=AsyncMock()
        installation.get_apps.return_value={usb.BUNDLE:{'CFBundleShortVersionString':'2.2.93','CFBundleVersion':'3488','UIFileSharingEnabled':False}}
        ctx=AsyncMock();ctx.__aenter__.return_value=installation
        House=SimpleNamespace(create=AsyncMock())
        a=SimpleNamespace(action='probe',device=None)
        with patch.object(usb,'load_backend',return_value=(mux,connect,lambda **kw:ctx,House)):
            result=asyncio.run(usb.run(a))
        self.assertEqual(result['status'],'file-sharing-unavailable')
        self.assertNotIn('private-serial',json.dumps(result))
        self.assertEqual(connect.call_args.kwargs['connection_type'],'USB')
        self.assertFalse(connect.call_args.kwargs['autopair'])
        House.create.assert_not_called()
        installation.get_apps.assert_called_once_with(bundle_identifiers=[usb.BUNDLE])
        lockdown.close.assert_awaited_once()


if __name__=='__main__':unittest.main()
