# -*- coding: utf-8 -*-
#
# Copyright (c) 2009, Robert Corsaro
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

from base64 import b32encode, b32decode
# TODO: this sucks, change it!
import __builtin__
pyemail = __builtin__.__import__('email')
try:
    Header = pyemail.header.Header
except:
    Header = pyemail.Header.Header
# end suckage

MAXHEADERLEN = 76

def next_decorator(event, message, decorates):
    if decorates and len(decorates) > 0:
        next = decorates.pop()
        return next.decorate_message(event, message, decorates)

def set_header(message, key, value, charset='ascii'):
    value = Header(value, charset, MAXHEADERLEN-(len(key)+2))
    if message.has_key(key):
        message.replace_header(key, value)
    else:
        message[key] = value
    return message

def uid_encode(projurl, realm, target, change_num='0'):
    """
    Unique identifier used to track resources in relation to emails.
    projurl included to avoid Message-ID collisions.  Returns a base32 encode 
    UID string.

    Set project_url in trac.ini for proper results.
    """
    if hasattr(target, 'id'):
        id = str(target.id)
    elif hasattr(target, 'name'):
        id = target.name
    else:
        id = str(target)
    change_num = str(change_num)
    uid = ','.join((projurl, realm, id, change_num))
    return b32encode(uid)

def uid_decode(encoded_uid):
    """
    Returns a tuple of projurl, realm, id and change_num.
    """
    uid = b32decode(encoded_uid)
    return uid.split(',')

class ResourceUIDs(object):
    """
    Repeatable generation of resource announcement message-ids used for 
    References, Message-ID and In-Reply-To headers.  Can also be used
    for incoming email replies that modify their target.
    """
    def __init__(self, env, event, message, change_num=0):
        self.event = event
        self.message = message
        self.env = env
        prev_change_num = change_num > 0 and change_num - 1 or change_num
        self.uids = dict(
            cur = uid_encode(
                self.env.abs_href(), 
                event.realm, 
                event.target, 
                change_num
            ),
            prev = uid_encode(
                self.env.abs_href(), 
                event.realm, 
                event.target, 
                change_num - 1 
            ), 
            first = uid_encode(
                self.env.abs_href(), 
                event.realm, 
                event.target, 
                0
            ), 
        )

    def msgid(self, key, host='localhost'):
        """
        cur, prev or first.  Formatted id for email headers.
        ie. <UIDUIDUIDUIDUID@localhost>
        """
        return "<%s@%s>"%(self.uids[key], host)

    def __getitem__(self, key):
        """
        Raw UID without message-id formatting.
        """
        return self.uids[key]

