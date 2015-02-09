#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
import six
import os, sys
import inspect
import pkgutil
import importlib
import argparse
import json
import logging
import arrow
import requests
from natsort import natsorted
from .models import *
from .util import *
from . import cache
from . import config as g_config

# Figure out where this script is, and change the PATH appropriately
BASE = os.path.abspath(os.path.dirname(sys.modules[__name__].__file__))
sys.path.insert(0, BASE)

# Create an argument parser
parser = argparse.ArgumentParser(description="Easily manage Halon nodes and clusters.")
subparsers = parser.add_subparsers(title='subcommands', dest='_mod_name', metavar='cmd')
subparsers.required = True

# All available modules and output formatters
modules = {}
formatters = {}

# Loaded configuration, configured nodes and clusters
config = {}
nodes = {}
clusters = {}

# Disable unverified HTTPS warnings - we know what we're doing
requests.packages.urllib3.disable_warnings()



def load_modules():
	'''Load all modules from the 'modules' directory.'''
	
	# Figure out where all the modules are, then treat it as a package,
	# iterating over its modules and attempting to load each of them. The
	# 'module' variable in the imported module is the module instance to use -
	# register that with the application. Yay, dynamic loading abuse.
	modules_path = os.path.join(BASE, 'modules')
	for loader, name, ispkg in pkgutil.iter_modules(path=[modules_path]):
		mod = loader.find_module(name).load_module(name)
		if hasattr(mod, 'module'):
			register_module(name.rstrip('_'), mod.module)
		else:
			print("Ignoring invalid module (missing 'module' variable): {name}".format(name=name))

def load_formatters():
	'''Load all formatters from the 'formatters' directory.'''
	
	formatters_path = os.path.join(BASE, 'formatters')
	for loader, name, ispkg in pkgutil.iter_modules(path=[formatters_path]):
		fmt = loader.find_module(name).load_module(name)
		if hasattr(fmt, 'format'):
			formatters[name.rstrip('_')] = fmt.format
		else:
			print("Ignoring invalid formatter (missing 'format' member): {name}".format(name))

def register_module(name, mod):
	'''Registers a loaded module instance'''
	
	p = subparsers.add_parser(name, help=mod.__doc__)
	p.set_defaults(_mod=mod)
	mod.register_arguments(p)
	modules[name] = mod

def open_config():
	'''Opens a configuration file from the first found default location.'''
	
	config_paths = [
		os.path.abspath(os.path.join(BASE, '..', 'halonctl.json')),
		os.path.expanduser('~/.config/halonctl.json'),
		os.path.expanduser('~/halonctl.json'),
		os.path.expanduser('~/.halonctl.json'),
		'/etc/halonctl.json',
	]
	
	config_path = None
	for p in config_paths:
		if os.path.exists(p):
			config_path = p
			break
	
	if not config_path:
		print("No configuration file found!")
		print("")
		print("Please create one in one of the following locations:")
		print("")
		for p in config_paths:
			print("  - {0}".format(p))
		print("")
		print("Or use the -C/--config flag to specify a path.")
		print("A sample config can be found at:")
		print("")
		print("  - {0}".format(os.path.abspath(os.path.join(BASE, 'halonctl.sample.json'))))
		print("")
		sys.exit(1)
	
	return open(config_path, 'rU')

def load_config(f):
	'''Loads configuration data from a given file.'''
	
	try:
		conf = json.load(f, encoding='utf-8')
	except ValueError as e:
		sys.exit("Configuration Syntax Error: " + str(e))
	
	f.close()
	g_config.config.update(conf)
	return conf

def process_config(config, preload_wsdl=False):
	'''Processes a configuration dictionary into usable components.'''
	
	nodes = { name: Node(data, name) for name, data in six.iteritems(config.get('nodes', {})) }
	clusters = {}
	
	if preload_wsdl:
		download_wsdl(six.itervalues(nodes), verify=config.get('verify_ssl', True))
		async_dispatch({ node: (node.load_wsdl,) for node in six.itervalues(nodes) })
	
	for name, data in six.iteritems(config.get('clusters', {})):
		cluster = NodeList()
		cluster.name = name
		cluster.load_data(data)
		
		for nid in data['nodes'] if isinstance(data, dict) else data:
			if not nid in nodes:
				sys.exit("Configuration Error: Cluster '{cid}' references nonexistent node '{nid}'".format(cid=cluster.name, nid=nid))
			node = nodes[nid]
			node.cluster = cluster
			cluster.append(node)
		
		clusters[cluster.name] = cluster
	
	return (nodes, clusters)

