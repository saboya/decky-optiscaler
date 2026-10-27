#!/usr/bin/env python3
"""Offline integration tests for the Deck preset's DLL/settings lifecycle."""
import asyncio
import hashlib
import json
import logging
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'py_modules'))
from optiscaler import installer, fsr4build
from optiscaler.constants import FFX_UPSCALER_PATH, INI_NAME, MANIFEST_NAME
from optiscaler.inifile import IniFile
from optiscaler.service import OptiScalerService

ROOT = Path(__file__).resolve().parents[1]


class BuildFetchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fsr4build._digests.clear()
        self.dll_bytes = b'verified community DLL'
        self.build = dict(fsr4build.find('4.1.1b'),
                          file_bytes=len(self.dll_bytes),
                          file_sha256=hashlib.sha256(self.dll_bytes).hexdigest())
        self.build['sources'] = [dict(source, archive_sha256=hashlib.sha256(
            source['repo'].encode()).hexdigest()) for source in self.build['sources']]

    def download(self, url, archive, **kwargs):
        source = next(s for s in self.build['sources'] if fsr4build.url_for(s) == url)
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(source['repo'].encode())

    def extract(self, archive, target, logger=None):
        target.mkdir(parents=True, exist_ok=True)
        (target / self.build['file']).write_bytes(self.dll_bytes)

    def test_two_files_remain_cached_and_changes_are_rehashed(self):
        paths = [self.root / name for name in ('game.dll', 'cached.dll')]
        for path in paths:
            path.write_bytes(self.dll_bytes)
        with patch.object(fsr4build.payload, 'sha256', wraps=fsr4build.payload.sha256) as sha:
            for _ in range(3):
                for path in paths:
                    fsr4build.digest(path)
            self.assertEqual(sha.call_count, 2)
            paths[0].write_bytes(b'changed DLL')
            self.assertNotEqual(fsr4build.digest(paths[0]), self.build['file_sha256'])
            self.assertEqual(sha.call_count, 3)
            for i in range(10):
                path = self.root / str(i)
                path.write_bytes(b'other DLL')
                fsr4build.digest(path)
            self.assertLessEqual(len(fsr4build._digests), 8)

    def test_identification_skips_unknown_sizes_but_checks_known_sizes(self):
        path = self.root / 'game.dll'
        path.write_bytes(b'unknown size')
        with patch.object(fsr4build, 'FSR4_BUILDS', [self.build]), \
                patch.object(fsr4build.payload, 'sha256', wraps=fsr4build.payload.sha256) as sha:
            self.assertFalse(fsr4build.identify(path)['known'])
            sha.assert_not_called()
            path.write_bytes(self.dll_bytes)
            self.assertEqual(fsr4build.identify(path)['id'], self.build['id'])
            path.write_bytes(b'x' * len(self.dll_bytes))
            self.assertFalse(fsr4build.identify(path)['known'])

    def test_primary_failure_uses_mirror_and_reuses_verified_cache(self):
        def download(url, archive, **kwargs):
            if url == fsr4build.url_for(self.build['sources'][0]):
                raise OSError('release deleted')
            self.download(url, archive, **kwargs)
        with patch.object(fsr4build.wiki, 'download', side_effect=download) as get, \
                patch.object(fsr4build.payload, 'extract_archive', side_effect=self.extract):
            path = fsr4build.fetch(self.build, self.root)
            self.assertEqual(path.read_bytes(), self.dll_bytes)
            self.assertEqual(get.call_count, 2)
            self.assertEqual(fsr4build.fetch(self.build, self.root), path)
            self.assertEqual(get.call_count, 2)

    def test_corrupt_primary_archive_falls_back(self):
        def download(url, archive, **kwargs):
            self.download(url, archive, **kwargs)
            if url == fsr4build.url_for(self.build['sources'][0]):
                archive.write_bytes(b'corrupt archive')
        with patch.object(fsr4build.wiki, 'download', side_effect=download), \
                patch.object(fsr4build.payload, 'extract_archive', side_effect=self.extract) as extract:
            self.assertEqual(fsr4build.fetch(self.build, self.root).read_bytes(), self.dll_bytes)
            self.assertEqual(extract.call_count, 1)

    def test_wrong_dll_from_either_source_is_rejected(self):
        def extract(archive, target, logger=None):
            self.extract(archive, target, logger)
            (target / self.build['file']).write_bytes(b'x' * len(self.dll_bytes))
        with patch.object(fsr4build.wiki, 'download', side_effect=self.download) as get, \
                patch.object(fsr4build.payload, 'extract_archive', side_effect=extract):
            with self.assertRaisesRegex(RuntimeError, 'DLL checksum mismatch'):
                fsr4build.fetch(self.build, self.root)
            self.assertEqual(get.call_count, 2)
            self.assertFalse(fsr4build.cached_path(self.root, self.build).exists())

    def test_failed_extraction_cannot_leave_a_dll_for_the_mirror(self):
        attempts = 0
        def extract(archive, target, logger=None):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                self.extract(archive, target, logger)
                raise RuntimeError('incomplete extraction')
            target.mkdir(parents=True, exist_ok=True)
        with patch.object(fsr4build.wiki, 'download', side_effect=self.download), \
                patch.object(fsr4build.payload, 'extract_archive', side_effect=extract):
            with self.assertRaisesRegex(RuntimeError, 'did not contain'):
                fsr4build.fetch(self.build, self.root)


