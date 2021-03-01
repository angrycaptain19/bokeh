#-----------------------------------------------------------------------------
# Copyright (c) 2012 - 2021, Anaconda, Inc., and Bokeh Contributors.
# All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
#-----------------------------------------------------------------------------
'''

'''

#-----------------------------------------------------------------------------
# Boilerplate
#-----------------------------------------------------------------------------
import logging # isort:skip
log = logging.getLogger(__name__)

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

# Standard library imports
import io
import os
import warnings
from os.path import abspath
from tempfile import mkstemp
from typing import TYPE_CHECKING, Any, List, Optional, Tuple, Union, cast

# External imports
from PIL import Image

# Bokeh imports
from ..document import Document
from ..embed import file_html
from ..models.layouts import LayoutDOM
from ..resources import INLINE, Resources
from .util import default_filename

#-----------------------------------------------------------------------------
# Globals and constants
#-----------------------------------------------------------------------------

__all__ = (
    'export_png',
    'export_svg',
    'export_svgs',
    'get_layout_html',
    'get_screenshot_as_png',
    'get_svgs',
)

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver

#-----------------------------------------------------------------------------
# General API
#-----------------------------------------------------------------------------

def export_png(obj: Union[LayoutDOM, Document], *, filename: Optional[str] = None, width: Optional[int] = None,
        height: Optional[int] = None, webdriver: "Optional[WebDriver]" = None, timeout: int = 5) -> str:
    ''' Export the ``LayoutDOM`` object or document as a PNG.

    If the filename is not given, it is derived from the script name (e.g.
    ``/foo/myplot.py`` will create ``/foo/myplot.png``)

    Args:
        obj (LayoutDOM or Document) : a Layout (Row/Column), Plot or Widget
            object or Document to export.

        filename (str, optional) : filename to save document under (default: None)
            If None, infer from the filename.

        width (int) : the desired width of the exported layout obj only if
            it's a Plot instance. Otherwise the width kwarg is ignored.

        height (int) : the desired height of the exported layout obj only if
            it's a Plot instance. Otherwise the height kwarg is ignored.

        webdriver (selenium.webdriver) : a selenium webdriver instance to use
            to export the image.

        timeout (int) : the maximum amount of time (in seconds) to wait for
            Bokeh to initialize (default: 5) (Added in 1.1.1).

    Returns:
        filename (str) : the filename where the static file is saved.

    If you would like to access an Image object directly, rather than save a
    file to disk, use the lower-level :func:`~bokeh.io.export.get_screenshot_as_png`
    function.

    .. warning::
        Responsive sizing_modes may generate layouts with unexpected size and
        aspect ratios. It is recommended to use the default ``fixed`` sizing mode.

    '''

    image = get_screenshot_as_png(obj, width=width, height=height, driver=webdriver, timeout=timeout)

    if filename is None:
        filename = default_filename("png")

    if image.width == 0 or image.height == 0:
        raise ValueError("unable to save an empty image")

    image.save(filename)

    return abspath(filename)

def export_svg(obj: Union[LayoutDOM, Document], *, filename: Optional[str] = None, width: Optional[int] = None,
        height: Optional[int] = None, webdriver: "Optional[WebDriver]" = None, timeout: int = 5) -> List[str]:
    ''' Export a layout as SVG file or a document as a set of SVG files.

    If the filename is not given, it is derived from the script name
    (e.g. ``/foo/myplot.py`` will create ``/foo/myplot.svg``)

    Args:
        obj (LayoutDOM object) : a Layout (Row/Column), Plot or Widget object to display

        filename (str, optional) : filename to save document under (default: None)
            If None, infer from the filename.

        width (int) : the desired width of the exported layout obj only if
            it's a Plot instance. Otherwise the width kwarg is ignored.

        height (int) : the desired height of the exported layout obj only if
            it's a Plot instance. Otherwise the height kwarg is ignored.

        webdriver (selenium.webdriver) : a selenium webdriver instance to use
            to export the image.

        timeout (int) : the maximum amount of time (in seconds) to wait for
            Bokeh to initialize (default: 5)

    Returns:
        filenames (list(str)) : the list of filenames where the SVGs files are saved.

    .. warning::
        Responsive sizing_modes may generate layouts with unexpected size and
        aspect ratios. It is recommended to use the default ``fixed`` sizing mode.

    '''
    svgs = get_svg(obj, width=width, height=height, driver=webdriver, timeout=timeout)
    return _write_collection(svgs, filename, "svg")

