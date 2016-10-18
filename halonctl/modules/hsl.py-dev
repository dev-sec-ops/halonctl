from __future__ import print_function
import sys
import os
import re
import six
import difflib
from jinja2 import Template
from textwrap import dedent
from blessings import Terminal
from halonctl.config import config
from halonctl.modapi import Module
from halonctl.roles import HTTPStatus
from halonctl.util import from_base64, to_base64, ask_confirm

FRAGMENTS = [
	'system_authentication_script',
	'transport_flow',
	'queue_flow',
]
MIMES = {
	'text/plain': 'txt',
	'text/csv': 'csv',
}
SCRIPT_RE = re.compile(r'\w+_flow__\d+')

t = Terminal()



class BaseFile(object):
	filename = u'unnamed'
	extension = u'bin'
	
	name = None
	meta = None
	body = u''
	
	@property
	def full_filename(self):
		return u"{0}.{1}".format(self.filename, self.extension)
	
	
	
	@classmethod
	def from_file(class_, path):
		f = class_()
		f.load(path)
		return f
	
	
	
	def __init__(self, item=None):
		if item:
			self.load_data(item)
	
	def load_data(self, item):
		'''Loads data from a configKeys() SOAP payload.'''
		pass
	
	def to_data(self):
		'''Returns a dictionary of key:value pairs for configKeySet().'''
		pass
	
	def deserialize(self, data):
		'''Deserializes data read from a file.'''
		lines = data.split('\n')
		if lines[0].startswith('//= NAME: '):
			self.name = lines.pop(0)[10:]
		if lines[0].startswith('//= META: '):
			self.meta = lines.pop(0)[10:]
		self.body = u'\n'.join(lines)
	
	def serialize(self, node=None):
		'''Serializes data for writing to a file.'''
		data = u""
		if self.name:
			data += u"//= NAME: {0}\n".format(self.name)
		if self.meta:
			data += u"//= META: {0}\n".format(self.meta)
		data += self.render(node)
		return data
	
	def path(self, args):
		'''Constructs a local path to the file.'''
		return os.path.join(args.path, self.full_filename)
	
	def save(self, args):
		#Avoid saving empty files
		if not self.body:
			return None
		
		if not os.path.exists(args.path):
			os.makedirs(args.path)
		
		with open(self.path(args), 'w') as f:
			f.write(self.serialize())
	
	def load(self, path):
		with open(path) as f:
			pts = os.path.splitext(os.path.basename(path))
			self.filename, self.extension = pts[0], pts[1][1:]
			self.deserialize(f.read())
	
	def diff(self, other, from_='', to='', node=None):
		if self.serialize(node) == other.serialize(node):
			return []
		
		return difflib.unified_diff(
			self.serialize().split('\n'),
			other.serialize().split('\n'),
			from_, to, lineterm=''
		)
	
	def render(self, node=None):
		if not node:
			return self.body
		
		return Template(self.body).render(node=node)

class ScriptFile(BaseFile):
	extension = 'hsl'
	
	def load_data(self, item):
		self.filename = item.name
		self.name = item.params.item[0]
		try:
			self.body = self.decode(item.params.item[-1])
		except AttributeError as e:
			#Any empty scriptfile will cause an Attributerror
			print(u"Notice: empty config \"{0}\" found".format(item.name), file=sys.stderr)
			self.body = None
		
		# Some kinds of scripts (ACL Flows) have an extra middle parameter...
		if len(item.params.item) > 2:
			self.meta = item.params.item[1]
	
	def to_data(self, node=None):
		def encode_script(lines):
			txt = u'\n'.join(lines)
			return u'script "{0}"'.format(to_base64(txt))
		
		items = { 'name': self.name }
		if self.meta:
			items['rate'] = self.meta
		
		body = self.render(node)
		blocks = []
		current_script = []
		for line in body.split('\n'):
			if line.startswith('//= '):
				if current_script:
					blocks.append(encode_script(current_script))
					current_script = []
				blocks.append(line[4:])
			else:
				current_script.append(line)
		if current_script:
			blocks.append(encode_script(current_script))
		items['flow'] = u','.join(blocks)
		
		return items
	
	def decode(self, data):
		body = ''
		for block in data.split(','):
			if block.startswith('script '):
				body += u'{0}\n'.format(from_base64(block[8:-1]))
			else:
				body += u'//= {0}\n'.format(block)
		return body

