project('softnoise', version : '1.0.0', license : 'MIT')

pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
bindir     = get_option('prefix') / get_option('bindir')

# ── Python package ──────────────────────────────────────────────────────────
install_subdir(
  'softnoise',
  install_dir : pkgdatadir,
)

# ── Launcher script ─────────────────────────────────────────────────────────
conf = configuration_data()
conf.set('PKGDATADIR', pkgdatadir)
conf.set('PYTHON',     find_program('python3').full_path())

configure_file(
  input         : 'bin/softnoise.in',
  output        : 'softnoise',
  configuration : conf,
  install       : true,
  install_dir   : bindir,
  install_mode  : 'rwxr-xr-x',
)

# ── Desktop entry ────────────────────────────────────────────────────────────
install_data(
  'data/com.softnoise.app.desktop',
  install_dir : get_option('datadir') / 'applications',
)

# ── AppStream metainfo ───────────────────────────────────────────────────────
install_data(
  'data/com.softnoise.app.metainfo.xml',
  install_dir : get_option('datadir') / 'metainfo',
)

# ── Icon ─────────────────────────────────────────────────────────────────────
install_data(
  'data/icons/scalable/apps/com.softnoise.app.svg',
  install_dir : get_option('datadir') / 'icons' / 'hicolor' / 'scalable' / 'apps',
)