class DeckFsr4Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.service = OptiScalerService(ROOT, self.root/'settings', self.root/'runtime',
                                        self.root/'home', logging.getLogger('test'))
        self.payload = asyncio.run(self.service.ensure_payload())
        self.target = self.root/'game'
        self.target.mkdir()
        (self.target/FFX_UPSCALER_PATH).parent.mkdir(exist_ok=True)
        (self.target/FFX_UPSCALER_PATH).write_bytes(b'original game DLL')
        installer.install(self.target, self.payload)
        ini = IniFile(self.target/INI_NAME)
        ini.set('FrameGen', 'FGOutput', 'fsr3')
        ini.save()
        self.dll = self.root/'community.dll'
        self.dll.write_bytes(b'test community DLL')
        self.build = dict(fsr4build.find('4.1.1b'),
                          file_sha256=hashlib.sha256(self.dll.read_bytes()).hexdigest(),
                          file_bytes=self.dll.stat().st_size)
        mock = patch.object(fsr4build, 'FSR4_BUILDS', [self.build])
        mock.start()
        self.addCleanup(mock.stop)

    def enable(self):
        with patch.object(fsr4build, 'fetch', return_value=self.dll):
            return asyncio.run(self.service.set_fsr4_build(str(self.target), '4.1.1b'))

    def snapshot(self):
        return {name: (self.target/name).read_bytes()
                for name in [FFX_UPSCALER_PATH, INI_NAME, MANIFEST_NAME]}

    def test_enable_verify_reinstall_restore_uninstall(self):
        self.assertTrue(self.enable()['ok'])
        config = asyncio.run(self.service.read_config(str(self.target)))
        self.assertEqual(config['fsr4_build'], '4.1.1b')
        self.assertEqual(config['values']['FSR']['Fsr4GpuSupport'], '2')
        self.assertEqual(config['values']['FSR']['Fsr4Model'], 'auto')
        self.assertEqual(config['values']['FSR']['UpscalerIndex'], '0')
        self.assertEqual(config['values']['FrameGen']['FGOutput'], 'fsr3')
        self.assertTrue(installer.verify_install(self.target, self.payload)['complete'])
        installer.install(self.target, self.payload)
        self.assertEqual((self.target/FFX_UPSCALER_PATH).read_bytes(), self.dll.read_bytes())
        self.assertEqual(installer.read_manifest(self.target)['fsr4_build']['id'], '4.1.1b')
        installer.restore_fsr4_build(self.target, self.payload)
        self.assertEqual(fsr4build.identify(self.target/FFX_UPSCALER_PATH)['id'], 'bundled')
        self.assertTrue(installer.verify_install(self.target, self.payload)['complete'])
        self.assertTrue(self.enable()['ok'])
        installer.uninstall(self.target)
        self.assertEqual((self.target/FFX_UPSCALER_PATH).read_bytes(), b'original game DLL')

    def test_other_registered_build_is_accepted_and_unknown_is_rejected(self):
        self.build['id'] = 'future-build'
        with patch.object(fsr4build, 'fetch', return_value=self.dll) as fetch:
            result = asyncio.run(self.service.set_fsr4_build(str(self.target), 'future-build'))
            self.assertTrue(result['ok'])
            fetch.reset_mock()
            result = asyncio.run(self.service.set_fsr4_build(str(self.target), 'unknown'))
            self.assertFalse(result['ok'])
            fetch.assert_not_called()

    def test_invalid_preset_rolls_back_settings_and_dll(self):
        before = self.snapshot()
        with patch.object(installer.schema, 'valid', return_value=False):
            self.assertFalse(self.enable()['ok'])
        self.assertEqual(before, self.snapshot())

    def test_download_failure_preserves_settings_and_dll(self):
        before = self.snapshot()
        with patch.object(fsr4build, 'fetch', side_effect=ValueError('checksum mismatch')):
            result = asyncio.run(self.service.set_fsr4_build(str(self.target), '4.1.1b'))
        self.assertFalse(result['ok'])
        self.assertEqual(before, self.snapshot())

    def test_same_size_corruption_fails_verification_and_reinstall(self):
        self.assertTrue(self.enable()['ok'])
        (self.target/FFX_UPSCALER_PATH).write_bytes(b'x'*self.build['file_bytes'])
        self.assertIn(FFX_UPSCALER_PATH, installer.verify_install(self.target, self.payload)['problems'])
        before = self.snapshot()
        with self.assertRaises(ValueError):
            installer.install(self.target, self.payload)
        self.assertEqual(before, self.snapshot())
        self.assertTrue(self.enable()['ok'])
        self.assertTrue(installer.verify_install(self.target, self.payload)['complete'])

    def test_running_game_rejected_before_download_and_after_download(self):
        before = self.snapshot()
        with patch.object(installer.live, 'status', return_value={'attached': True}), \
                patch.object(fsr4build, 'fetch') as fetch:
            result = asyncio.run(self.service.set_fsr4_build(str(self.target), '4.1.1b'))
            self.assertFalse(result['ok'])
            fetch.assert_not_called()
        with patch.object(installer.live, 'status', side_effect=[{}, {'attached': True}]):
            self.assertFalse(self.enable()['ok'])
        self.assertEqual(before, self.snapshot())

    def test_unmanaged_install_rejected(self):
        (self.target/MANIFEST_NAME).unlink()
        before = (self.target/FFX_UPSCALER_PATH).read_bytes()
        self.assertFalse(self.enable()['ok'])
        self.assertEqual(before, (self.target/FFX_UPSCALER_PATH).read_bytes())

    def test_manifest_write_failure_rolls_back_dll_and_ini(self):
        before = self.snapshot()
        real_copy = installer.atomic_copy
        def fail_once(source, destination):
            if Path(source).name == 'new.json':
                raise OSError('simulated disk failure')
            real_copy(source, destination)
        with patch.object(installer, 'atomic_copy', side_effect=fail_once):
            self.assertFalse(self.enable()['ok'])
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    logging.disable(logging.CRITICAL)
    unittest.main()