class FragmentFile(BaseFile):
	extension = 'hsl'
	
	def load_data(self, item):
		self.filename = item.name
		self.body = from_base64(item.params.item[0])
	
	def to_data(self, node=None):
		return {
			'value': to_base64(self.render(node))
		}

class TextFile(BaseFile):
	extension = 'txt'
	
	def load_data(self, item):
		self.filename = item.name
		self.extension = MIMES.get(item.params.item[1], 'bin')
		self.name = item.params.item[0]
		self.body = from_base64(item.params.item[2])
	
	def to_data(self, node=None):
		mime = 'text/plain'
		for t, ext in six.iteritems(MIMES):
			if ext == self.extension:
				mime = t
		
		return {
			'name': self.name,
			'type': mime,
			'data': to_base64(self.render(node)),
		}

def files_from_result(result, ignore=[]):
	for item in result.item:
		if item.name in ignore:
			continue
		elif SCRIPT_RE.match(item.name):
			yield ScriptFile(item)
		elif item.name in FRAGMENTS:
			yield FragmentFile(item)
		elif item.name.startswith('file__'):
			yield TextFile(item)

def files_from_storage(path, ignore=[]):
	for filename in os.listdir(path):
		basename = os.path.splitext(filename)[0]
		filepath = os.path.join(path, filename)
		if basename in ignore:
			continue
		elif SCRIPT_RE.match(basename):
			yield ScriptFile.from_file(filepath)
		elif basename in FRAGMENTS:
			yield FragmentFile.from_file(filepath)
		elif basename.startswith('file__'):
			yield TextFile.from_file(filepath)

def load_ignore_list(path):
	ignore_path = os.path.join(path, '_ignore')
	if os.path.exists(ignore_path):
		with open(ignore_path, 'rU') as f:
			return f.read().split('\n')
	return []

def print_diff(diff):
	print(t.bold(diff[0]))
	print(t.bold(diff[1]))
	print(t.bold(diff[2]))
	for line in diff[3:]:
		if line.startswith('+'):
			print(t.green(line))
		elif line.startswith('-'):
			print(t.red(line))
		else:
			print(line)

def confirm_diff(diff, args):
	'''Asks the user to confirm a diff application.'''
	while True:
		a = 'y' if args.force else six.moves.input(t.cyan(u"Apply patch [y/n/q/?]? "))
		if a == '?':
			print(t.magenta(dedent(u'''
			y - apply this patch
			n - do not apply this patch
			q - quit; do not apply this or any subsequent patch
			? - display a help message
			''').strip()))
			continue
		elif a in ['y', 'n', 'q']:
			return a



class HSLDumpModule(Module):
	'''Dumps scripts from a node'''
	
	def register_arguments(self, parser):
		parser.add_argument('path', nargs='?', default='.',
			help=u"node configuration directory")
	
	def run(self, nodes, args):
		# It doesn't make sense to dump from multiple nodes into one directory
		node = nodes[0]
		code, result = node.service.configKeys()
		ignore = load_ignore_list(args.path)
		
		if code != 200:
			self.exitcode = 1
			return HTTPStatus(code)
		
		for f in files_from_result(result, ignore):
			f.save(args)

