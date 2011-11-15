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
try:
    from email.header import Header
except:
    from email.Header import Header

from trac.util.text import to_unicode
try:
    # Method only available in Trac 0.11.3 or higher.
    from trac.util.text import exception_to_unicode
except:
    def exception_to_unicode(e, traceback=False):
        """Convert an `Exception` to an `unicode` object.

        In addition to `to_unicode`, this representation of the exception
        also contains the class name and optionally the traceback.
        This replicates the Trac core method for backwards-compatibility.
        """
        message = '%s: %s' % (e.__class__.__name__, to_unicode(e))
        if traceback:
            from trac.util import get_last_traceback
            traceback_only = get_last_traceback().split('\n')[:-2]
            message = '\n%s\n%s' % (to_unicode('\n'.join(traceback_only)),
                                    message)
        return message

MAXHEADERLEN = 76

def next_decorator(event, message, decorates):
    """
    Helper method for IAnnouncerEmailDecorators.  Call the next decorator
    or return.
    """
    if decorates and len(decorates) > 0:
        next = decorates.pop()
        return next.decorate_message(event, message, decorates)

def set_header(message, key, value, charset=None):
    if not charset:
        charset = message.get_charset() or 'ascii'
    # Don't encode pure ASCII headers.
    try:
        value = Header(value, 'ascii', MAXHEADERLEN-(len(key)+2))
    except:
        value = Header(value, charset, MAXHEADERLEN-(len(key)+2))
    if message.has_key(key):
        message.replace_header(key, value)
    else:
        message[key] = value
    return message

def uid_encode(projurl, realm, target):
    """
    Unique identifier used to track resources in relation to emails.

    Returns a base64 encode UID string.  projurl included to avoid
    Message-ID collisions.  Returns a base64 encode UID string.
    Set project_url in trac.ini for proper results.
    """
    if hasattr(target, 'id'):
        id = str(target.id)
    elif hasattr(target, 'name'):
        id = target.name
    else:
        id = str(target)
    uid = ','.join((projurl, realm, id))
    return b32encode(uid.encode('utf8'))

def uid_decode(encoded_uid):
    """
    Returns a tuple of projurl, realm, id and change_num.
    """
    uid = b32decode(encoded_uid).decode('utf8')
    return uid.split(',')

def msgid(uid, host='localhost'):
    """
    Formatted id for email headers.
    ie. <UIDUIDUIDUIDUID@localhost>
    """
    return "<%s@%s>"%(uid, host)

