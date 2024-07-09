# main.spec
# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Collect all necessary data files and hidden imports
datas = collect_data_files('server_api') + collect_data_files('server_pytc') + collect_data_files('pytorch_connectomics')
hiddenimports = collect_submodules('server_api') + collect_submodules('server_pytc') + collect_submodules('pytorch_connectomics')

a = Analysis(['server_api/main.py', 'server_pytc/main.py'],
             pathex=['.'],
             binaries=[],
             datas=datas,
             hiddenimports=hiddenimports,
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='pytc_backend',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True)

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='pytc_backend')