class HSLDiffModule(Module):
	'''Views differences between local and remote files.'''
	
	def register_arguments(self, parser):
		parser.add_argument('path', nargs='?', default='.',
			help=u"node configuration directory")
	
	def run(self, nodes, args):
		ignore = load_ignore_list(args.path)
		local = { f.full_filename: f for f in files_from_storage(args.path, ignore) }
		
		diffs = {}
		for node, (code, result) in six.iteritems(nodes.service.configKeys()):
			if code != 200:
				print(u"{0}: {1}".format(node, HTTPStatus(code).human()))
				self.partial = True
				continue
			
			for f in files_from_result(result, ignore):
				f2 = local.get(f.full_filename, BaseFile())
				diff = list(f.diff(f2, node.name, f.full_filename))
				if diff:
					print_diff(diff)

class HSLPullModule(Module):
	'''Merges remote changes into local files.'''
	
	def register_arguments(self, parser):
		parser.add_argument('path', nargs='?', default='.',
			help=u"node configuration directory")
		parser.add_argument('-f', '--force', action='store_true',
			help=u"apply changes without confirmation")
	
	def run(self, nodes, args):
		ignore = load_ignore_list(args.path)
		local = { f.full_filename: f for f in files_from_storage(args.path, ignore) }
		
		for node, (code, result) in six.iteritems(nodes.service.configKeys()):
			if code != 200:
				print(u"{0}: {1}".format(node, HTTPStatus(code).human()))
				self.partial = True
				continue
			
			for f in files_from_result(result, ignore):
				f2 = local.get(f.full_filename, BaseFile())
				diff = list(f2.diff(f, f.full_filename, node.name, node=node))
				if diff:
					print_diff(diff)
					a = confirm_diff(diff, args)
					if a == 'y':
						f.save(args)
					elif a == 'n':
						continue
					elif a == 'q':
						return

class HSLPushModule(Module):
	'''Pushes local scripts to nodes.'''
	
	def register_arguments(self, parser):
		parser.add_argument('path', nargs='?', default='.',
			help=u"node configuration directory")
		parser.add_argument('-f', '--force', action='store_true',
			help=u"allow application of changes to all nodes")
	
	def run(self, nodes, args):
		if len(nodes) == len(config['nodes']) and not args.force:
			if not ask_confirm(dedent(u'''
				{b}Warning:{n}
				
				Looks like you're about to push a configuration change to {b}all{n} of your
				nodes! If any of them are clustered, this is probably not what you want.
				
				If the configuration change is written to multiple nodes in a cluster, each node
				will push it out to its entire cluster, one after another, and each push will
				cause every node in the cluster to recompile its configuration. If you're
				pushing to an entire large cluster, this can cause excessive amounts of system
				load across it!
				
				To silence this warning in the future, use the {b}-f{n} ({b}--force{n}) flag.
				
				Do you want to proceed?
				'''.format(b=t.bold, n=t.normal)).strip(), default=False):
				return
		
		ignore = load_ignore_list(args.path)
		local = { f.full_filename: f for f in files_from_storage(args.path, ignore) }
		
		for node, (code, result) in six.iteritems(nodes.service.configKeys()):
			if code != 200:
				print(u"{0}: {1}".format(node, HTTPStatus(code).human()))
				self.partial = True
				continue
			
			for f in files_from_result(result, ignore):
				if not f.full_filename in local:
					continue
				
				f2 = local[f.full_filename]
				diff = list(f.diff(f2, node.name, f2.full_filename, node=node))
				if diff:
					print_diff(diff)
					a = confirm_diff(diff, args)
					if a == 'y':
						d = f2.to_data(node)
						code, result = node.service.configKeySet(key=f2.filename, params={
							'item': [{'first': k, 'second': v} for k, v in six.iteritems(d)]
						})
						if code != 200:
							print(u"Failed to apply patch: {0}".format(result.faultstring), file=sys.stderr)
							self.exitcode = 2
							return
					elif a == 'n':
						continue
					elif a == 'q':
						return

class HSLModule(Module):
	'''Manages HSL scripts'''
	
	submodules = {
		'dump': HSLDumpModule(),
		'diff': HSLDiffModule(),
		'pull': HSLPullModule(),
		'push': HSLPushModule(),
	}

module = HSLModule()