def apply_slice(list_, slice_):
	if not slice_:
		return list_
	
	offsets = [-1, 0, 0]
	parts = [int(p) + offsets[i] if p else None for i, p in enumerate(slice_.split(':'))]
	return list_[slice(*parts)] if len(parts) > 1 else [list_[parts[0]]]

def apply_filter(available_nodes, available_clusters, nodes, clusters, slice_=''):
	targets = []
	
	if len(nodes) == 0 and len(clusters) == 0:
		targets = apply_slice(available_nodes.values(), slice_)
	elif len(clusters) > 0:
		for cid in clusters:
			targets += apply_slice(available_clusters[cid], slice_)
	
	if len(nodes) > 0:
		targets += [available_nodes[nid] for nid in nodes]
	
	return NodeList(natsorted(targets, key=lambda t: [t.cluster.name, t.name]))

def download_wsdl(nodes, verify):
	path = cache.get_path('wsdl.xml')
	min_mtime = arrow.utcnow().replace(hours=-12)
	if not os.path.exists(path) or arrow.get(os.path.getmtime(path)) < min_mtime:
		has_been_downloaded = False
		for node in nodes:
			try:
				r = requests.get("{scheme}://{host}/remote/?wsdl".format(scheme=node.scheme, host=node.host), stream=True, verify=verify)
				if r.status_code == 200:
					with open(path, 'wb') as f:
						for chunk in r.iter_content(256):
							f.write(chunk)
					has_been_downloaded = True
					break
			except requests.exceptions.SSLError:
				print_ssl_error(node)
				sys.exit(1)
			except:
				pass
		
		if not has_been_downloaded:
			sys.exit("None of your nodes are available, can't download WSDL")



def main():
	# Configure logging
	logging.basicConfig(level=logging.ERROR)
	logging.getLogger('suds.client').setLevel(logging.CRITICAL)
	
	# Load modules and formatters
	load_modules()
	load_formatters()
	
	# Add parser arguments
	parser.add_argument('-C', '--config', type=argparse.FileType('rU'),
		help="use specified configuration file")
	
	parser.add_argument('-n', '--node', dest='nodes', action='append', metavar="NODES",
		default=[], help="target nodes")
	parser.add_argument('-c', '--cluster', dest='clusters', action='append', metavar="CLUSTERS",
		default=[], help="target clusters")
	parser.add_argument('-s', '--slice', dest='slice',
		default='', help="slicing, as a Python slice expression")
	
	parser.add_argument('-i', '--ignore-partial', action='store_true',
		help="exit normally even for partial results")
	parser.add_argument('-f', '--format', choices=formatters.keys(), default='table',
		help="use the specified output format (default: table)")
	
	# Parse!
	args = parser.parse_args()
	
	# Load configuration
	config = load_config(args.config or open_config())
	nodes, clusters = process_config(config, preload_wsdl=True)
	
	# Validate cluster and node choices
	invalid_clusters = [cid for cid in args.clusters if not cid in clusters]
	if invalid_clusters:
		print("Unknown clusters: {0}".format(', '.join(invalid_clusters)))
		print("Available: {0}".format(', '.join(clusters.iterkeys())))
		sys.exit(1)
	
	invalid_nodes = [nid for nid in args.nodes if not nid in nodes]
	if invalid_nodes:
		print("Unknown nodes: {0}".format(', '.join(invalid_nodes)))
		print("Available: {0}".format(', '.join(nodes.iterkeys())))
		sys.exit(1)
	
	# Filter nodes to choices
	target_nodes = apply_filter(nodes, clusters, args.nodes, args.clusters, args.slice)
	
	# Run the selected module
	mod = args._mod
	retval = mod.run(target_nodes, args)
	
	# Normalize generator mods into lists
	if inspect.isgenerator(retval):
		retval = list(retval)
	
	# Print something, if there's anything to print
	if retval:
		if hasattr(retval, 'draw'):
			print(retval.draw())
		else:
			print(formatters[args.format](retval))
	
	# Let the module decide the exit code - either by explicitly setting it, or
	# by marking the result as partial, in which case a standard exit code is
	# returned unless the user has requested partial results to be ignored
	if mod.exitcode != 0:
		sys.exit(mod.exitcode)
	elif mod.partial and not args.ignore_partial:
		sys.exit(99)

if __name__ == '__main__':
	main()
