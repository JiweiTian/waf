#! /usr/bin/env python
# encoding: utf-8
# XCode 3/XCode 4 generator for Waf
# Nicolas Mercier 2011
# Modified by Simon Warg 2015
# XCode project file format based on http://www.monobjc.net/xcode-project-file-format.html

"""
Usage:

def options(opt):
	opt.load('xcode')

$ waf configure xcode
"""

# TODO: support iOS projects

from waflib import Context, TaskGen, Build, Utils
import os, sys, random, time

HEADERS_GLOB = '**/(*.h|*.hpp|*.H|*.inl)'

MAP_EXT = {
	'.h' :  "sourcecode.c.h",

	'.hh':  "sourcecode.cpp.h",
	'.inl': "sourcecode.cpp.h",
	'.hpp': "sourcecode.cpp.h",

	'.c':   "sourcecode.c.c",

	'.m':   "sourcecode.c.objc",

	'.mm':  "sourcecode.cpp.objcpp",

	'.cc':  "sourcecode.cpp.cpp",

	'.cpp': "sourcecode.cpp.cpp",
	'.C':   "sourcecode.cpp.cpp",
	'.cxx': "sourcecode.cpp.cpp",
	'.c++': "sourcecode.cpp.cpp",

	'.l':   "sourcecode.lex", # luthor
	'.ll':  "sourcecode.lex",

	'.y':   "sourcecode.yacc",
	'.yy':  "sourcecode.yacc",

	'.plist': "text.plist.xml",
	".nib":   "wrapper.nib",
	".xib":   "text.xib",
}

# Used in PBXNativeTarget elements
PRODUCT_TYPE_APPLICATION = 'com.apple.product-type.application'
PRODUCT_TYPE_FRAMEWORK = 'com.apple.product-type.framework'
PRODUCT_TYPE_TOOL = 'com.apple.product-type.tool'
PRODUCT_TYPE_LIB_STATIC = 'com.apple.product-type.library.static'
PRODUCT_TYPE_LIB_DYNAMIC = 'com.apple.product-type.library.dynamic'
PRODUCT_TYPE_EXTENSION = 'com.apple.product-type.kernel-extension'
PRODUCT_TYPE_IOKIT = 'com.apple.product-type.kernel-extension.iokit'

# Used in PBXFileReference elements
FILE_TYPE_APPLICATION = 'wrapper.cfbundle'
FILE_TYPE_FRAMEWORK = 'wrapper.framework'

TARGET_TYPE_FRAMEWORK = (PRODUCT_TYPE_FRAMEWORK, FILE_TYPE_FRAMEWORK, '.framework')
TARGET_TYPE_APPLICATION = (PRODUCT_TYPE_APPLICATION, FILE_TYPE_APPLICATION, '.app')

import sys, traceback

part1 = 0
part2 = 10000
part3 = 0
id = 562000999
def newid():
	global id
	id = id + 1
	return "%04X%04X%04X%012d" % (0, 10000, 0, id)

class XCodeNode:
	def __init__(self):
		self._id = newid()

	def tostring(self, value):
		if isinstance(value, dict):
			result = "{\n"
			for k,v in value.items():
				result = result + "\t\t\t%s = %s;\n" % (k, self.tostring(v))
			result = result + "\t\t}"
			return result
		elif isinstance(value, str):
			return "\"%s\"" % value
		elif isinstance(value, list):
			result = "(\n"
			for i in value:
				result = result + "\t\t\t%s,\n" % self.tostring(i)
			result = result + "\t\t)"
			return result
		elif isinstance(value, XCodeNode):
			return value._id
		else:
			return str(value)

	def write_recursive(self, value, file):
		if isinstance(value, dict):
			for k,v in value.items():
				self.write_recursive(v, file)
		elif isinstance(value, list):
			for i in value:
				self.write_recursive(i, file)
		elif isinstance(value, XCodeNode):
			value.write(file)

	def write(self, file):
		for attribute,value in self.__dict__.items():
			if attribute[0] != '_':
				self.write_recursive(value, file)

		w = file.write
		w("\t%s = {\n" % self._id)
		w("\t\tisa = %s;\n" % self.__class__.__name__)
		for attribute,value in self.__dict__.items():
			if attribute[0] != '_':
				w("\t\t%s = %s;\n" % (attribute, self.tostring(value)))
		w("\t};\n\n")

class XCID(XCodeNode):
	def __init__(self, id):
	    self._id = id
	def write(self, file):
		pass


