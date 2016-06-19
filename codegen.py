#
# Copyright 2014-6 Jari Ojanen
#

# Possible values for OBase.mods list
#
PRIVATE   = "private"
PROTECTED = "protected"
PUBLIC    = "public"
STATIC    = "static"
FINAL     = "final"
TEST      = "test"
GETTER    = "getter"
SETTER    = "setter"
OVERRIDE  = "override"
DBVAR     = "db"
REMEMBER  = "remember"  # between code generations

# Possible values for LANGUAGE
#
LANG_C    = { 'name': "C",
              'ext': ".c",
              'func': "GenC" }
LANG_H    = { 'name': "H",
              'ext': ".h",
              'func': "GenH" }
LANG_CPP  = { 'name': "C++",
              'ext': ".cpp",
              'func': "GenCPP" }
LANG_HPP  = { 'name': "H++",
              'ext': ".hpp",
              'func': "GenHPP" }
LANG_CS   = { 'name': "C#",
              'ext': ".cs",
              'func': "GenCS" }
LANG_JAVA = { 'name': "JAVA",
              'ext': ".java",
              'func': "GenCS" }
LANG_JS   = { 'name': "JAVASCRIPT",   # not yet supported
              'ext': ".js",
              'func': "GenCS" }

from functools import wraps
import os.path

CLASSES = []
INSTANCES = []
LANGUAGE = LANG_C
LANGUAGES = [LANG_C, LANG_H, LANG_CPP, LANG_HPP, LANG_CS, LANG_JAVA]

NEWLINE = "\n"

def isLang(lang):
    global LANGUAGE

    return LANGUAGE['name'] == lang['name']

def q(s: str):
    return "\""+s+"\""


#def p(l):
#    a = ",".join(l)
#    return "("+a+")"

def c(*items):
    lst = []

    for i in items:
        if isinstance(i, str):
            lst.append(i)
        elif isinstance(i, OArg):
            lst.append(i.name)
        else:
            lst.append("????")

    return "(" + (", ".join(lst)) + ")"

def export(rtype):
    def func_wrap(func):
        func.export = 1
        func.rtype = rtype
        #print(func.__name__)
        #print(func)
        @wraps(func)
        def rfunc(*args, **kwargs):
            return func(*args, **kwargs)
        return rfunc
    return func_wrap

def exportclass(oclass):
    CLASSES.append(oclass)
    return oclass

def processExports():
    for c in CLASSES:
        o = c()
        m = [getattr(o,x) for x in dir(o) if "export" in dir(getattr(o,x))]

        for fn in m:
            meth = OMethod(fn.__name__, fn.rtype)
            fn(meth)
            o << meth
    
        INSTANCES.append(o)

# If class needs contructor parameters or some processing,
# this is replacement for processExports-getInstance system 
#
def handleExports(obj):
    m = [getattr(obj,x) for x in dir(obj) if "export" in dir(getattr(obj,x))]
    for fn in m:
        meth = OMethod(fn.__name__, fn.rtype)
        fn(meth)
        obj << meth


def getInstance(name):
    for i in INSTANCES:
        if i.name == name:
            return i
    return None


def flatten(l):
    for el in l:
        if isinstance(el, list) and not isinstance(el, str):
            for sub in flatten(el):
                yield sub
        else:
            yield el

class OBlock(object):
    def __init__(self, parent):
        self.parent = parent

    def __enter__(self):
        self.parent << "{"

    def __exit__(self,a,b,c):
        self.parent << "}"

class OFile(object):
    def __init__(self, fname, namespace=""):
        print("generating "+fname+"...")
        self.fname = fname
        self.f = open(fname, "wt")
        self.indent = 0
        self.includes = []
        self.namespace = namespace

        global LANGUAGE
        for lang in LANGUAGES:
            if fname.endswith(lang['ext']):
                LANGUAGE = lang
            
        if isLang(LANG_H) or isLang(LANG_HPP): 
            fbase = os.path.basename(fname)
            self << "#ifndef _"+fbase.upper()+"_H"
            self << "#define _"+fbase.upper()+"_H"
            self << ""

    def block(self, pre):
        self << pre
        return OBlock(self)

    def __lshift__(self, s):
        if isinstance(s, OBase):
            s.generate(self)
            return self

        if s in ["}", "};"]:
            self.indent -= 1
        #print ("\t"*self.indent) + self.line
        self.f.write(("    "*self.indent) + s + NEWLINE)
        if s == "{" or s.startswith("case "):
            self.indent += 1
        if s == "break;":
            self.indent -= 1
        return self

    def addIncludes(self):
        for inc in self.includes:
            if isLang(LANG_CS):
                self << "using " + inc + ";"
            elif isLang(LANG_JAVA):
                self << "import " + inc + ";"
            else:
                if inc.startswith("<"):
                    self << "#include " + inc
                else:
                    self << "#include " + q(inc)
        self << ""

        if len(self.namespace) > 0 and isLang(LANG_CS):
            self << "namespace " + self.namespace
            self << "{"


    def close(self):
        if len(self.namespace) > 0:
            self << "}"
        if isLang(LANG_H) or isLang(LANG_HPP):
            self <<  ""
            self << "#endif"
        self.f.close()


