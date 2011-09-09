import os
import subprocess
import posixpath

from django.conf import settings
from django.contrib.staticfiles import finders

import jinja2
from jingo import register, env


try:
    from build import BUILD_ID_CSS, BUILD_ID_JS, BUILD_ID_IMG, BUNDLE_HASHES
except ImportError:
    BUILD_ID_CSS = BUILD_ID_JS = BUILD_ID_IMG = 'dev'
    BUNDLE_HASHES = {}


def path(*a):
    return finders.find(posixpath.normpath(os.path.join(*a))) or \
           os.path.join(settings.STATIC_ROOT, *a)

def _build_html(items, wrapping):
    """
    Wrap `items` in wrapping.
    """
    return jinja2.Markup("\n".join((wrapping % (settings.STATIC_URL + item)
                                   for item in items)))

@register.function
def js(bundle, debug=settings.TEMPLATE_DEBUG):
    """
    If we are in debug mode, just output a single script tag for each js file.
    If we are not in debug mode, return a script that points at bundle-min.js.
    """
    if debug:
        items = settings.MINIFY_BUNDLES['js'][bundle]
    else:
        build_id = BUILD_ID_JS
        bundle_full = "js:%s" % bundle
        if bundle_full in BUNDLE_HASHES:
            build_id = BUNDLE_HASHES[bundle_full]
        items = ("js/%s-min.js?build=%s" % (bundle, build_id,),)

    return _build_html(items, """<script src="%s"></script>""")


@register.function
def css(bundle, media="screen,projection,tv", debug=settings.TEMPLATE_DEBUG):
    """
    If we are in debug mode, just output a single script tag for each css file.
    If we are not in debug mode, return a script that points at bundle-min.css.
    """
    if debug:
        items = []
        for item in settings.MINIFY_BUNDLES['css'][bundle]:
            if (item.endswith('.less') and
                getattr(settings, 'LESS_PREPROCESS', False)):
                build_less(item)
                items.append('%s.css' % item)
            else:
                items.append(item)
    else:
        build_id = BUILD_ID_CSS
        bundle_full = "css:%s" % bundle
        if bundle_full in BUNDLE_HASHES:
            build_id = BUNDLE_HASHES[bundle_full]

        items = ("css/%s-min.css?build=%s" % (bundle, build_id,),)

    return _build_html(items,
            """<link rel="stylesheet" media="%s" href="%%s" />""" % media)

def build_less(item):
    path_less = path(item)
    path_css = '%s.css' % path_less

    updated_less = os.path.getmtime(path(item))
    updated_css = 0  # If the file doesn't exist, force a refresh.
    if os.path.exists(path_css):
        updated_css = os.path.getmtime(path_css)

    # Is the uncompiled version newer?  Then recompile!
    if True or updated_less > updated_css:
        with open(path_css, 'w') as output:
            less_dirs = []
            for finder in finders.get_finders():
                for rel_path, storage in finder.list(''):
                    if rel_path.endswith('.less'):
                        abs_path = storage.path(rel_path)
                        # Compute relative path of less_dir due to lessc
                        # peculiarity
                        common_prefix = os.path.commonprefix([abs_path,
                                                              path_less])
                        base_dir = os.path.dirname(common_prefix)
                        less_dir = os.path.relpath(os.path.dirname(abs_path),
                                                   base_dir)
                        if not less_dir in less_dirs:
                            less_dirs.append(less_dir)
            subprocess.Popen([settings.LESS_BIN,
                              '--include-path=%s' % ':'.join(less_dirs),
                              path_less],
                             stdout=output)

def build_ids(request):
    """A context processor for injecting the css/js build ids."""
    return {'BUILD_ID_CSS': BUILD_ID_CSS, 'BUILD_ID_JS': BUILD_ID_JS,
            'BUILD_ID_IMG': BUILD_ID_IMG}
