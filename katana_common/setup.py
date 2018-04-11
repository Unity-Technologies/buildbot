from distutils.core import setup


setup_args = {
    'name': "katana_common",
    'version': '1.0.0',
    'description': "Katana log tools",
    'long_description': "Katana log tools",
    'package_dir': {'klog': 'klog'},
    'packages': ["klog"],
    # This makes it include all files from MANIFEST.in
    # It also needs a newer version of setuptools than 17.1
    # which has a bug when dealing with MANIFEST.in
    'include_package_data': True,
    'install_requires': ['setuptools >= 21.1.0']
}

setup(**setup_args)