def export_svgs(obj: Union[LayoutDOM, Document], *, filename: Optional[str] = None, width: Optional[int] = None,
        height: Optional[int] = None, webdriver: "Optional[WebDriver]" = None, timeout: int = 5) -> List[str]:
    ''' Export the SVG-enabled plots within a layout. Each plot will result
    in a distinct SVG file.

    If the filename is not given, it is derived from the script name
    (e.g. ``/foo/myplot.py`` will create ``/foo/myplot.svg``)

    Args:
        obj (LayoutDOM object) : a Layout (Row/Column), Plot or Widget object to display

        filename (str, optional) : filename to save document under (default: None)
            If None, infer from the filename.

        width (int) : the desired width of the exported layout obj only if
            it's a Plot instance. Otherwise the width kwarg is ignored.

        height (int) : the desired height of the exported layout obj only if
            it's a Plot instance. Otherwise the height kwarg is ignored.

        webdriver (selenium.webdriver) : a selenium webdriver instance to use
            to export the image.

        timeout (int) : the maximum amount of time (in seconds) to wait for
            Bokeh to initialize (default: 5) (Added in 1.1.1).

    Returns:
        filenames (list(str)) : the list of filenames where the SVGs files are saved.

    .. warning::
        Responsive sizing_modes may generate layouts with unexpected size and
        aspect ratios. It is recommended to use the default ``fixed`` sizing mode.

    '''
    svgs = get_svgs(obj, width=width, height=height, driver=webdriver, timeout=timeout)

    if len(svgs) == 0:
        log.warning("No SVG Plots were found.")
        return []

    return _write_collection(svgs, filename, "svg")

#-----------------------------------------------------------------------------
# Dev API
#-----------------------------------------------------------------------------

def get_screenshot_as_png(obj: Union[LayoutDOM, Document], *, driver: "Optional[WebDriver]" = None, timeout: int = 5,
        resources: Resources = INLINE, width: Optional[int] = None, height: Optional[int] = None) -> Image:
    ''' Get a screenshot of a ``LayoutDOM`` object.

    Args:
        obj (LayoutDOM or Document) : a Layout (Row/Column), Plot or Widget
            object or Document to export.

        driver (selenium.webdriver) : a selenium webdriver instance to use
            to export the image.

        timeout (int) : the maximum amount of time to wait for initialization.
            It will be used as a timeout for loading Bokeh, then when waiting for
            the layout to be rendered.

    Returns:
        image (PIL.Image.Image) : a pillow image loaded from PNG.

    .. warning::
        Responsive sizing_modes may generate layouts with unexpected size and
        aspect ratios. It is recommended to use the default ``fixed`` sizing mode.

    '''
    from .webdriver import webdriver_control

    with _tmp_html() as tmp:
        html = get_layout_html(obj, resources=resources, width=width, height=height)
        with open(tmp.path, mode="w", encoding="utf-8") as file:
            file.write(html)

        web_driver = driver if driver is not None else webdriver_control.get()
        web_driver.maximize_window()
        web_driver.get("file:///" + tmp.path)
        wait_until_render_complete(web_driver, timeout)
        [width, height, dpr] = _maximize_viewport(web_driver)
        png = web_driver.get_screenshot_as_png()

    return (Image.open(io.BytesIO(png))
                 .convert("RGBA")
                 .crop((0, 0, width*dpr, height*dpr))
                 .resize((width, height)))

