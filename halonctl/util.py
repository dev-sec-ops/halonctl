from __future__ import print_function
import six
import sys
import re
import datetime
import arrow
from base64 import b64decode, b64encode
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, wait
from dateutil import tz
from natsort import natsorted
from .config import config

executor = ThreadPoolExecutor(64)

def async_dispatch(tasks):
	'''Dispatches jobs into a thread pool.
	
	This will take a set of jobs as a dictionary in the form::
	
	    { 'key': (callable, args, kwargs) }
	
	And dispatch it into a thread pool, completing the tasks asynchronously,
	and returning the results. This will take as long as the slowest job.'''
	
	futures = {
		executor.submit(v[0], *(v[1] if len(v) >= 2 else []), **(v[2] if len(v) >= 3 else {})): k
		for k, v in six.iteritems(tasks)
	}
	done, not_done = wait(futures)
	
	return { futures[future]: future.result() for future in done }

def nodesort(nodes):
	'''Sorts a dictionary of nodes into an OrderedDict, by cluster and name.'''
	
	return OrderedDict(natsorted(list(nodes.items()), key=lambda t: [t[0].cluster.name, t[0].name]))

def ask_confirm(prompt, default=True):
	'''Ask the user for confirmation.
	
	This prompts the user to answer either y/yes or n/no, with a default for if
	they just hit Enter.
	
	The question is presented as "Prompt [Yn]" or
	"Prompt [yN]", depending on the default answer, similar to for instance
	Debian's ``apt-get`` command. It will repeat until a valid answer is given.
	
	:rtype: bool
	'''
	if type(default) != bool:
		raise TypeError("The default value for ask_confirm must be a bool!")
	
	answers = {
		u"y": True, u"yes": True,
		u"n": False, u"no": False,
		u"": default
	}
	suffixes = { True: u"[Yn]", False: u"[yN]" }
	
	while True:
		print(u"{prompt} {suffix} ".format(prompt=prompt, suffix=suffixes[default]), file=sys.stderr, end='')
		answer = six.moves.input().lower()
		if not answer in answers:
			print(u"Enter either y/yes or n/no, or nothing for default ({0})".format(u"yes" if default else u"no"), file=sys.stderr)
			continue
		return answers[answer]

def get_date(s, timezone=0):
	'''Returns a timezone-adjusted date as an arrow object.'''
	return arrow.get(arrow.get(s).naive, tz.tzoffset(None, timezone*60*60 if timezone else 0))

filter_timestamp_re = re.compile(r'\{([^}]*)\}')
def hql_from_filters(filters, timezone=0):
	'''Gets a HQL statement from a list of filter components.
	
	Filter components may include ``{YYYY-MM-DD HH:MM:SS}`` placeholders, which
	are interpreted according to the given timezone and replaced with UTC
	timestamps.
	
	:param list filters: A list of filters to glue together
	:param int timezone: The UTC offset of the assumed timezone
	'''
	conditions = []
	for s in filters:
		s = filter_timestamp_re.sub(lambda m: str(get_date(m.groups(0)[0], timezone).timestamp), s)
		conditions.append(s)
	
	return u" ".join(conditions)

def from_base64(s):
	'''Decodes a Base64-encoded string.
	
	This exists because base64.b64decode doesn't take strings in Python 3, and
	there's an awful lot of boilerplate with encodings and handling Nones.'''
	
	return u"" if not s else b64decode(s.encode('utf8', 'replace')).decode('utf-8', 'replace')

def to_base64(s):
	'''Encodes a unicode string as Base64.
	
	This exists because base64.b64decode doesn't take strings in Python 3, and
	there's an awful lot of boilerplate with encodings and handling Nones.'''
	
	return u"" if not s else b64encode(s.encode('utf8', 'replace')).decode('utf-8', 'replace')

def textualize(item, raw=False):
	'''
	Performs output conversion of the given item.
	
	It currently has converters for:
	
	* ``None``, ``True``, ``False``
	* `datetime.timedelta <https://docs.python.org/2/library/datetime.html#timedelta-objects>`_
	
	:param bool raw: Whether to format for machines rather than humans
	'''
	if item is None:
		return u"-" if not raw else None
	elif item is True:
		return u"Yes" if not raw else True
	elif item is False:
		return u"No" if not raw else False
	elif isinstance(item, datetime.timedelta):
		if not raw:
			s = u""
			if item > datetime.timedelta(days=1):
				s += u"{d}d "
			if item > datetime.timedelta(hours=1):
				s += u"{h}h "
			if item > datetime.timedelta(minutes=1):
				s += u"{m}m "
			return s.rstrip().format(d=item.days, h=item.seconds // 3600, m=(item.seconds // 60) % 60)
		else:
			return int(item.total_seconds())
	return six.text_type(item)

def print_ssl_error(node):
	print(u"ERROR: Couldn't contact '{nid}': SSL verification failed!".format(nid=node.name), file=sys.stderr)
	print(u"", file=sys.stderr)
	print(u"If you'd like to disable SSL verification, add this to your config:", file=sys.stderr)
	print(u"    \"verify_ssl\": false", file=sys.stderr)
	print(u"", file=sys.stderr)
	print(u"Or, if you're using a self-signed certificate, add this instead:", file=sys.stderr)
	print(u"    \"verify_ssl\": \"/path/to/my/cert.pem\"", file=sys.stderr)
	print(u"", file=sys.stderr)
	print(u"You can also connect over plain HTTP by adjusting your node definition.", file=sys.stderr)
	print(u"", file=sys.stderr)
