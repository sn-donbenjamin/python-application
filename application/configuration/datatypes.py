# Copyright (C) 2005-2006 Dan Pascu <dan@ag-projects.com>
#

"""Provide basic data types to interpret entries in the configuration file"""


__all__ = ['Boolean', 'StringList', 'IPAddress', 'Hostname', 'HostnameList',
           'NetworkRange', 'NetworkRangeList', 'ControlSocket',
           'NetworkAddress', 'EndpointAddress']

import socket
import re
import struct

from application import log


class Boolean(int):
    """A boolean value that handles multiple boolean input keywords"""
    __states = {'1': True, 'yes': True, 'true': True, 'on': True, 1: True, True: True,
                '0': False, 'no': False, 'false': False, 'off': False, 0: False, False: False}
    __objects = {} ## We want True and False to be singletons. Store them here.
    def __new__(typ, value):
        try: 
            value + 0
        except:
            try: value + ''
            except: raise TypeError, 'value should be a string'
            else: val = value.lower()
        else:
            val = value # eventually we can accept any int value by using 'not not value'
        try:
            state = Boolean.__states[val]
        except KeyError:
            raise ValueError, 'not a boolean: %s' % value
        if not state in Boolean.__objects:
            Boolean.__objects[state] = int.__new__(typ, state)
        return Boolean.__objects[state]
    def __repr__(self): return (self and 'True') or 'False'
    __str__ = __repr__


class StringList(list):
    """A list of strings"""
    def __new__(typ, value):
        if value.lower() in ('none', ''):
            return []
        return re.split(r'\s*,\s*', value)

class IPAddress(str):
    """An IP address"""
    def __new__(typ, value):
        try:
            socket.inet_aton(value)
        except socket.error:
            raise ValueError("invalid IP address: %r" % value)
        return str(value)

class Hostname(str):
    """A Hostname or an IP address. The keyword `Any' is accepted in place of '0.0.0.0' """
    def __new__(typ, value):
        if value.lower() == 'any':
            return '0.0.0.0'
        try:
            socket.inet_aton(socket.gethostbyname(value))
        except (socket.error, socket.gaierror):
            raise ValueError("invalid hostname or IP address: %r" % value)
        return str(value)

class HostnameList(list):
    """A list of hostnames"""
    def __new__(typ, description):
        if description.lower()=='none':
            return []
        lst = re.split(r'\s*,\s*', description)
        hosts = []
        for x in lst:
            try:
                host = Hostname(x)
            except ValueError, why:
                log.warn("%s (ignored)" % why)
            else:
                hosts.append(host)
        return hosts

class NetworkRange(tuple):
    """
    Describes a network address range in the form of: (base_address, network_mask)

    Input should be a string in the form of:
        - network/mask
        - ip_address
        - hostname
    in the latter two cases a mask of 32 is assumed.
    Except the hostname case, where a DNS name is present, in the other cases
    the address should be in quad dotted number notation.
    Mask is number between 0 and 32 (bits used by the network part of address)
    On error ValueError is raised.
    """
    def __new__(typ, description):
        if not description or description.lower()=='none':
            return (0L, 0xFFFFFFFFL)
        if description.lower()=='any':
            return (0L, 0L) ## This is the any address 0.0.0.0
        match = re.search(r'^(?P<net>.+?)/(?P<bits>\d+)$', description)
        if match:
            net     = match.group('net')
            netbits = int(match.group('bits'))
        else:
            try:
                net = socket.gethostbyname(description) # if not a net/mask it may be a host or ip
            except socket.gaierror:
                raise NameError, "invalid hostname or IP address: '%s'" % description
            netbits = 32
        if netbits < 0 or netbits > 32:
            raise ValueError, "invalid network mask in address: '%s' (should be between 0 and 32)" % description
        try:
            netaddr = socket.inet_aton(net)
        except:
            raise ValueError, "invalid IP address: '%s'" % net
        mask = (0xFFFFFFFFL << 32-netbits) & 0xFFFFFFFFL
        #mask = (-1L << 32-netbits) & 0xFFFFFFFFL
        #mask = ((1L << netbits) - 1) << 32-netbits
        netbase = struct.unpack('!L', netaddr)[0] & mask
        return (netbase, mask)

class NetworkRangeList(list):
    """A list of NetworkRange objects"""
    def __new__(typ, description):
        if description.lower()=='none':
            return None
        lst = re.split(r'\s*,\s*', description)
        ranges = []
        for x in lst:
            try:
                range = NetworkRange(x)
            except NameError:
                log.warn("couldn't resolve hostname: `%s' (ignored)" % x)
            except ValueError:
                log.warn("Invalid network specification: `%s' (ignored)" % x)
            else:
                ranges.append(range)
        return ranges or None

class ControlSocket(str):
    """A UNIX filesystem socket or None"""
    def __new__(typ, value):
        if value.lower() == 'none':
            return None
        return str(value)

class NetworkAddress(tuple):
    """A TCP/IP host[:port] network address. 
    Host may be a hostname, an IP address or the keyword `any' meaning `0.0.0.0'.
    If port is missing, NGNPro's default port (9200) will be used.
    Using the keyword `default' as the value, will use `0.0.0.0:9200' as the address."""
    _defaultPort = 9200
    def __new__(typ, value):
        if value.lower() == 'none': return None
        if value.lower() == 'default': return ('0.0.0.0', typ._defaultPort)
        match = re.search(r'^(?P<address>.+?):(?P<port>\d+)$', value)
        if match:
            address = str(match.group('address'))
            port = int(match.group('port'))
        else:
            address = value
            port = typ._defaultPort
        try:
            address = Hostname(address)
        except ValueError:
            raise ValueError("invalid network address: %r" % value)
        return (address, port)

class EndpointAddress(NetworkAddress):
    """A network endpoint. This is a NetworkAddress that cannot be None or have an undefined address/port."""
    _defaultPort = 0
    _name = 'end point address'
    def __new__(typ, value):
        address = NetworkAddress.__new__(typ, value)
        if address is None:
            raise ValueError("invalid %s: %s" % (typ._name, value))
        elif address[0]=='0.0.0.0' or address[1]==0:
            raise ValueError("invalid %s: %s:%s" % (typ._name, address[0], address[1]))
        return address