def get_svg(obj: Union[LayoutDOM, Document], *, driver: "Optional[WebDriver]" = None, timeout: int = 5,
        resources: Resources = INLINE, width: Optional[int] = None, height: Optional[int] = None) -> List[str]:
    from .webdriver import webdriver_control

    with _tmp_html() as tmp:
        html = get_layout_html(obj, resources=resources, width=width, height=height)
        with open(tmp.path, mode="w", encoding="utf-8") as file:
            file.write(html)

        web_driver = driver if driver is not None else webdriver_control.get()
        web_driver.get("file:///" + tmp.path)
        wait_until_render_complete(web_driver, timeout)
        svgs = cast(List[str], web_driver.execute_script(_SVG_SCRIPT))

    return svgs

def get_svgs(obj: Union[LayoutDOM, Document], *, driver: "Optional[WebDriver]" = None, timeout: int = 5,
        resources: Resources = INLINE, width: Optional[int] = None, height: Optional[int] = None) -> List[str]:
    from .webdriver import webdriver_control

    with _tmp_html() as tmp:
        html = get_layout_html(obj, resources=resources, width=width, height=height)
        with open(tmp.path, mode="w", encoding="utf-8") as file:
            file.write(html)

        web_driver = driver if driver is not None else webdriver_control.get()
        web_driver.get("file:///" + tmp.path)
        wait_until_render_complete(web_driver, timeout)
        svgs = cast(List[str], web_driver.execute_script(_SVGS_SCRIPT))

    return svgs

def get_layout_html(obj: Union[LayoutDOM, Document], *, resources: Resources = INLINE,
        width: Optional[int] = None, height: Optional[int] = None) -> str:
    '''

    '''
    resize = False
    if width is not None or height is not None:
        # Defer this import, it is expensive
        from ..models.plots import Plot
        if not isinstance(obj, Plot):
            warnings.warn("Export method called with height or width kwargs on a non-Plot layout. The size values will be ignored.")
        else:
            resize = True

            old_width = obj.plot_width
            old_height = obj.plot_height

            if width is not None:
                obj.plot_width = width
            if height is not None:
                obj.plot_height = height

    template = r"""\
    {% block preamble %}
    <style>
        html, body {
            box-sizing: border-box;
            width: 100%;
            height: 100%;
            margin: 0;
            border: 0;
            padding: 0;
            overflow: hidden;
        }
    </style>
    {% endblock %}
    """

    try:
        html = file_html(obj, resources, title="", template=template, suppress_callback_warning=True, _always_new=True)
    finally:
        if resize:
            assert isinstance(obj, Plot)
            obj.plot_width = old_width
            obj.plot_height = old_height

    return html

def wait_until_render_complete(driver: "WebDriver", timeout: int) -> None:
    '''

    '''
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.common.exceptions import TimeoutException

    def is_bokeh_loaded(driver: "WebDriver") -> bool:
        return cast(bool, driver.execute_script('''
            return typeof Bokeh !== "undefined" && Bokeh.documents != null && Bokeh.documents.length != 0
        '''))

    try:
        WebDriverWait(driver, timeout, poll_frequency=0.1).until(is_bokeh_loaded)
    except TimeoutException as e:
        _log_console(driver)
        raise RuntimeError('Bokeh was not loaded in time. Something may have gone wrong.') from e

    driver.execute_script(_WAIT_SCRIPT)

    def is_bokeh_render_complete(driver: "WebDriver") -> bool:
        return cast(bool, driver.execute_script('return window._bokeh_render_complete;'))

    try:
        WebDriverWait(driver, timeout, poll_frequency=0.1).until(is_bokeh_render_complete)
    except TimeoutException:
        log.warning("The webdriver raised a TimeoutException while waiting for "
                    "a 'bokeh:idle' event to signify that the layout has rendered. "
                    "Something may have gone wrong.")
    finally:
        _log_console(driver)

