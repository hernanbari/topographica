"""
Topographica cortical map simulator package.

Topographica is designed as a collection of packages from which
elements can be selected to model specific systems.  For more
information, see the individual subpackages::

  base           - Core Topographica functions and classes
  plotting       - Visualization functions and classes
  analysis       - Analysis functions and classes (besides plotting)
  tkgui          - Tk-based graphical user interface (GUI)
  command        - High-level user commands
  misc           - Various useful independent modules

The Topographica primitives library consists of a family of classes
that can be used with the above functions and classes::

  sheet          - Sheet classes: 2D arrays of processing units
  projection     - Projection classes: connections between Sheets
  pattern        - PatternGenerator classes: 2D input or weight patterns
  ep             - EventProcessor classes: other simulation objects
  transferfn     - Transfer functions, for e.g. normalization or squashing
  responsefn     - Calculate the response of a Projection
  learningfn     - Adjust weights for a Projection
  coordmapper    - CoordinateMapperFn classes: map coords between Sheets

Each of the library directories can be extended with new classes of
the appropriate type, just by adding a new .py file to that directory.
E.g. new PatternGenerator classes can be added to pattern/, and will
then show up in the GUI menus as potential input patterns.
"""

# The tests and the GUI are omitted from this list, and have to be
# imported explicitly if desired.
__all__ = ['analysis',
           'base',
           'command',
           'coordmapper',
           'ep',
           'learningfn',
           'misc',
           'numbergen',
           'transferfn',
           'pattern',
           'plotting',
           'projection',
           'responsefn',
           'sheet']


# Find out Topographica's version.
# First, try Git; if that fails, try to read the release file.

from subprocess import Popen, CalledProcessError, PIPE #pyflakes:ignore (has to do with Python versions for CalledProcessError)
import os, sys

(basepath, _) = os.path.split(os.path.abspath(__file__))
sys.path = [os.path.join(basepath, '../', 'external', 'param')] + sys.path
sys.path = [os.path.join(basepath, '../', 'external', 'paramtk')] + sys.path
sys.path = [os.path.join(basepath, '../', 'external', 'imagen')] + sys.path
sys.path = [os.path.join(basepath, '../', 'external', 'lancet')] + sys.path

import param
import imagen

# Patch for versions of param prior to 10 May 2013
param.main=param.Parameterized(name="main")


def version_int(v):
    """
    Convert a version four-tuple to a format that can be used to compare
    version numbers.
    """
    return int("%02d%02d%02d%05d" % v)



def version_str(v):
	"""
	Convert a version four-tuple to a string format x.y.z
	"""
	return "%d.%d.%d" % (v[0], v[1], v[2])



def _find_version():
    """
    Return the version tuple, the release number, the git commit, and
    whether reading pickle files is allowed (False if no version
    information avaliable).
    """

    version_warning = """\
Unable to determine the version information for this copy of Topographica.

For an official release, the version information is stored in a file
named topo/.release.  For a development copy checked out from Git, the
version is requested using "git describe".  Neither of these options
was successful (output: "%s"), 
perhaps because Git is not available on this machine.  To work around
this problem, either install Git on this machine, or temporarily use a
machine that does have Git and run "topographica make-release-file",
making sure you have write permissions on Topographica's root
directory.

In the meantime, reading and saving snapshots will be disabled,
because version information is necessary for determining how to
interpret saved files.\n\n""" 

    version_string = None

    (basepath,_) = os.path.split(os.path.abspath(__file__))

    try:
        git_process = Popen(["git","describe","--long","--match","v*.*.*"], stdout=PIPE, stderr=PIPE, cwd=basepath)
        version_string = git_process.communicate()[0].strip()
        if git_process.poll():
            raise OSError

    except OSError, CalledProcessError: #pyflakes:ignore (has to do with Python versions for CalledProcessError)
        try:
            release_file = open(basepath + "/.release")
            version_string = release_file.read()
            release_file.close()
        except IOError:
            pass

    try:
        (_version, count, _commit) = version_string[1:].split("-")
        _version = _version.split(".")
        _version = (int(_version[0]), int(_version[1]), int(_version[2]), int(count))
        _release = version_int(_version)
        pickle_allowed = True

    except:
        param.main.warning(version_warning % version_string)
        (_version, _release, _commit, pickle_allowed) = ((0,0,0,0),0,0,False)

    return (_version, _release, _commit, pickle_allowed)


