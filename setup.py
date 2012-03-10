# To build:
# python setup.py py2exe --includes sip

from distutils.core import setup
import py2exe

setup(
    # The first three parameters are not required, if at least a
    # 'version' is given, then a versioninfo resource is built from
    # them and added to the executables.
    version = "0.0.1",
    description = "TestSuite",
    name = "TestSuite",
    #ascii = True,
    options = {
        'py2exe': {
            'includes': [
                'sip',
                ],
            'excludes': [
                "pywin",
                "pywin.debugger",
                "pywin.debugger.dbgcon",
                "pywin.dialogs",
                "pywin.dialogs.list",
                "Tkconstants",
                "Tkinter",
                "tcl",
                'pyreadline',
                'difflib',
                'doctest',
                'locale',
                'optparse',
                'pickle',
                'calendar',
                '_ssl',
                'email',
                'ctypes',
                'pydoc_topics',
                'pydoc',
                #'urllib',
                'inspect',
                #'httplib',
                'subprocess',
                #'rfc822',
                'ftplib',


                ]
            }
        },

    # targets to build
    windows = ["gui.py"],
    )
