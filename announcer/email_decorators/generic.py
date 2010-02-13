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
import re
from email.utils import parseaddr 
 
from trac.core import * 
from trac.config import ListOption 

from announcer.distributors.mail import IAnnouncementEmailDecorator 
from announcer.util.mail import set_header, msgid, next_decorator, uid_encode

class ReplyToEmailDecorator(Component): 
    """ 
    Add Message-ID, In-Reply-To and References message headers for resources. 
    All message ids are derived from the properties of the ticket so that they 
    can be regenerated later. 
    """ 
 
    implements(IAnnouncementEmailDecorator) 
 
    supported_realms = ListOption('announcer', 'email_threaded_realms',  
        ['ticket', 'wiki'],  
        doc=""" 
        These are realms with announcements that should be threaded 
        emails.  In order for email threads to work, the announcer 
        system needs to give the email recreatable Message-IDs based 
        on the resources in the realm.  The resources must have a unique 
        and immutable id, name or str() representation in it's realm
        """) 

    def decorate_message(self, event, message, decorates=None): 
        """ 
        Added headers to the outgoing email to track it's relationship 
        with a ticket.  

        References, In-Reply-To and Message-ID are just so email clients can 
        make sense of the threads. 

        This algorithm seems pretty generic, so maybe we can make the realm 
        configurable.  Any resource with and id and version should work.  The  
        Reply-To header only makes sense for things that can be appended to 
        through email.  Two examples are tickets and blog comments. 
        """ 
        if event.realm in self.supported_realms: 
            smtp_from = self.config.get('announcer', 'smtp_from', 'localhost') 
            _, smtp_addr = parseaddr(smtp_from) 
            host = re.sub('^.+@', '', smtp_addr) 
            uid = uid_encode(self.env.abs_href(), event.realm, event.target) 
            mymsgid = msgid(uid, host) 
            if event.category == 'created': 
                set_header(message, 'Message-ID', mymsgid) 
            else: 
                set_header(message, 'In-Reply-To', mymsgid) 
                set_header(message, 'References', mymsgid) 

        return next_decorator(event, message, decorates) 