class OBase(object):
    def __init__(self, name: str, ctype: str, mods):
        self.name = name
        self.ctype = ctype
        self.mods = mods
        self.doc = ""
        self.pre = []

    def got(self, item):
        return item in self.mods

    def isGetter(self):
        return GETTER in self.mods

    def isSetter(self):
        return SETTER in self.mods

    def isOverride(self):
        return OVERRIDE in self.mods

    def isDbVal(self):
        return DBVAR in self.mods
        
    def getMods(self):
        visible = {FINAL, PRIVATE, PROTECTED, PUBLIC, STATIC}
        if isLang(LANG_CPP):
            visible = {STATIC}
        
        return " ".join(visible.intersection(self.mods)) + " "

    def generate(self, f):
        if isLang(LANG_H):
            self.genH(f)
        elif isLang(LANG_C):
            self.genC(f)
        elif isLang(LANG_HPP):
            self.genHPP(f)
        elif isLang(LANG_CPP):
            self.genCPP(f)
        elif isLang(LANG_CS):
            self.genCS(f)

        #func = getattr(self.__clss__, LANGUAGE['func'])
        #func(f)

    def define(self):
        return self.ctype + " " + self.name

class OArg(OBase):
    def __init__(self, name: str, ctype: str, mods={PRIVATE}, initial=None):
        OBase.__init__(self, name, ctype, mods)
        self.initial = initial

    def genH(self, f):
        f << self.define() + ";"
        
    def genC(self, f):
        pass

    def genCPP(self, f):
        pass

    def genCS(self, f):
        post = ""
        if self.initial:
            post = " = " + self.initial
        if len(self.pre) > 0:
            for line in self.pre:
                f << line
        f << self.getMods() + self.define() + post + ";"


class OMacro(OBase):
    def __init__(self, name, value):
        OBase.__init__(self, name, "", {PUBLIC})
        self.value = value

    def genH(self, f):
        if PUBLIC in self.mods:
            f << "#define " + self.name + " " + self.value
    
    def genC(self, f):
        if not PUBLIC in self.mods:
            f << "#define " + self.name + " " + self.value


class OMethod(OBase):
    def __init__(self, name, ctype, args=[], mods={PUBLIC}):
        OBase.__init__(self, name, ctype, mods)
        self.args = args
        self.code = []
        self.parent = None

    def arg(self):
        if len(self.args) == 0 and (isLang(LANG_C) or isLang(LANG_H)):
            return "(void)"
        alist = [ a.define() for a in self.args]
        return "("+ (", ".join(alist)) + ")"

    def genCS(self, f):
        f << ""
        if TEST in self.mods:
            f << "[TestMethod]"
        if self.isOverride():
            f << "@Override"
        with f.block(self.getMods() + self.define() + self.arg()):
            for code in self.code:
                f << code

    def genH(self, f):
        funcname = self.parent.name + "_" + self.name
        if PUBLIC in self.mods:
            f << "extern " + self.ctype + " " + funcname + " " + self.arg() + ";"
    
    def genHPP(self, f):
        f << self.getMods() + self.define() + self.arg() + ";"

                
    def _writeCMeth(self, f, funcname):
        with f.block(self.ctype + " " + funcname +  self.arg()):
            if REMEMBER in self.mods:
                f << "//{BEGIN:"+funcname+"}"
            for code in self.code:
                if isinstance(code, OBase):
                    code.generate(f)
                else:
                    f << code
            if REMEMBER in self.mods:
                f << "//{END:"+funcname+"}"
        
    def genCPP(self, f):
        self._writeCMeth(f, self.parent.name + "::" + self.name)

    def genC(self, f):
        funcname = self.parent.name + "_" + self.name

        f << ""
        self._writeCMeth(f, funcname)

    def __lshift__(self, s):
        if isinstance(s, str):
	        self.code.append(s)
        elif isinstance(s, OBase):
            self.code.append(s)
        else:
            for line in flatten(s):
                self.code.append(line)
        return self


class OEnum(OBase):
    def __init__(self, name: str, mods={PUBLIC}, items=[]):
        OBase.__init__(self, name, name, mods)
        self.items = items

    def add(self, item):
        self.items.append(item)

    def genCS(self, f):
        with f.block(self.getMods() + "enum " + self.name):
            for i in self.items:
                f << i + ","


def doBlock(f, name, items):
    with f.block(name):
        for i in items:
            f << i

class OProperty(OBase):
    def __init__(self, name: str, ctype, mods={PUBLIC}):
        OBase.__init__(self, name, ctype, mods)

        if self.name.startswith("_"):
            self.name = self.name[1].upper() + self.name[2:]

        self.getter = []
        self.setter = []

    def genCS(self, f):
        if len(self.pre) > 0:
            for line in self.pre:
                f << line
        with f.block(self.getMods() + self.define()):
            if self.isGetter():
                if len(self.getter) == 1:
                    f << "get { " + self.getter[0] + " }"
                else:
                    doBlock(f, "get", self.getter)
            if self.isSetter():
                if len(self.setter) == 1:
                    f << "set { " + self.setter[0] + " }"
                else:
                    doBlock(f, "set", self.setter)


