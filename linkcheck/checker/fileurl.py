# -*- coding: iso-8859-1 -*-
"""Handle local file: links"""
# Copyright (C) 2000-2004  Bastian Kleineidam
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import re
import os
import time
import urlparse
import urllib

import urlbase
import linkcheck
import linkcheck.checker

# if file extension lookup was unsuccessful, look at the content
contents = {
    "html": re.compile(r'^(?i)<(!DOCTYPE html|html|head|title)'),
    "opera" : re.compile(r'^Opera Hotlist'),
    "text" : re.compile(r'(?i)^# LinkChecker URL list'),
}


def get_files (dirname):
    """Get lists of files in directory. Does only allow regular files
       and directories, no symlinks.
    """
    files = []
    for entry in os.listdir(dirname):
        fullentry = os.path.join(dirname, entry)
        if os.path.islink(fullentry) or \
           not (os.path.isfile(fullentry) or os.path.isdir(fullentry)):
            continue
        files.append(entry)
    return files


class FileUrl (urlbase.UrlBase):
    "Url link with file scheme"

    def __init__ (self, base_url, recursion_level, consumer,
                  parent_url = None,
                  base_ref = None, line=0, column=0, name=""):
        super(FileUrl, self).__init__(base_url, recursion_level, consumer,
             parent_url=parent_url, base_ref=base_ref,
             line=line, column=column, name=name)
        if not (parent_url or base_ref or self.base_url.startswith("file:")):
            self.base_url = os.path.expanduser(self.base_url)
            if not self.base_url.startswith("/"):
                self.base_url = os.getcwd()+"/"+self.base_url
            self.base_url = "file://"+self.base_url
        self.base_url = self.base_url.replace("\\", "/")
        # transform c:/windows into /c|/windows
        self.base_url = re.sub(r"^file://(/?)([a-zA-Z]):", r"file:///\2|",
                              self.base_url)

    def build_url (self):
        super(FileUrl, self).build_url()
        # ignore query and fragment url parts for filesystem urls
        self.urlparts[3] = self.urlparts[4] = ''
        if self.is_directory() and not self.urlparts[2].endswith('/'):
            self.add_warning(_("Added trailing slash to directory"))
            self.urlparts[2] += '/'
        self.url = urlparse.urlunsplit(self.urlparts)

    def check_connection (self):
        if self.is_directory():
            self.set_result(_("directory"))
            return
        super(FileUrl, self).check_connection()

    def get_content (self):
        if not self.valid:
            return ""
        if self.is_directory() and not self.has_content:
            return self.get_directory_content()
        return super(FileUrl, self).get_content()

    def get_directory_content (self):
        t = time.time()
        files = get_files(self.get_os_filename())
        self.data = linkcheck.checker.get_index_html(files)
        self.dltime = time.time() - t
        self.dlsize = len(self.data)
        self.has_content = True
        return self.data

    def set_cache_keys (self):
        """Set keys for URL checking and content recursion."""
        # remove anchor from content cache key
        self.cache_content_key = urlparse.urlunsplit(self.urlparts[:4]+[''])
        # same here - a local file with different anchors has always the
        # same result
        self.cache_url_key = self.cache_content_key

    def is_html (self):
        if linkcheck.checker.extensions['html'].search(self.url):
            return True
        if contents['html'].search(self.get_content()):
            return True
        return False

    def is_file (self):
        return True

    def get_os_filename (self):
        return urllib.url2pathname(self.urlparts[2])

    def is_directory (self):
        filename = self.get_os_filename()
        return os.path.isdir(filename) and not os.path.islink(filename)

    def is_parseable (self):
        if self.is_directory():
            return True
        # guess by extension
        for ro in linkcheck.checker.extensions.values():
            if ro.search(self.url):
                return True
        # try to read content (can fail, so catch error)
        try:
            for ro in contents.values():
                if ro.search(self.get_content()[:30]):
                    return True
        except IOError:
            pass
        return False

    def parse_url (self):
        if self.is_directory():
            return self.parse_html()
        for key, ro in linkcheck.checker.extensions.items():
            if ro.search(self.url):
                return getattr(self, "parse_"+key)()
        for key, ro in contents.items():
            if ro.search(self.get_content()[:30]):
                return getattr(self, "parse_"+key)()
        return None