# Configurations
class XCBuildConfiguration(XCodeNode):
	def __init__(self, name, settings = {}, env=None):
		XCodeNode.__init__(self)
		self.baseConfigurationReference = ""
		self.buildSettings = settings
		self.name = name
		if env and env.ARCH:
			settings['ARCHS'] = " ".join(env.ARCH)


class XCConfigurationList(XCodeNode):
	def __init__(self, settings):
		XCodeNode.__init__(self)
		self.buildConfigurations = settings
		self.defaultConfigurationIsVisible = 0
		self.defaultConfigurationName = settings and settings[0].name or ""

# Group/Files
class PBXFileReference(XCodeNode):
	def __init__(self, name, path, filetype = '', sourcetree = "SOURCE_ROOT"):
		XCodeNode.__init__(self)
		self.fileEncoding = 4
		if not filetype:
			_, ext = os.path.splitext(name)
			filetype = MAP_EXT.get(ext, 'text')
		self.lastKnownFileType = filetype
		self.name = name
		self.path = path
		self.sourceTree = sourcetree

class PBXBuildFile(XCodeNode):
	""" This element indicate a file reference that is used in a PBXBuildPhase (either as an include or resource). """
	def __init__(self, fileRef, settings={}):
		XCodeNode.__init__(self)
		
		# fileRef is a reference to a PBXFileReference object
		self.fileRef = XCID(fileRef._id)

		# A map of key/value pairs for additionnal settings.
		self.settings = settings
		

class PBXGroup(XCodeNode):
	def __init__(self, name, sourcetree = "<group>"):
		XCodeNode.__init__(self)
		self.children = []
		self.name = name
		self.sourceTree = sourcetree

	def add(self, root, sources):
		folders = {}
		def folder(n):
			if not n.is_child_of(root):
				return self
			try:
				return folders[n]
			except KeyError:
				f = PBXGroup(n.name)
				p = folder(n.parent)
				folders[n] = f
				p.children.append(f)
				return f
		for s in sources:
			# f = folder(s.parent)

			source = PBXFileReference(s.name, s.abspath())
			self.children.append(source)
			# f.children.append(source)

# Framework sources
class PBXFrameworksBuildPhase(XCodeNode):
	""" This is the element for the framework link build phase, i.e. linking to frameworks """
	def __init__(self, pbxbuildfiles):
		XCodeNode.__init__(self)
		self.buildActionMask = 2147483647
		self.runOnlyForDeploymentPostprocessing = 0
		self.files = pbxbuildfiles #List of PBXBuildFile (.o, .framework, .dylib)


# Compile Sources
class PBXSourcesBuildPhase(XCodeNode):
	""" Represents the 'Compile Sources' build phase in a Xcode target """
	def __init__(self, buildfiles):
		XCodeNode.__init__(self)
		self.files = buildfiles # List of PBXBuildFile objects

# Targets
class PBXLegacyTarget(XCodeNode):
	def __init__(self, action, target=''):
		XCodeNode.__init__(self)
		self.buildConfigurationList = XCConfigurationList([XCBuildConfiguration('waf', {})])
		if not target:
			self.buildArgumentsString = "%s %s" % (sys.argv[0], action)
		else:
			self.buildArgumentsString = "%s %s --targets=%s" % (sys.argv[0], action, target)
		self.buildPhases = []
		self.buildToolPath = sys.executable
		self.buildWorkingDirectory = ""
		self.dependencies = []
		self.name = target or action
		self.productName = target or action
		self.passBuildSettingsInEnvironment = 0

class PBXShellScriptBuildPhase(XCodeNode):
	def __init__(self, action, target):
		XCodeNode.__init__(self)
		self.buildActionMask = 2147483647
		self.files = []
		self.inputPaths = []
		self.outputPaths = []
		self.runOnlyForDeploymentPostProcessing = 0
		self.shellPath = "/bin/sh"
		self.shellScript = "%s %s %s --targets=%s" % (sys.executable, sys.argv[0], action, target)

class PBXNativeTarget(XCodeNode):
	def __init__(self, action, target, node, buildphases, env, target_type=TARGET_TYPE_APPLICATION):
		XCodeNode.__init__(self)

		buildsettings = env.get_merged_dict()
		buildsettings.update({
			'FRAMEWORK_VERSION': env.VERSION,
			'PRODUCT_NAME':target,
			'CONFIGURATION_BUILD_DIR':node.parent.abspath(),
			'HEADER_SEARCH_PATHS': ' '.join(env.HEADER_SEARCH_PATHS)
		})

		product_type = target_type[0]
		file_type = target_type[1]

		conf = XCBuildConfiguration(env.CONFIG_NAME, buildsettings, env)
		self.buildConfigurationList = XCConfigurationList([conf])
		self.buildPhases = buildphases #[PBXShellScriptBuildPhase(action, target)]
		self.buildRules = []
		self.dependencies = []
		self.name = target
		self.productName = target
		self.productType = product_type # See TARGET_TYPE_ tuples constants
		self.productReference = PBXFileReference(target, node.abspath(), file_type, 'CONFIGURATION_BUILD_DIR')

