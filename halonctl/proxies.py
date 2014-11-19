import signal
import inspect
import requests
from base64 import b64encode, b64decode
from halonctl.util import async_dispatch, nodesort



class NodeSoapProxy(object):
	'''SOAP call proxy.
	
	This allows you to make SOAP calls as easily as calling a normal Python
	function.
	
	Returns a tuple of ``( status, response )``.
	
	Example::
	
		status, response = node.myCall(param='abc')
		if status != 200:
			# ... the call failed, handle the error ...
			print "Error: " + status
		
		print response
	'''
	
	def __init__(self, node):
		self.node = node
	
	def __getattr__(self, name):
		def _soap_proxy_executor(*args, **kwargs):
			context = self.node.make_request(name, *args, **kwargs)
			try:
				r = requests.post(context.client.location(),
					auth=(self.node.username, self.node.password),
					headers=context.client.headers(), data=context.envelope,
					timeout=10)
				return context.process_reply(r.text, r.status_code, r.reason)
			except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
				return (0, None)
		
		return _soap_proxy_executor

class NodeListSoapProxy(object):
	'''Multi-node SOAP call proxy.
	
	Similar to NodeSoapProxy, this allows you to easily make SOAP calls, but
	additionally, these calls are made asynchronously to any number of nodes,
	taking only as long to return as the slowest node takes to answer.
	
	Returns a dictionary of ``{ node: (status, response) }``.
	
	Example::
	
		for node, result in nodes.myCall(param='abc').iteritems():
			# result[0] is the response status; 200 = Success
			if result[0] != 200:
				# ... the call failed, handle the error ...
				print "Error: " + status
				continue
			
			# result[1] is the response data
			print "{node}: {result}".format(node=node, result=result[1])
	
	'''
	
	def __init__(self, nodelist):
		self.nodelist = nodelist
	
	def __getattr__(self, name):
		def _soap_proxy_executor(*args, **kwargs):
			return nodesort(async_dispatch({node: (getattr(node.service, name), args, kwargs) for node in self.nodelist}))
		return _soap_proxy_executor

class CommandProxy(object):
	'''Proxy for a command executing on a remote server.
	
	This abstracts away all the messy ``commandRun()``/``commandPoll()`` logic,
	letting you treat a remote process as an interactive iterator.
	
	For example, this will print command output as it arrives::
	
		cmd = node.command('mycommand')
		for chunk in cmd:
			print chunk
	
	'''
	
	done = False
	
	def __init__(self, node, cid):
		self.node = node
		self.cid = cid
	
	def __iter__(self):
		return self
	
	# Python 3 compatibility
	def __next__(self):
		return self.next()
	
	def next(self):
		'''Returns a chunk of the remote process' stdout. Lets you treat this
		object as an iterator.'''
		
		while True:
			code, data = self.read()
			
			if code == 200:
				return data
			else:
				self.done = True
				raise StopIteration()
	
	def all(self):
		'''Waits for the process to exit, and returns all of its output.'''
		
		return ''.join(self)
	
	def read(self):
		'''Reads some data from the remote process' stdin'''
		
		code, res = self.node.service.commandPoll(commandid=self.cid)
		if code != 200:
			self.done = True
		
		return (code, ''.join([b64decode(item) for item in res.item]) if hasattr(res, 'item') else res)
	
	def write(self, data):
		'''Writes some data to the remote process' stdin.'''
		
		code, res = self.node.service.commandPush(commandid=self.cid, data=b64encode(data))
		if code != 200:
			self.done = True
		
		return code, res
	
	def signal(self, sigid):
		'''Sends a signal to the remote process.
		
		The signal can be specified either as a signal number (eg. 15) or a
		signal name (eg. SIGTERM).'''
		
		try:
			# This will raise a ValueError if the string is not numeric
			sig = int(sigid)
		except ValueError:
			# If it's not, try to get the signal by name from the signal module
			sig = int(getattr(signal, sigid.upper()))
		
		code, res = self.node.service.commandSignal(commandid=self.cid, signal=sig)
		if code != 200:
			self.done = True
		
		return code, res
	
	def stop(self):
		'''Terminates the remote process.'''
		
		self.done = True
		return self.node.service.commandStop(commandid=self.cid)
	
	def __str__(self):
		return self.all()