#-----------------------------------------------------------------------------
# Private API
#-----------------------------------------------------------------------------

def _write_collection(items: List[str], filename: Union[str, None], ext: str) -> List[str]:
    if filename is None:
        filename = default_filename(ext)

    filenames = []

    for i, item in enumerate(items):
        if i > 0:
            idx = filename.find(f".{ext}")
            filename = filename[:idx] + f"_{i}" + filename[idx:]

        with open(filename, mode="w", encoding="utf-8") as f:
            f.write(item)

        filenames.append(filename)

    return filenames

def _log_console(driver: "WebDriver") -> None:
    levels = {'WARNING', 'ERROR', 'SEVERE'}
    try:
        logs = driver.get_log('browser')
    except Exception:
        return
    messages = [ log.get("message") for log in logs if log.get('level') in levels ]
    if messages:
        log.warning("There were browser warnings and/or errors that may have affected your export")
        for message in messages:
            log.warning(message)

def _maximize_viewport(web_driver: "WebDriver") -> Tuple[int, int, int]:
    calculate_viewport_size = """\
        const root = document.getElementsByClassName("bk-root")[0]
        const {width, height} = root.children[0].getBoundingClientRect()
        return [width, height, window.devicePixelRatio]
    """
    viewport_size: Tuple[int, int, int] = web_driver.execute_script(calculate_viewport_size)
    calculate_window_size = """\
        const [width, height, dpr] = arguments
        return [
            // XXX: outer{Width,Height} can be 0 in headless mode under certain window managers
            Math.max(0, window.outerWidth - window.innerWidth) + width*dpr,
            Math.max(0, window.outerHeight - window.innerHeight) + height*dpr,
        ]
    """
    [width, height] = web_driver.execute_script(calculate_window_size, *viewport_size)
    eps = 100 # XXX: can't set window size exactly in certain window managers, crop it to size later
    web_driver.set_window_size(width + eps, height + eps)
    return viewport_size

_SVGS_SCRIPT = """
const {LayoutDOMView} = Bokeh.require("models/layouts/layout_dom")
const {PlotView} = Bokeh.require("models/plots/plot")

function* collect_svgs(views) {
  for (const view of views) {
    if (view instanceof LayoutDOMView) {
      yield* collect_svgs(view.child_views.values())
    }
    if (view instanceof PlotView && view.model.output_backend == "svg") {
      const {ctx} = view.canvas_view.compose()
      yield ctx.get_serialized_svg(true)
    }
  }
}

const root_views = Object.values(Bokeh.index)
return [...collect_svgs(root_views)]
"""

_SVG_SCRIPT = """\
function* export_svgs(views) {
  for (const view of views) {
    // TODO: use to_blob() API in future
    const {ctx} = view.export("svg")
    yield ctx.get_serialized_svg(true)
  }
}

const root_views = Object.values(Bokeh.index)
return [...export_svgs(root_views)]
"""

_WAIT_SCRIPT = """
// add private window prop to check that render is complete
window._bokeh_render_complete = false;
function done() {
  window._bokeh_render_complete = true;
}

const doc = Bokeh.documents[0];

if (doc.is_idle)
  done();
else
  doc.idle.connect(done);
"""


class _TempFile:
    _closed: bool = False

    fd: int
    path: str

    def __init__(self, *, prefix: str = "tmp", suffix: str = "") -> None:
        self.fd, self.path = mkstemp(prefix=prefix, suffix=suffix)

    def __enter__(self) -> "_TempFile":
        return self

    def __exit__(self, exc: Any, value: Any, tb: Any) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return

        try:
            os.close(self.fd)
        except OSError:
            pass

        try:
            os.unlink(self.path)
        except OSError:
            pass

        self._closed = True

def _tmp_html() -> _TempFile:
    return _TempFile(prefix="bokeh", suffix=".html")

#-----------------------------------------------------------------------------
# Code
#-----------------------------------------------------------------------------