(version, release, commit, pickle_read_write_allowed) = _find_version()



# Determine which paths to search for input files
#
# By default, searches in:
# - the current working directory (the default value of param.resolve_path.search_paths),
# - the parent of topo (to get images/, examples/, etc.)
# - topo (for backwards compatibility, e.g. for finding color keys)
#
_package_path = os.path.split(__file__)[0] # location of topo
_root_path = os.path.abspath(os.path.join(_package_path,'..')) # parent of topo
param.resolve_path.search_paths+=[_root_path,_package_path]



# CEBALERT (about PIL):
# PIL can be installed so that it's e.g. "from PIL import Image" or
# just "import Image".  The code below means Image etc are always
# imported, but then the rest of topographica can consistently use
# Image (rather than a try/except, such as the one below). An
# alternative would be an import hook, which would only run on
# attempting to import Image etc.

try:
    import Image
except ImportError:
    from PIL import Image, ImageOps, ImageDraw, ImageFont  # pyflakes:ignore (try/except import)
    import sys
    sys.modules['Image']=Image
    sys.modules['ImageOps']=ImageOps
    sys.modules['ImageDraw']=ImageDraw
    sys.modules['ImageFont']=ImageFont

# ImageTk is completely optional
try:
    import ImageTk
except ImportError:
    try:
        from PIL import ImageTk  # pyflakes:ignore (try/except import)
        import sys
        sys.modules['ImageTk']=ImageTk
    except ImportError:
        pass


# CEBALERT: can we move these pickle support functions elsewhere?  In
# fact, can we just gather all the non-legacy pickle garbage into one
# place? Pickle clutter adds complexity, and having all the pickle
# support in one places makes it easier for other developers to copy
# in new situations.

# (note that these _pickle_support functions also work for deep copying)

def _numpy_ufunc_pickle_support():
    """
    Allow instances of numpy.ufunc to pickle.
    """
    # Remove this when numpy.ufuncs themselves support pickling.
    # Code from Robert Kern; see:
    #http://news.gmane.org/find-root.php?group=gmane.comp.python.numeric.general&article=13400
    from numpy import ufunc
    import copy_reg

    def ufunc_pickler(ufunc):
        """Return the ufunc's name"""
        return ufunc.__name__

    copy_reg.pickle(ufunc,ufunc_pickler)

_numpy_ufunc_pickle_support()


def _mpq_pickle_support():
    """Allow instances of gmpy.mpq to pickle."""
    from gmpy import mpq
    mpq_type = type(mpq(1,10)) # gmpy doesn't appear to expose the type another way
    import copy_reg
    copy_reg.pickle(mpq_type,lambda q: (mpq,(q.digits(),)))



def _instance_method_pickle_support():
    """Allow instance methods to pickle."""
    # CB: well, it seems to work - maybe there are cases where this
    # wouldn't work?
    # Alternative technique (totally different approach), but would
    # only work with pickle (not cPickle):
    # http://code.activestate.com/recipes/572213/
    def _pickle_instance_method(mthd):
        mthd_name = mthd.im_func.__name__
        obj = mthd.im_self
        return getattr, (obj,mthd_name)

    import copy_reg, types
    copy_reg.pickle(types.MethodType, _pickle_instance_method)

_instance_method_pickle_support()


from topo.base.simulation import Simulation

