from setuptools import setup

APP = ['pdf_editor.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': True,
    'packages': ['fitz', 'PIL'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)