# -*- coding: utf-8 -*-
#
# Copyright (c) 2010, Robert Corsaro
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the <ORGANIZATION> nor the names of its
#       contributors may be used to endorse or promote products derived from
#       this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# ----------------------------------------------------------------------------
import Queue
import time

from threading import Thread
from xmpp import Client
from xmpp.protocol import Message, JID

from trac.config import Option, BoolOption, IntOption, OrderedExtensionsOption
from trac.core import *
from trac.util.compat import set

from announcer.api import IAnnouncementDistributor
from announcer.api import IAnnouncementPreferenceProvider
from announcer.api import IAnnouncementAddressResolver
from announcer.api import IAnnouncementFormatter
from announcer.api import IAnnouncementProducer
from announcer.resolvers import SpecifiedXmppResolver
from announcer.util.settings import SubscriptionSetting


class XmppDistributor(Component):
    """Distribute announcements to XMPP clients."""

    implements(IAnnouncementDistributor)

    formatters = ExtensionPoint(IAnnouncementFormatter)

    resolvers = OrderedExtensionsOption('announcer', 'xmpp_resolvers',
        IAnnouncementAddressResolver, 'SpecifiedXmppResolver',
        """Comma seperated list of xmpp resolver components in the order
        they will be called.  If an xmpp address is resolved, the remaining
        resolvers will no be called.
        """)

    default_format = Option('announcer', 'default_xmpp_format',
            'text/plain',
            """Default format for xmpp messages.""")

    server = Option('xmpp', 'server', None,
        """XMPP server hostname to use for jabber notifications.""")

    port = IntOption('xmpp', 'port', 5222,
        """XMPP server port to use for jabber notification.""")

    user = Option('xmpp', 'user', 'trac@localhost',
        """Sender address to use in xmpp message.""")

    resource = Option('xmpp', 'resource', 'TracAnnouncerPlugin',
        """Sender resource to use in xmpp message.""")

    password = Option('xmpp', 'password', None,
        """Password for XMPP server.""")

    use_threaded_delivery = BoolOption('announcer', 'use_threaded_delivery',
            False,
            """If true, the actual delivery of the message will occur
            in a separate thread.  Enabling this will improve responsiveness
            for requests that end up with an announcement being sent over
            email. It requires building Python with threading support
            enabled-- which is usually the case. To test, start Python and
            type 'import threading' to see if it raises an error.
            """)

    def __init__(self):
        self.connections = {}
        self.delivery_queue = None
        self.xmpp_format_setting = SubscriptionSetting(self.env, 'xmpp_format',
                self.default_format)

    def get_delivery_queue(self):
        if not self.delivery_queue:
            self.delivery_queue = Queue.Queue()
            thread = DeliveryThread(self.delivery_queue, self.send)
            thread.start()
        return self.delivery_queue

    # IAnnouncementDistributor
    def transports(self):
        yield "xmpp"

    def distribute(self, transport, recipients, event):
        self.log.info('XmppDistributor called')
        if transport != 'xmpp':
            return
        fmtdict = self._formats(transport, event.realm)
        if not fmtdict:
            self.log.error(
                "XmppDistributor No formats found for %s %s"%(
                    transport, event.realm))
            return
        msgdict = {}
        for name, authed, addr in recipients:
            fmt = name and \
                self._get_preferred_format(name, event.realm)
            if fmt not in fmtdict:
                self.log.debug(("XmppDistributor format %s not available " +
                    "for %s %s, looking for an alternative")%(
                        fmt, transport, event.realm))
                # If the fmt is not available for this realm, then try to find
                # an alternative
                oldfmt = fmt
                fmt = None
                for f in fmtdict.values():
                    fmt = f.alternative_style_for(
                            transport, event.realm, oldfmt)
                    if fmt: break
            if not fmt:
                self.log.error(
                    "XmppDistributor was unable to find a formatter " +
                    "for format %s"%k
                )
                continue
            # TODO:  This won't work with multiple distributors
            #rslvr = None
            # figure out what the addr should be if it's not defined
            #for rslvr in self.resolvers:
            #    addr = rslvr.get_address_for_name(name, authed)
            #    if addr: break
            rslvr = SpecifiedXmppResolver(self.env)
            addr = rslvr.get_address_for_name(name, authed)
            if addr:
                self.log.debug("XmppDistributor found the " \
                        "address '%s' for '%s (%s)' via: %s"%(
                        addr, name, authed and \
                        'authenticated' or 'not authenticated',
                        rslvr.__class__.__name__))
                # ok, we found an addr, add the message
                msgdict.setdefault(fmt, set()).add((name, authed, addr))
            else:
                self.log.debug("XmppDistributor was unable to find an " \
                        "address for: %s (%s)"%(name, authed and \
                        'authenticated' or 'not authenticated'))
        for k, v in msgdict.items():
            if not v or not fmtdict.get(k):
                continue
            self.log.debug(
                "XmppDistributor is sending event as '%s' to: %s"%(
                    fmt, ', '.join(x[2] for x in v)))
            self._do_send(transport, event, k, v, fmtdict[k])

    def _formats(self, transport, realm):
        "Find valid formats for transport and realm"
        formats = {}
        for f in self.formatters:
            for style in f.styles(transport, realm):
                formats[style] = f
        self.log.debug(
            "XmppDistributor has found the following formats capable "
            "of handling '%s' of '%s': %s"%(transport, realm,
                ', '.join(formats.keys())))
        if not formats:
            self.log.error("XmppDistributor is unable to continue " \
                    "without supporting formatters.")
        return formats

    def _get_preferred_format(self, sid, realm=None):
        if realm:
            name = 'xmpp_format_%s'%realm
        else:
            name = 'xmpp_format'
        setting = SubscriptionSetting(self.env, name,
                self.xmpp_format_setting.default)
        return self.xmpp_format_setting.get_user_setting(sid)[0]

    def _do_send(self, transport, event, format, recipients, formatter):
        message = formatter.format(transport, event.realm, format, event)

        package = (recipients, message)

        start = time.time()
        if self.use_threaded_delivery:
            self.get_delivery_queue().put(package)
        else:
            self.send(*package)
        stop = time.time()
        self.log.debug("XmppDistributor took %s seconds to send."\
                %(round(stop-start,2)))

    def send(self, recipients, message):
        """Send message to recipients via xmpp."""
        jid = JID(self.user)
        if self.server:
            server = self.server
        else:
            server = jid.getDomain()
        cl = Client(server, port=self.port, debug=[])
        if not cl.connect():
            raise IOError("Couldn't connect to xmpp server %s"%server)
        if not cl.auth(jid.getNode(), self.password,
                resource=self.resource):
            cl.Connection.disconnect()
            raise IOError("Xmpp auth erro using %s to %s"%(jid, server))
        default_domain = jid.getDomain()
        for recip in recipients:
            cl.send(Message(recip[2], message))