# Set the default value of Simulation.time_type to gmpy.mpq. If gmpy
# is unavailable, use the slower fixedpoint.FixedPoint.
try:
    import gmpy
    Simulation.time_type = gmpy.mpq
    Simulation.time_type_args = ()
    _mpq_pickle_support()
except ImportError:
    import topo.misc.fixedpoint as fixedpoint
    param.main.warning('gmpy.mpq not available; using slower fixedpoint.FixedPoint for simulation time.')
    Simulation.time_type = fixedpoint.FixedPoint
    Simulation.time_type_args = (4,)  # gives precision=4

    # Provide a fake gmpy.mpq (to allow e.g. pickled test data to be
    # loaded).
    # CEBALERT: can we move this into whatever test needs it? I guess
    # it also has to be here to allow snapshots saved using gmpy time
    # type to open on systems where gmpy is not available.
    from topo.misc.util import gmpyImporter
    import sys
    sys.meta_path.append(gmpyImporter())



sim = Simulation()


# numbergen used to be part of topo; import it there for backwards compatibility
# and set the time function to be topo.sim.time()
import sys,numbergen
sys.modules['topo.numbergen']=numbergen
sys.modules['topo.numbergen.basic']=numbergen
try:
    numbergen.TimeDependentValue.time_fn = sim.time
except AttributeError: # For versions of numbergen before April 2013
    numbergen.ExponentialDecay.time_fn = sim.time

# imagen used to be part of topo; import its files at their former locations
# for backwards compatibility and set the time function to be topo.sim.time()
import imagen as pattern
import imagen.random, imagen.image
sys.modules['topo.base.boundingregion']=pattern.boundingregion
sys.modules['topo.base.sheetcoords']=pattern.sheetcoords
sys.modules['topo.base.patterngenerator']=pattern.patterngenerator
sys.modules['topo.misc.patternfn']=pattern.patternfn
sys.modules['topo.pattern']=pattern
sys.modules['topo.pattern.basic']=pattern
sys.modules['topo.pattern.random']=pattern.random
sys.modules['topo.pattern.image']=pattern.image
sys.modules['topo.pattern.rds']=imagen.random
pattern.Translator.time_fn = sim.time



def about(display=True):
    """Print release and licensing information."""

    ABOUT_TEXT = """
Pre-release version %s (%s) of Topographica; an updated
version may be available from topographica.org.

This program is free, open-source software available under the BSD
license (http://www.opensource.org/licenses/bsd-license.php).
"""%(release,version)
    if display:
        print ABOUT_TEXT
    else:
        return ABOUT_TEXT


# Set most floating-point errors to be fatal for safety; see
# topo/misc/patternfn.py for examples of how to disable
# the exceptions when doing so is safe.  Underflow is always
# considered safe; e.g. input patterns can be very small
# at large distances, and when they are scaled by small
# weights underflows are common and not a problem.
from numpy import seterr
old_seterr_settings=seterr(all="raise",under="ignore")


# Load Topographica IPython extension if imported as module
try:
    ip = get_ipython() # pyflakes:ignore (try/except import)
    ip.extension_manager.load_extension('topo.misc.ipython')
except:
    pass

from topo.analysis.featureresponses import FeatureResponses, FeatureCurves,\
    FeatureMaps, ReverseCorrelation, MeasureResponseCommand, FeatureCurveCommand,\
    pattern_response, topo_metadata_fn, store_rfs, store_maps, store_curves,\
    get_feature_preference

FeatureResponses.metadata_fns = [topo_metadata_fn]
FeatureMaps.measurement_storage_hook = store_maps
FeatureCurves.measurement_storage_hook = store_curves
ReverseCorrelation.measurement_storage_hook = store_rfs

MeasureResponseCommand.preference_lookup_fn = get_feature_preference
MeasureResponseCommand.pattern_response_fn = pattern_response.instance()
FeatureCurveCommand.pattern_response_fn = pattern_response.instance()