class OClass(OBase):
    def __init__(self, name: str, mods={PUBLIC}):
        OBase.__init__(self, name, name, mods)
        self.members = []
        self.implements = []

    def __lshift__(self, m):
        m.parent = self
        self.members.append(m)
        return self

    def makeGetsSets(self):
        for i in self.members:
            if i.isGetter():
                m = OMethod("get_"+i.name, i.ctype, [])
                m << "return "+i.name+";"
                self << m
            if i.isSetter():
                m = OMethod("set_"+i.name, "void", [OArg("val", i.ctype)])
                m << i.name+" = val;"
                self << m

    def genCS(self, f):
        if len(self.doc) > 0:
            f << "/// <summary>"
            f << "/// " + self.doc
            f << "/// </summary>"
        if TEST in self.mods:
            f << "[TestClass]"

        post = ""
        if len(self.implements) > 0:
            if isLang(LANG_JAVA):
            	post = " implements "
            else:
                post = " : "
            post += ", ".join(self.implements)


        for i in self.members:
            if isinstance(i, OArg) and (i.isGetter() or i.isSetter()):
                p = OProperty(i.name, i.ctype)

                p.mods = {PUBLIC} | ( i.mods & {GETTER,SETTER} )   # | = union     & = intersection

                if i.isGetter():
                	p.getter = ["return "+i.name+";"]
                if i.isSetter():
                	p.setter = [i.name + " = value;"]
                self << p

        with f.block(self.getMods() + "class " + self.name + post):
            for m in self.members:
                m.genCS(f)

    def genHPP(self, f):
        self.makeGetsSets()
        with f.block(self.getMods() + "class " + self.name):
            for prot in [PUBLIC, PROTECTED, PRIVATE]:
                items = [x for x in self.members if x.got(prot)]
                f << prot + ":"
                for m in items:
                    m.genHPP(f)
        f << ";"
    
    def genCPP(self, f):
        for prot in [PUBLIC, PROTECTED, PRIVATE]:
            items = [x for x in self.members if x.got(prot)]
            for m in items:
                m.genCPP(f)

    def genH(self, f):
        for m in self.members:
            m.generate(f)

    def genC(self, f):
        for m in self.members:
            m.generate(f)

    def genPY(self, f):
        pass


class OStruct(OBase):
    def __init__(self, name: str, mods={PUBLIC}):
        OBase.__init__(self, name, name, mods)
        self.members = []

    def __lshift__(self, m):
        m.parent = self
        self.members.append(m)
        return self

    def genH(self, f):
        with f.block("typedef struct"):
            for m in self.members:
                m.generate(f)
        f << self.name + "_t;"
        
    def genC(self, f):
        pass


class OSwitch(OBase):
    def __init__(self, name: str, mods={PUBLIC}):
        OBase.__init__(self, name, "", mods)
        self.members = []

    def add(self, cond, code):
        self.members.append([cond,code])
        return self

    def _write(self, f):
        with f.block("switch (" + self.name + ")"):
            for cond, code in self.members:
                f << "case " + cond + ":"
                for line in code:
                    f << line
                f << "break;"

    def genH(self, f):
        pass

    def genC(self, f):
        self._write(f)

    def genCS(self, f):
        self._write(f)

    def genCPP(self, f):
        self._write(f)

        
class OTestClass(OClass):
    def __init__(self, name: str):
        OClass.__init__(self, name, mods={PUBLIC,TEST})


#-------------------------------------------------------------------------------
def write_file(c, path):
    for ext in ['.h', '.c']:
        f = OFile(path+c.name+ext)
        if ext == '.c':
            f.includes = ['hw.h']
            f.addIncludes()
        c.generate(f)
        f.close()

def write_file_cs(lst, fname: str, namespace: str, includes=[]):
    f = OFile(fname, namespace)
    f.includes = includes
    f.addIncludes()
    for c in lst:
    	c.generate(f)
    f.close()

def write_file_cpp(c, path: str):
    for ext in ['.hpp', '.cpp']:
        f = OFile(path+c.name+ext)
        c.genCPP(f)
        f.close()

def write_file_n(fname, *classes):
    for ext in ['.h', '.c']:
        f = OFile(fname+ext)
        if ext == '.c':
            fbase = os.path.basename(fname)
            f.includes = ['hw.h', fbase+".h"]
            f.addIncludes()
        for c in classes:
            if isinstance(c, list):
                for ci in c:
                    ci.generate(f)
            else:
                c.generate(f)
        f.close()

#
# for generating code inside method
#
def block(name, items):
    return [name, '{'] + items + ['}']

def IF(cond, items):
    return block("if (" + cond + ")", items)

def ELSE(items):
    return block("else", items)

def FOREACH(cond, items):
    return block("foreach (" + cond + ")", items)

def SWITCH(cond, items):
    return block("switch(" + cond + ")", items)

def CASE(cond, items):
    return ["case "+ cond + ":"] + items + ["break;"]
