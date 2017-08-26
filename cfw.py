#=======================================================================
#       $Id: cfw.py,v 1.1 2011/02/21 13:42:09 pythontech Exp pythontech $
#	Configuration framework
#=======================================================================
import os
import logging
import urllib
#try:
#    from cherrypy.lib import unrepr
#except ImportError:
#    def unrepr(s):
#        return _simple_unrepr(s)

_root = {}
_classes = {}
_logger = logging.getLogger('cfw')

class CfwNotFound(Exception):
    pass

class obj:
    def __init__(self, classname,*args,**kw):
        self.classname = classname
        self.args = args
        self.kw = kw

    def instantiate(self,uri='?'):
        _logger.debug("instantiating %s (%s)", uri, self.classname)
#        print " instantiate", self.classname, self.args, self.kw
        if _classes.has_key(self.classname):
            # Already found
            cls = _classes[self.classname]
        else:
            cpath = self.classname.split('.')
            clsname = cpath.pop()
            mname = '.'.join(cpath)
            mod = __import__(mname)
            for comp in cpath[1:]:
                mod = getattr(mod,comp)
            cls = getattr(mod,clsname)
            # Save in cache
            _classes[self.classname] = cls
        # Instantiate arguments & keywords
        iargs = _cfw(self.args)
        ikw = _cfw(self.kw)
        inst = cls(*iargs, **ikw)
#        print "  =",inst
        return inst

class ref:
    def __init__(self,uri):
        self.uri = uri

def _set(node, path, value):
    if len(path)==0:
        raise ValueError, "Empty path"
    for step in path[:-1]:
        if step not in node:
            node[step] = {}
        node = node[step]
    step = path[-1]
    node[step] = value

def set(**kw):
    for p,v in kw.items():
        setpath(p, v)

def setpath(url, value):
    _set(_root, _url2path(url), value)

def setitem(name, value):
    _set(_root, [name], value)

def merge(dct):
    for uri,v in dct.items():
        path = _url2pat(uri)
        if len(path)==0:
            raise None, "Empty uri in cfw.merge"
        pos = _root
        for step in path[:-1]:
            if pos.has_key(step):
                pos = pos[step]
            elif type(pos) is dict:
                new = dict()
                pos[step] = new
                pos = new
            else:
                raise None, "Step %s in uri leads to %s" \
                      % (step,type(pos))
        step = path[-1]
        pos[step] = v

def parse_config(filenames):
    '''
    Parse one or more INI-style file and merge with existing 
    config.
    Item name of __class__ determines Python class.
    If class is 'list' or 'tuple' then item names are ignored.
    If no class, result is a dict.
    Value is converted to int or float if possible.
    Value beginning with '@' is taken as ref.
    '''
    from ConfigParser import SafeConfigParser
    p = SafeConfigParser()
    # Don't convert item names to lowercase
    p.optionxform = str
    p.read([os.path.expanduser(f) for f in filenames])
    #print p.sections()
    for sect in p.sections():
        klass = None
        kw = {}
        vals = []
        for name, value in p.items(sect):
            if name=='__class__':
                klass = value
            elif name.startswith('__'):
                raise ValueError, 'Unknown special name %s' % repr(name)
            else:
                if value.startswith('@'):
                    # Reference to another item
                    value = ref(value[1:])
                else:
                    # Convert to number or boolean if possible
                    value = unrepr(value)
                kw[name] = value
                vals.append(value)
        if sect=='GLOBAL':
            if klass is not None:
                raise ValueError, '__class__ may not be set at GLOBAL level'
            for name, value in kw.items():
                setitem(name, value)
        elif klass is None  or  klass=='dict':
            setitem(sect, kw)
        elif klass=='list':
            # Names ignored
            setitem(sect, vals)
        elif klass=='tuple':
            # Names ignored
            setitem(sect, tuple(vals))
        else:
            setitem(sect, obj(klass, **kw))
    
def _cfw(any, uri='?'):
    '''Instantiate arbitrary item'''
    if type(any) is tuple:
        val = tuple(map(_cfw, any))
    elif type(any) is list:
        val = map(_cfw, any)
    elif type(any) is dict:
        val = {}
        for n,v in any.items():
            val[n] = _cfw(v)
    elif isinstance(any, ref):
        val = get(any.uri)
    elif isinstance(any, obj):
        val = any.instantiate(uri)
    elif callable(any):
        # e.g. lambda: cfw.get('foo')+'99'
        val = any()
    else:
        val = any
    return val

# Arbitrary value we can distinguish from anything user passes in
_fail_if_not_found = []

def get(uri, default=_fail_if_not_found):
    try:
        value = xget(uri)
        return value
    except CfwNotFound, e:
        if default is not _fail_if_not_found:
            return default
        raise

def xget(uri):
#    print "cfw.get",uri
    path = _url2path(uri)
    if len(path)==0:
        raise ValueError, "Empty uri in cfw.get"
    pos = _root
    for step in path[:-1]:
        if not pos.has_key(step):
            raise CfwNotFound, 'Unknown cfw path: %s' % uri
        pos = pos[step]
    step = path[-1]
    if not pos.has_key(step):
        raise CfwNotFound, 'Unknown cfw path: %s' % uri
    item = pos[step]
    inst = _cfw(item, uri)
    pos[step] = inst
#    print " =",inst
    return inst

def _url2path(url):
    return map(urllib.quote, url.split('/'))

# Basic converter of string to value
def unrepr(s):
    if not s:
        return s
    # Maybe an integer
    try:
        v = int(s)
        return v
    except ValueError: pass
    # Maybe a float
    try:
        v = float(s)
        return s
    except ValueError: pass
    # Maybe a bool or None
    if s == 'True':
        return True
    if s == 'False':
        return False
    if s == 'None':
        return None
    if s.startswith("'") and s.endswith("'"):
        # FIXME escape chars
        return s[1:-1]
    if s.startswith('"') and s.endswith('"'):
        # FIXME escape chars
        return s[1:-1]
    return s

if __name__=='__main__':
    set(abc = 123,
        defg = 'hij',
        jkl = obj('string.split','m.n','.'),
        cmd = obj('cmd.Cmd', completekey='A'))
    parse_config('test.ini')
    import sys
    for arg in sys.argv[1:]:
        print get(arg)
    print _root.keys()