class FakeResponse:
    def __init__(self, data, status=206):
        import io
        self.stream, self.status = io.BytesIO(data), status

    def read(self, n):
        return self.stream.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class LiteFetchTests(unittest.TestCase):
    """The AMD download: recipe handling, with a tiny synthetic package."""

    def setUp(self):
        import lzma
        from optiscaler import fsr4lite
        self.fsr4lite = fsr4lite
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = bytes(range(256)) * 400
        self.junk = b'precedes the DLL ' * 50
        raw = self.junk + self.payload
        packed = lzma.compress(raw, format=lzma.FORMAT_RAW, filters=[
            {'id': lzma.FILTER_X86, 'start_offset': 0},
            {'id': lzma.FILTER_LZMA2, 'dict_size': 2**24}])
        self.packed = packed
        self.recipe = dict(
            fsr4lite.RECIPE, unpacked_offset=0, dll_offset=len(self.junk),
            dll_size=len(self.payload), sha256=hashlib.sha256(self.payload).hexdigest())

    def opener(self, data=None, status=206):
        return lambda recipe: FakeResponse(self.packed if data is None else data, status)

    def test_decodes_the_dll_after_the_skipped_bytes_and_verifies_it(self):
        dest = self.root / 'out' / 'amdxcffx64.dll'
        self.fsr4lite.fetch(dest, self.recipe, opener=self.opener())
        self.assertEqual(dest.read_bytes(), self.payload)
        self.assertTrue(self.fsr4lite.is_valid(dest, self.recipe))
        self.assertFalse(dest.with_name(dest.name + '.part').exists())

    def test_wrong_hash_leaves_nothing_behind(self):
        dest = self.root / 'amdxcffx64.dll'
        bad = dict(self.recipe, sha256='0' * 64)
        with self.assertRaises(self.fsr4lite.FetchError):
            self.fsr4lite.fetch(dest, bad, opener=self.opener())
        self.assertFalse(dest.exists())
        self.assertEqual(list(self.root.glob('*.part')), [])

    def test_a_server_that_ignores_the_range_is_refused(self):
        with self.assertRaises(self.fsr4lite.FetchError):
            self.fsr4lite.fetch(self.root / 'x.dll', self.recipe, opener=self.opener(status=200))

    def test_truncated_download_is_refused(self):
        with self.assertRaises(self.fsr4lite.FetchError):
            self.fsr4lite.fetch(self.root / 'x.dll', self.recipe,
                                opener=self.opener(self.packed[:len(self.packed) // 2]))

    def test_ensure_reuses_a_valid_cache_without_a_download(self):
        self.fsr4lite.fetch(self.fsr4lite.cached_path(self.root, self.recipe), self.recipe,
                            opener=self.opener())
        def boom(recipe):
            raise AssertionError('should not download')
        path = self.fsr4lite.ensure(self.root, self.recipe, opener=boom)
        self.assertEqual(path.read_bytes(), self.payload)


class UpgradeFromFlatLayoutTests(unittest.TestCase):
    """A 0.0.7 install, upgraded in place by this one.

    0.0.7 kept the support DLLs next to the proxy and the ASI in plugins/. The
    new manifest only lists the OptiScaler/ paths, so without a migration every
    file the old one listed would stay beside the executable -- where a stale
    FidelityFX DLL is the one the game would load -- and uninstall would never
    find it.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.game = root / 'game'
        self.game.mkdir()
        self.payload = root / 'payload'
        (self.payload / 'OptiScaler').mkdir(parents=True)
        (self.payload / 'OptiScaler.dll').write_bytes(b'OptiScaler' * 500000)
        (self.payload / 'OptiScaler.ini').write_text('[Upscalers]\n')
        for name in installer.PAYLOAD_FILES:
            (self.payload / name).write_bytes(b'new')
        self.old = ['dxgi.dll', 'OptiScaler.ini', 'amd_fidelityfx_upscaler_dx12.dll',
                    'fakenvapi.dll', 'amdxcffx64.dll', 'plugins/decky_optiscaler_live.asi']
        for name in self.old:
            path = self.game / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(b'OptiScaler' * 500000 if name == 'dxgi.dll' else b'old ' + name.encode())
        stash = self.game / 'decky_optiscaler_backup_files'
        stash.mkdir()
        (stash / 'amd_fidelityfx_upscaler_dx12.dll').write_bytes(b"THE GAME'S OWN")
        (self.game / MANIFEST_NAME).write_text(json.dumps({
            'plugin': 'decky-optiscaler', 'filename': 'dxgi.dll', 'optiscaler_version': '0.9.4',
            'files': self.old, 'dirs': [],
            'backups': {'amd_fidelityfx_upscaler_dx12.dll': 'amd_fidelityfx_upscaler_dx12.dll'},
            'backup_dir': 'decky_optiscaler_backup_files'}))

    def files(self):
        return sorted(str(p.relative_to(self.game)) for p in self.game.rglob('*') if p.is_file())

    def test_old_layout_files_are_removed_and_the_games_own_dll_comes_back(self):
        installer.install(self.game, self.payload, 'dxgi.dll')
        files = self.files()
        for stale in ('fakenvapi.dll', 'plugins/decky_optiscaler_live.asi'):
            self.assertNotIn(stale, files)
        self.assertFalse((self.game / 'plugins').exists())
        # The file 0.0.7 had put in the game's folder was OptiScaler's; the game's
        # own, which it had stashed, is back where the game expects it.
        self.assertEqual((self.game / 'amd_fidelityfx_upscaler_dx12.dll').read_bytes(),
                         b"THE GAME'S OWN")
        self.assertNotIn('decky_optiscaler_backup_files/amd_fidelityfx_upscaler_dx12.dll', files)

    def test_imported_driver_dlls_are_moved_not_lost(self):
        installer.install(self.game, self.payload, 'dxgi.dll')
        self.assertFalse((self.game / 'amdxcffx64.dll').exists())
        self.assertEqual((self.game / 'OptiScaler' / 'amdxcffx64.dll').read_bytes(),
                         b'old amdxcffx64.dll')
        self.assertIn('OptiScaler/amdxcffx64.dll', installer.read_manifest(self.game)['files'])

    def test_switching_the_proxy_name_during_an_upgrade_still_restores_the_games_dll(self):
        # The proxy is handled by install()'s own stale-proxy step; the migration
        # must not delete it first.
        (self.game / 'decky_optiscaler_backup_files' / 'dxgi.dll').write_bytes(b"GAME'S DXGI")
        manifest = installer.read_manifest(self.game)
        manifest['backups']['dxgi.dll'] = 'dxgi.dll'
        (self.game / MANIFEST_NAME).write_text(json.dumps(manifest))
        installer.install(self.game, self.payload, 'winmm.dll')
        self.assertEqual((self.game / 'dxgi.dll').read_bytes(), b"GAME'S DXGI")
        self.assertTrue((self.game / 'winmm.dll').is_file())

    def test_uninstall_after_the_upgrade_leaves_only_the_games_own_files(self):
        installer.install(self.game, self.payload, 'dxgi.dll')
        installer.uninstall(self.game)
        self.assertEqual(self.files(), ['amd_fidelityfx_upscaler_dx12.dll'])


class LiteRecipeTests(unittest.TestCase):
    def test_both_recipes_are_complete_and_distinct(self):
        from optiscaler import fsr4lite
        keys = {'id', 'api', 'driver', 'fsr', 'file', 'url', 'referer', 'packed_offset',
                'unpacked_offset', 'dll_offset', 'dll_size', 'sha256'}
        for api, recipe in fsr4lite.RECIPES.items():
            self.assertTrue(keys <= set(recipe), api)
            self.assertEqual(recipe['api'], api)
            self.assertEqual(len(recipe['sha256']), 64)
        self.assertNotEqual(fsr4lite.RECIPE['id'], fsr4lite.RECIPE_VULKAN['id'])
        self.assertNotEqual(fsr4lite.RECIPE['file'], fsr4lite.RECIPE_VULKAN['file'])
        self.assertEqual(fsr4lite.RECIPE['url'], fsr4lite.RECIPE_VULKAN['url'])
        # The cache keeps one folder per recipe, so one never overwrites the other.
        self.assertNotEqual(fsr4lite.cached_path('/c', fsr4lite.RECIPE),
                            fsr4lite.cached_path('/c', fsr4lite.RECIPE_VULKAN))


class LiteInstallTests(DeckFsr4Tests):
    """Choosing Lite: DLL, settings and manifest are one atomic unit."""

    def setUp(self):
        super().setUp()
        from optiscaler import fsr4lite
        self.fsr4lite = fsr4lite
        self.lite = self.root / 'amdxcffx64.dll'
        self.lite.write_bytes(b'stand-in for AMD DLL')
        self.lite_vk = self.root / 'amdvkffx64.dll'
        self.lite_vk.write_bytes(b'stand-in for AMD Vulkan DLL')
        self.recipe = dict(fsr4lite.RECIPE, dll_size=self.lite.stat().st_size,
                           sha256=hashlib.sha256(self.lite.read_bytes()).hexdigest())
        self.recipe_vk = dict(fsr4lite.RECIPE_VULKAN, dll_size=self.lite_vk.stat().st_size,
                              sha256=hashlib.sha256(self.lite_vk.read_bytes()).hexdigest())
        standins = {'dx12': self.lite, 'vulkan': self.lite_vk}

        def fake_ensure(cache, recipe=None, *a, **k):
            return standins[(recipe or self.recipe)['api']]

        def fake_valid(path, recipe=None):
            expected = standins[(recipe or self.recipe)['api']]
            return Path(path).is_file() and Path(path).read_bytes() == expected.read_bytes()

        for patcher in (patch.object(fsr4lite, 'RECIPE', self.recipe),
                        patch.object(fsr4lite, 'RECIPE_VULKAN', self.recipe_vk),
                        patch.object(fsr4lite, 'RECIPES', {'dx12': self.recipe, 'vulkan': self.recipe_vk}),
                        patch.object(fsr4lite, 'ensure', fake_ensure),
                        patch.object(fsr4lite, 'is_valid', fake_valid)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def enable_lite(self):
        return asyncio.run(self.service.enable_fsr4_lite(str(self.target)))

    def values(self):
        return asyncio.run(self.service.read_config(str(self.target)))['values']

    def test_enable_writes_the_dll_the_settings_and_the_manifest(self):
        self.assertTrue(self.enable_lite()['ok'])
        self.assertEqual((self.target / 'OptiScaler' / 'amdxcffx64.dll').read_bytes(),
                         self.lite.read_bytes())
        fsr = self.values()['FSR']
        self.assertEqual((fsr['Fsr4GpuSupport'], fsr['Fsr4Model'], fsr['Fsr4EnableWatermark']),
                         ('4', '3', 'true'))
        self.assertEqual(self.values()['Upscalers']['Dx12Upscaler'], 'ffx')
        manifest = installer.read_manifest(self.target)
        self.assertIn('OptiScaler/amdxcffx64.dll', manifest['files'])
        self.assertTrue(manifest['fsr4_lite'])
        self.assertTrue(installer.lite_status(self.target)['valid'])

    def test_enable_also_installs_the_vulkan_library_and_selects_ffx_for_vulkan(self):
        self.assertTrue(self.enable_lite()['ok'])
        vk = self.target / 'OptiScaler' / 'amdvkffx64.dll'
        self.assertEqual(vk.read_bytes(), self.lite_vk.read_bytes())
        upscalers = self.values()['Upscalers']
        # Native Vulkan runs the FFX backend itself (which loads amdvkffx64);
        # DX11 stays on the DX12 route.
        self.assertEqual(upscalers['VulkanUpscaler'], 'ffx')
        self.assertEqual(upscalers['Dx12Upscaler'], 'ffx')
        self.assertEqual(upscalers['Dx11Upscaler'], 'ffx_12')
        manifest = installer.read_manifest(self.target)
        self.assertIn('OptiScaler/amdvkffx64.dll', manifest['files'])
        self.assertTrue(manifest['fsr4_lite']['vulkan'])
        status = installer.lite_status(self.target)
        self.assertTrue(status['dx12']['valid'] and status['vulkan']['valid'])

    def test_dx12_only_install_leaves_vulkan_on_the_dx12_route(self):
        result = asyncio.run(self.service.enable_fsr4_lite(str(self.target), vulkan=False))
        self.assertTrue(result['ok'])
        self.assertFalse((self.target / 'OptiScaler' / 'amdvkffx64.dll').exists())
        self.assertEqual(self.values()['Upscalers']['VulkanUpscaler'], 'ffx_12')
        self.assertFalse(installer.read_manifest(self.target)['fsr4_lite']['vulkan'])

    def test_disable_removes_both_libraries(self):
        self.enable_lite()
        self.assertTrue(asyncio.run(self.service.disable_fsr4_lite(str(self.target)))['ok'])
        for name in ('amdxcffx64.dll', 'amdvkffx64.dll'):
            self.assertFalse((self.target / 'OptiScaler' / name).exists())
        self.assertFalse(any(f.endswith(('amdxcffx64.dll', 'amdvkffx64.dll'))
                             for f in installer.read_manifest(self.target)['files']))

    def test_a_vulkan_library_that_fails_verification_changes_nothing(self):
        before = {n: (self.target / n).read_bytes() for n in (INI_NAME, MANIFEST_NAME)}
        bad = self.root / 'bad-vk.dll'
        bad.write_bytes(b'not the vulkan library')
        with self.assertRaises(ValueError):
            installer.install_fsr4_lite(self.target, self.lite, None, bad)
        self.assertEqual(before, {n: (self.target / n).read_bytes() for n in (INI_NAME, MANIFEST_NAME)})
        self.assertFalse((self.target / 'OptiScaler' / 'amdxcffx64.dll').exists())

    def test_failure_after_the_first_dll_rolls_back_both(self):
        before = {n: (self.target / n).read_bytes() for n in (INI_NAME, MANIFEST_NAME)}
        # 1st atomic_copy = DX12 DLL, 2nd = Vulkan DLL fails.
        with patch.object(installer, 'atomic_copy',
                          side_effect=[None, OSError('disk full'), None, None, None]):
            self.assertFalse(self.enable_lite()['ok'])
        self.assertEqual(before, {n: (self.target / n).read_bytes() for n in (INI_NAME, MANIFEST_NAME)})

    def test_disable_removes_the_dll_and_resets_the_model_settings(self):
        self.enable_lite()
        result = asyncio.run(self.service.disable_fsr4_lite(str(self.target)))
        self.assertTrue(result['ok'])
        self.assertFalse((self.target / 'OptiScaler' / 'amdxcffx64.dll').exists())
        fsr = self.values()['FSR']
        self.assertEqual((fsr['Fsr4GpuSupport'], fsr['Fsr4Model']), ('auto', 'auto'))
        self.assertFalse(installer.read_manifest(self.target)['fsr4_lite'])

    def test_failure_rolls_everything_back(self):
        before = {n: (self.target / n).read_bytes() for n in (INI_NAME, MANIFEST_NAME)}
        with patch.object(installer, 'atomic_copy', side_effect=[None, OSError('disk full')]):
            self.assertFalse(self.enable_lite()['ok'])
        self.assertEqual(before, {n: (self.target / n).read_bytes() for n in (INI_NAME, MANIFEST_NAME)})

    def test_refuses_while_the_game_runs(self):
        with patch.object(installer.live, 'status', return_value={'attached': True}):
            self.assertFalse(self.enable_lite()['ok'])
        self.assertFalse((self.target / 'OptiScaler' / 'amdxcffx64.dll').exists())

    def test_reinstall_keeps_the_dll_on_the_manifest_and_uninstall_removes_it(self):
        self.enable_lite()
        installer.install(self.target, self.payload)
        kept = installer.read_manifest(self.target)['files']
        self.assertIn('OptiScaler/amdxcffx64.dll', kept)
        self.assertIn('OptiScaler/amdvkffx64.dll', kept)
        installer.uninstall(self.target)
        self.assertFalse((self.target / 'OptiScaler' / 'amdxcffx64.dll').exists())
        self.assertFalse((self.target / 'OptiScaler' / 'amdvkffx64.dll').exists())
        # The game's own file that setUp put there comes back, and nothing else stays.
        self.assertEqual(sorted(p.name for p in (self.target / 'OptiScaler').iterdir()),
                         ['amd_fidelityfx_upscaler_dx12.dll'])


# LiteInstallTests reuses DeckFsr4Tests' setUp; do not run its tests a second time.
for _name in dir(DeckFsr4Tests):
    if _name.startswith('test_'):
        setattr(LiteInstallTests, _name, None)