# Root project object
class PBXProject(XCodeNode):
	def __init__(self, name, version):
		XCodeNode.__init__(self)
		self.buildConfigurationList = XCConfigurationList([XCBuildConfiguration('waf', {})])
		self.compatibilityVersion = version[0]
		self.hasScannedForEncodings = 1;
		self.mainGroup = PBXGroup(name)
		self.projectRoot = ""
		self.projectDirPath = ""
		self.targets = []
		self._objectVersion = version[1]
		self._output = PBXGroup('Products')
		self.mainGroup.children.append(self._output)

	def write(self, file):
		w = file.write
		w("// !$*UTF8*$!\n")
		w("{\n")
		w("\tarchiveVersion = 1;\n")
		w("\tclasses = {\n")
		w("\t};\n")
		w("\tobjectVersion = %d;\n" % self._objectVersion)
		w("\tobjects = {\n\n")

		XCodeNode.write(self, file)

		w("\t};\n")
		w("\trootObject = %s;\n" % self._id)
		w("}\n")

	def add_task_gen(self, target):
		self.targets.append(target)
		# self._output.children.append(target.productReference._id)

class xcode(Build.BuildContext):
	cmd = 'xcode'
	fun = 'build'

	def collect_source(self, tg):
		source_files = tg.to_nodes(getattr(tg, 'source', []))
		plist_files = tg.to_nodes(getattr(tg, 'mac_plist', []))
		resource_files = [tg.path.find_node(i) for i in Utils.to_list(getattr(tg, 'mac_resources', []))]
		include_dirs = Utils.to_list(getattr(tg, 'includes', [])) + Utils.to_list(getattr(tg, 'export_dirs', []))
		include_files = []
		for x in include_dirs:
			if not isinstance(x, str):
				include_files.append(x)
				continue
			d = tg.path.find_node(x)
			if d:
				lst = [y for y in d.ant_glob(HEADERS_GLOB, flat=False)]
				include_files.extend(lst)

		tg.env.append_value('HEADER_SEARCH_PATHS', [node.parent.abspath() for node in include_files])

		# remove duplicates
		source = list(set(source_files + plist_files + resource_files + include_files))
		source.sort(key=lambda x: x.abspath())
		return source

	def execute(self):
		"""
		Entry point
		"""
		self.restore()
		if not self.all_envs:
			self.load_envs()
		self.recurse([self.run_dir])

		appname = getattr(Context.g_module, Context.APPNAME, os.path.basename(self.srcnode.abspath()))
		p = PBXProject(appname, ('Xcode 3.2', 46))

		for g in self.groups:
			for tg in g:
				if not isinstance(tg, TaskGen.task_gen):
					continue

				tg.post()

				#features = Utils.to_list(getattr(tg, 'features', ''))


				group = PBXGroup(tg.name)
				group.add(tg.path, self.collect_source(tg))
				p.mainGroup.children.append(group)

			#	if ('cprogram' in features) or ('cxxprogram' in features):
			#	p.add_task_gen(tg)

				# if not getattr(tg, 'mac_app', False):
				# 	self.targets.append(PBXLegacyTarget('build', tg.name))
				if hasattr(tg, 'target_type'):
					file_ext = tg.target_type[2]
					node = tg.path.find_or_declare(tg.name+file_ext)
					buildfiles = [PBXBuildFile(fileref) for fileref in group.children]
					compilesources = PBXSourcesBuildPhase(buildfiles)
					framework = PBXFrameworksBuildPhase(buildfiles)
					target = PBXNativeTarget('build', tg.name, node, [compilesources], tg.env, tg.target_type)
					p.add_task_gen(target)
					# p.mainGroup.children.append(PBXBuildFile(target.productReference))
				# else:
				# 	node = tg.path.find_or_declare(tg.name+file_ext)
				# 	buildfiles = [PBXBuildFile(fileref) for fileref in group.children]
				# 	compilesources = PBXSourcesBuildPhase(buildfiles)
				# 	target = PBXNativeTarget('build', tg.name, node, [compilesources], tg.env)
				# 	p.add_task_gen(target)

		node = self.bldnode.make_node('%s.xcodeproj' % appname)
		node.mkdir()
		node = node.make_node('project.pbxproj')
		p.write(open(node.abspath(), 'w'))


