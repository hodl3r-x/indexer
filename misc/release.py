#!/usr/bin/env python3
#
# usage:
# python3 -m venv ve3
# ve3/bin/pip install markdown2
# ve3/bin/python misc/release.py

import io
import logging
import os
import subprocess
import tarfile
import time

import markdown2

logger = logging.getLogger(__name__)

#GOOS GOARCH DEB_HOST_ARCH
osArchArch = [
    ('linux', 'amd64', 'amd64'),
    ('linux', 'arm', 'armhf'),
    ('linux', 'arm64', 'arm64'),
    ('darwin', 'amd64', None),
]

filespec = [
    # [files], source path, deb path, tar path
    [
        ['algorand-indexer.service', 'algorand-indexer@.service'],
        'misc/systemd',
        'lib/systemd/system',
        '',
    ],
    [
        ['algorand-indexer'],
        'cmd/algorand-indexer',
        'usr/bin',
        '',
    ],
    [
        ['LICENSE'],
        '',
        None,
        '',
    ],
]

debian_copyright_top = (
'''Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: Algorand Indexer
Upstream-Contact: Algorand developers <dev@algorand.com>
Source: https://github.com/algorand/indexer

Files: *
Copyright: Algorand developers <dev@algorand.com>
License: MIT
''')

def debian_copyright(outpath):
    with open(outpath, 'wt') as fout:
        fout.write(debian_copyright_top)
        with open('LICENSE') as fin:
            for line in fin:
                line = line.strip()
                if not line:
                    line = ' .\n'
                else:
                    line = ' ' + line + '\n'
                fout.write(line)

def arch_ver(outpath, inpath, debarch, version):
    with open(outpath, 'wt') as fout:
        with open(inpath) as fin:
            for line in fin:
                line = line.replace('@ARCH@', debarch)
                line = line.replace('@VER@', version)
                fout.write(line)

def link(sourcepath, destpath):
    if os.path.exists(destpath):
        if (os.path.getmtime(destpath) >= os.path.getmtime(sourcepath)):
            return # nothing to do
        os.remove(destpath)
    os.link(sourcepath, destpath)

def compile(goos=None, goarch=None):
    env = dict(os.environ)
    env['CGO_ENABLED'] = '0'
    if goos is not None:
        env['GOOS'] = goos
    if goarch is not None:
        env['GOARCH'] = goarch
    subprocess.run(['go', 'build'], cwd='cmd/algorand-indexer', env=env).check_returncode()

def build_deb(debarch, version):
    os.makedirs('.deb_tmp/DEBIAN', exist_ok=True)
    debian_copyright('.deb_tmp/DEBIAN/copyright')
    arch_ver('.deb_tmp/DEBIAN/control', 'misc/debian/control', debarch, version)
    for files, source_path, deb_path, _ in filespec:
        if deb_path is None:
            continue
        for fname in files:
            if deb_path:
                os.makedirs(deb_path, exist_ok=True)
            link(os.path.join(source_path, fname), os.path.join(deb_path, fname))
    debname = 'algorand-indexer_{}_{}.deb'.format(version, debarch)
    subprocess.run(
        ['dpkg-deb', '--build', '.deb_tmp', debname])
    return debname

_usage_html = None
def usage_html():
    global _usage_html
    if _usage_html is not None:
        return _usage_html
    md = open('usage.md').read()
    _usage_html = markdown2.markdown(md, extras=["tables", "fenced-code-blocks"])
    return _usage_html

def build_tar(goos, goarch, version):
    rootdir = 'algorand-indexer_{}_{}_{}'.format(goos, goarch, version)
    tarname = rootdir + '.tar.bz2'
    tf = tarfile.open(tarname, 'w:bz2')
    for files, source_path, _, tar_path in filespec:
        if tar_path is None:
            continue
        for fname in files:
            if tar_path:
                os.makedirs(tar_path, exist_ok=True)
            tf.add(os.path.join(source_path, fname), os.path.join(rootdir, tar_path, fname))
    ti = tarfile.TarInfo("usage.html")
    ti.mtime = time.time()
    ti.mode = 0o444
    ti.type = tarfile.REGTYPE
    uhtml = usage_html().encode('utf-8')
    ti.size=len(uhtml)
    tf.addfile(ti, io.BytesIO(uhtml))
    tf.close()
    return tarname

def main():
    logging.basicConfig(level=logging.INFO)
    with open('.version') as fin:
        version = fin.read().strip()
    for goos, goarch, debarch in osArchArch:
        logger.info('GOOS=%s GOARCH=%s DEB_HOST_ARCH=%s', goos, goarch, debarch)
        compile(goos, goarch)
        tarname = build_tar(goos, goarch, version)
        logger.info('\t%s', tarname)
        if debarch is not None:
            debname = build_deb(debarch, version)
            logger.info('\t%s', debname)
    return

if __name__ == '__main__':
    main()