class XmppPreferencePanel(Component):
    implements(IAnnouncementPreferenceProvider)

    formatters = ExtensionPoint(IAnnouncementFormatter)
    producers = ExtensionPoint(IAnnouncementProducer)
    distributors = ExtensionPoint(IAnnouncementDistributor)

    def get_announcement_preference_boxes(self, req):
        yield "xmpp", "XMPP Formats"

    def render_announcement_preference_box(self, req, panel):
        supported_realms = {}
        for producer in self.producers:
            for realm in producer.realms():
                for distributor in self.distributors:
                    for transport in distributor.transports():
                        for fmtr in self.formatters:
                            for style in fmtr.styles(transport, realm):
                                if realm not in supported_realms:
                                    supported_realms[realm] = set()
                                supported_realms[realm].add(style)

        settings = {}
        for realm in supported_realms:
            name = 'xmpp_format_%s'%realm
            settings[realm] = SubscriptionSetting(self.env, name,
                self.xmpp_format_setting.default)
        if req.method == "POST":
            for realm, setting in settings.items():
                name = 'xmpp_format_%s'%realm
                setting.set_user_setting(req.session, req.args.get(name),
                    save=False)
            req.session.save()
        prefs = {}
        for realm, setting in settings.items():
            prefs[realm] = setting.get_user_setting(req.session.sid)[0]
        data = dict(
            realms = supported_realms,
            preferences = prefs,
        )
        return "prefs_announcer_xmpp.html", data


class DeliveryThread(Thread):

    def __init__(self, queue, sender):
        Thread.__init__(self)
        self._sender = sender
        self._queue = queue
        self.setDaemon(True)

    def run(self):
        while 1:
            sendfrom, recipients, message = self._queue.get()
            self._sender(sendfrom, recipients, message)

