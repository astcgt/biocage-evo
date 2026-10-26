"""Repository paths and external tools (config.json at the repo root)."""
import os, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, 'config.json')))
FEBIO, MKL = CFG['febio_bin'], CFG['mkl_lib']
SNAP = os.path.join(ROOT, 'snapshot')
RESULTS = os.path.join(ROOT, 'results')
