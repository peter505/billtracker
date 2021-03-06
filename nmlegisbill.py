#!/usr/bin/env python

from __future__ import print_function

# Scrape bill data from bill pages from nmlegis.org.

import sys, os
import datetime, dateutil.parser
import re
import requests
import posixpath
from bs4 import BeautifulSoup

if sys.version[:1] == '2':
    from urlparse import urlparse
else:
    from urllib.parse import urlparse

# For offline debugging without hitting the real nmlegis site too often,
# URL handling goes through this class, which can be set to debug mode.
# For debugging, set:
# nmlegisbill.url_mapper = nmlegisbill.LocalURLmapper('https://www.nmlegis.gov')
# nmlegisbill.url_mapper = \
#     nmlegisbill.LocalhostURLmapper('http://localhost/billtracker',
#                                    'https://www.nmlegis.gov')
# or define your own URL mapper class: see DebugURLMapper below.

class URLmapper:
    def __init__(self, baseurl, billurlpat):
        '''baseurl is the basic top-level home page (no terminal slash).
           billurlpat is the URL pattern for bills, taking five arguments:
           baseurl, chamber, billtype, number and (2-digit string) year.
           If you need something that doesn't include these four
           patterns in that order, redefine bill_url() accordingly.
        '''
        self.baseurl = baseurl
        self.billurlpat = billurlpat

    def to_abs_link(self, url, cururl):
        '''Try to map relative and / URLs to absolute ones.
           cururl is the page on which the link was found,
           for relative links like ../
        '''
        if not url:
            return url
        purl = urlparse(url)
        if purl.scheme:
            return url

        if purl.path.startswith('/'):
            return self.baseurl + url

        # Otherwise it's (we hope) a relative URL, relative to cururl.
        curl = urlparse(cururl)
        path = posixpath.normpath(posixpath.join(posixpath.dirname(curl.path),
                                                 purl.path))
        url = curl.scheme  + '://' + curl.netloc + path
        if purl.query:
            url += '?' + purl.query
        return url

    def to_local_link(self, url, cururl):
        '''In URLmappers that are local, return a local link
           that won't hit the server.
        '''
        return url

    def bill_url(self, chamber, billtype, number, year):
        return self.billurlpat % (self.baseurl, chamber, billtype, number,
                                  (year_to_2digit(year)))

#
# Two derived classes that are useful for debugging:
#

# Use localhost:// with cached files, for testing CGI:
class LocalhostURLmapper(URLmapper):
    def __init__(self, localurl, realurl, realbillurlpat):
        self.baseurl = localurl
        self.remoteurl = realurl
        self.realbillurlpat = realbillurlpat

    def to_local_link(self, url, cururl):
        '''In URLmappers that are local, return a local link
           that won't hit the server.
        '''
        if not url:
            return url
        return URLmapper.to_abs_link(self, url, cururl)
        # This should be an absolute link in terms of localhost.

    def to_abs_link(self, url, cururl):
        '''Try to map relative, / and localhost URLs to absolute ones
           based on the realurl.
           cururl is the page on which the link was found,
           for relative links like ../
        '''
        mapped_url = self.to_local_link(url, None)

        # Now we have an absolute link in terms of localhost.
        # But if it's a bill URL like http://localhost/foo/cache/2018-HB98.html,
        # remap it to the real url of
        # http://www.nmlegis.gov/lcs/legislation.aspx?chamber=H&legtype=B&legno=98&year=18
        if not mapped_url.startswith(self.baseurl):
            return mapped_url

        mapped_url = mapped_url.replace(self.baseurl, '')

        # Now it's just /cache/2018-HB98.html
        if not mapped_url.startswith('/cache/20'):
            return mapped_url
        year = mapped_url[8:10]
        match = re.match('([HS])([A-Z]+)([0-9]+)', mapped_url[11:-5])
        if not match:
            return mapped_url
        chamber, billtype, number = match.groups()
        return self.realbillurlpat % (self.remoteurl, chamber,
                                      billtype, number,
                                      (year_to_2digit(year)))

    def bill_url(self, chamber, billtype, number, year):
        return '%s/cache/20%s-%s%s%s.html' % (self.baseurl,
                                              year_to_2digit(year),
                                              chamber, billtype, number)

    def get_url(self, url):
        return url

# Use cached local files: good for unit tests.
class LocalURLmapper(URLmapper):
    '''For debugging, look for files like ./test/2018-HJR1.html
       but still use the real links for other links.
    '''
    def __init__(self, baseurl):
        self.baseurl = baseurl

    def bill_url(self, chamber, billtype, number, year):
        return './test/20%s-%s%s%s.html' % (year_to_2digit(year),
                                            chamber, billtype, number)

    def to_local_link(self, url, cururl):
        '''In URLmappers that are local, return a local link
           that won't hit the server.
        '''
        if not url:
            return url

        # XXX This is bogus and will probably not return anything useful,
        # but at least it won't hit the server.
        purl = urlparse(url)
        return './test/%s' % purl.path

url_mapper = URLmapper('https://www.nmlegis.gov',
    '%s/Legislation/Legislation?chamber=%s&legtype=%s&legno=%s&year=%s')

committees = {
    "HAFC": "House Appropriations & Finance",
    "HAWC": "House Agriculture, Water & Wildlife",
    "HAWR": "Agriculture, Water Resources",
    "HBEC": "House Business & Employment",
    "HBIC": "House Business &amp; Industry",
    "HCAL": "House Calendar (for a vote)",
    "HCPAC": "Consumer &amp; Public Affairs",
    "HEC": "House Education Committee",
    "HEENC": "House Energy, Environment & Natural Resources",
    "HGEIC": "House Gov't, Elections & Indian Affairs",
    "HHC": "House Health",
    "HHHC": "House Health and Human Services",
    "HJC": "House Judiciary",
    "HLEDC": "House Labor &amp; Economic Development",
    "HLELC": " House Local Government, Elections, Land Grants &amp; Cultural Affairs",
    "HR": "House Rules",
    "HXRC": "House Rules & Order of Business Committee",
    "HRPA": "House Regulatory & Public Affairs",
    "HSCA": "House Safety & Civil Affairs",
    "HSIVC": "House  State Gov't, Indian &amp; Veteran Affairs",
    "HTPWC": "House Transportation, Public Works &amp; Capital Improvements",
    "HTPW": "House Transportation & Public Works",
    "HTRC": "House Tax &amp; Revenue",
    "HWMC": "House Ways & Means",
    "SAIC": "Senate Indian and Cultural Affairs",
    "SCAL": "Senate Calendar (for vote)",
    "SXCC": "Senate Committee on Committees",
    "SCON": "Senate Conservation",
    "SCORC": "Senate Corporations & Transportation",
    "SEC": "Senate Education Committee",
    "SFC": "Senate Finance Committee",
    "SJC": "Senate Judiciary Committee",
    "SPAC": "Senate Public Affairs",
    "SRC": "Senate Rules Committee",
}

# User-friendly strings for the various bill keys:
# (Not actually used yet)
# keytitles = {
#     'billno'       : 'Bill #',
#     'chamber'      : 'Chamber',
#     'billtype'     : 'Type',
#     'number'       : 'Number',
#     'year'         : 'Year',
#     'bill_url    ' : 'Bill Link',
#     'title'        : 'Title',
#     'sponsor'      : 'Sponsor',
#     'sponsorlink'  : 'Sponsor link',
#     'curloc'       : 'Current Location',
#     'curloclink'   : 'Current Location Link',
#     'contents_url' : 'Bill Contents Link',
# }

def year_to_2digit(year):
    '''Translate a year in various formats to a 2-digit string.
    '''

    if type(year) is int:
        if year > 2000:
            year -= 2000
        return '%02d' % year

    elif type(year) is str:
        if len(year) > 2:
            return year[-2:]

    # Use this year if not defined or in an unknown format.
    return '%02d' % (datetime.datetime.now().year - 2000)

def billno_to_parts(billno, year=None):
    year = year_to_2digit(year)

    # billno is chamber, bill type, digits, e.g. HJM4. Parse that:
    match = re.match('([HS])([A-Z]+)([0-9]+)', billno)
    if not match:
        raise RuntimeError("Can't parse bill name '%s'" % billno)
    chamber, billtype, number = match.groups()
    return chamber, billtype, number, year

def check_analysis(billno):
    '''See if there are any FIR or LESC analysis links.
       The bill's webpage won't tell us because those are hidden
       behind Javascript, so just try forming URLs and see if
       anything's there.
    '''
    (chamber, billtype, number, year) = billno_to_parts(billno)
    # number = int(number)

    # XXX This urlmapper stuff needs to be redesigned.
    # The to_local_link stuff here is just to keep us from
    # hitting a remote server while running tests.
    firlink = url_mapper.to_local_link(
        '%s/Sessions/%s%%20Regular/firs/%s%s00%s.PDF' \
        % (url_mapper.baseurl, year, chamber, billtype, number),
        None)
    lesclink = url_mapper.to_local_link(
        '%s/Sessions/%s%%20Regular/LESCAnalysis/%s%s00%s.PDF' \
               % (url_mapper.baseurl, year, chamber, billtype, number),
        None)
    amendlink = url_mapper.to_local_link(
        '%s/Sessions/%s%%20Regular/Amendments_In_Context/%s%s00%s.PDF' \
               % (url_mapper.baseurl, year, chamber, billtype, number),
        None)

    if ':' in firlink:
        request = requests.get(firlink)
        if request.status_code != 200:
            firlink = None
    else:
        firlink = None
    if ':' in lesclink:
        request = requests.get(lesclink)
        if request.status_code != 200:
            lesclink = None
    else:
        lesclink = None

    return firlink, lesclink, amendlink

def parse_bill_page(billno, year=None, cache_locally=False):
    '''Download and parse a bill's page on nmlegis.org.
       Return a dictionary containing:
       chamber, billtype, number, year,
       title, sponsor, sponsorlink,
       curloc, curloclink, and contents_url.
       Set update_date to now.
       Does *not* save the fetched bill back to the database.
    '''

    billdic = { 'billno': billno }
    (billdic['chamber'], billdic['billtype'],
     billdic['number'], billdic['year']) = billno_to_parts(billno, year)

    baseurl = url_mapper.bill_url(billdic['chamber'],
                                  billdic['billtype'],
                                  billdic['number'],
                                  billdic['year'])
    if cache_locally:
        filename = 'cache/20%s-%s.html' % (billdic['year'], billno)

        # While in a debugging cycle, used cached pages
        # so as not to hit the server so often.
        if os.path.exists(filename):
            print("Temporarily using cache for", billno, file=sys.stderr)
            baseurl = filename

    if ':' in baseurl:
        billdic['bill_url'] = url_mapper.to_abs_link(baseurl, baseurl)
        print("Fetching %s info from %s" % (billno, baseurl), file=sys.stderr)
        r = requests.get(baseurl)
        soup = BeautifulSoup(r.text, 'lxml')

        if cache_locally:
            with open(filename, "w") as cachefp:
                cachefp.write(r.text.encode('utf-8', "xmlcharrefreplace"))
                print("Cached locally as %s" % filename, file=sys.stderr)
    else:
        with open(baseurl) as fp:
            billdic['bill_url'] = baseurl
            soup = BeautifulSoup(fp, 'lxml')

        # This probably ought to be folded into the url mapper somehow.
        baseurl = "http://www.nmlegis.gov/Legislation/Legislation"

    # If something failed -- for instance, if we got an empty file
    # or an error page -- then the title span won't be there.
    # Detect that:
    try:
        billdic['title'] = soup.find("span",
                                     id="MainContent_formViewLegislation_lblTitle").text
    except AttributeError:
        # If we cached, remove the cache file.
        if cache_locally and filename:
            os.unlink(filename)
        print("No such bill %s" % billno)
        return None
    sponsor_a = soup.find("a",
                          id="MainContent_formViewLegislation_linkSponsor")
    billdic['sponsor'] = sponsor_a.text.strip()
    billdic['sponsorlink'] = url_mapper.to_abs_link(sponsor_a.get('href'),
                                                    baseurl)

    curloc_a  = soup.find("a",
                          id="MainContent_formViewLegislation_linkLocation")
    billdic['curloc'] = curloc_a.text.strip()
    billdic['curloclink'] = url_mapper.to_abs_link(curloc_a.get('href'),
                                                   baseurl)

    contents_a = soup.find("a",
                           id="MainContent_formViewLegislationTextIntroduced_linkLegislationTextIntroducedHTML")
    billdic['contents_url'] = url_mapper.to_abs_link(contents_a.get('href'),
                                                     baseurl)

    # Does the bill have any amendments?
    # Unfortunately we can't get the amendments themselves --
    # they're only available in PDF. But we can see if they exist.
    # amenddiv = soup.find("div", id="MainContent_tabContainerLegislation_tabPanelFloorReports")
    #     # Inside this div is a div for a label (Proposed, Adopted, Not Adopted)
    #     # followed by a table where (I think) there's a <tr><td> for each
    #     # amendment in that class; the actual amendment will look like
    #     # <a ... href="/Sessions/18%20Regular/memorials/house/HJM010FH1.pdf">
    #     #   <span ...>House Floor Amendment 1</span> &nbsp;
    #     #   <span ...">2/07/18</span>
    #     # </a>

    # Alternately, the "Amendments in Context" button:
    amendbutton = soup.find("a", id="MainContent_formViewAmendmentsInContext_linkAmendmentsInContext")
    if amendbutton:
        billdic["amendlink"] = url_mapper.to_abs_link(amendbutton.get('href'),
                                                      baseurl)

    # The all-important part: what was the most recent action?
    actiontable = soup.find("table",
      id="MainContent_tabContainerLegislation_tabPanelActions_dataListActions")

    actions = actiontable.findAll('span', class_="list-group-item")
    if actions:
        lastaction = actions[-1]

        # Try to parse the most recent modification date from it:
        actiontext = lastaction.text
        match = re.search('Calendar Day: (\d\d/\d\d/\d\d\d\d)', actiontext)
        if match:
            last_action_date = dateutil.parser.parse(match.group(1))
        else:
            last_action_date = None
        billdic['last_action_date'] = last_action_date

        # nmlegis erroneously uses <br>blah</br><strong> and
        # apparently assumes browsers will put a break at the </br>.
        # Since that's illegal HTML, BS doesn't parse it that way.
        # But if we don't compensate, the status looks awful.
        # So try to mitigate that by inserting a <br> before <strong>.
        billdic["statusHTML"] = re.sub('<strong>', '<br><strong>',
                                       str(lastaction))

        # Clean up the text in a similar way, adding spaces and line breaks.
        while actiontext.startswith('\n'):
            actiontext = actiontext[1:]
        actiontext = '    ' + actiontext
        actiontext = re.sub('(Legislative Day: [0-9]*)', '\\1\n    ',
                            actiontext)
        actiontext = re.sub('(Calendar Day: ../../....)', '\\1\n    ',
                            actiontext)
        actiontext = re.sub('\n\n*', '\n', actiontext)
        billdic["statustext"] = actiontext

    # The bill's page has other useful info, like votes, analysis etc.
    # but unfortunately that's all filled in later with JS and Ajax so
    # it's invisible to us. But we can make a guess at FIR and LESC links:
    billdic['FIRlink'], billdic['LESClink'], billdic['amendlink'] \
        = check_analysis(billno)

    billdic['update_date'] = datetime.datetime.now()
    billdic['mod_date'] = None

    return billdic

def most_recent_action(billdic):
    '''Return a date, plus text and HTML, for the most recent action
       represented in billdic["statusHTML"].
    '''
    if not billdic['statusHTML']:
        return None
    soup = BeautifulSoup(billdic["statusHTML"])
    actions = soup.findAll('span', class_="list-group-item")
    if not actions:
        return None
    lastaction = actions[-1]

    # Try to parse the most recent modification date from t.
    match = re.search('Calendar Day: (\d\d/\d\d/\d\d\d\d)', lastaction)
    if match:
        last_action_date = dateutil.parser.parse(match.group(1))
    else:
        last_action_date = None
    billdic['last_action_date'] = last_action_date
    return last_action_date, str(lastaction), lastaction.text

# There doesn't seem to be a way, without javascript,
# to get a list of all current legislation. Sigh.
# Here's a failed attempt.
# def get_all_legislation(year):
#     payload = {'ctl00$MainContent$ddlSessionStart': '56',
#                'ctl00$MainContent$ddlSessionEnd': '56',
#                'ctl00$MainContent$chkSearchBills': 'on',
#                'ctl00$MainContent$chkSearchMemorials': 'on',
#                'MainContent_chkSearchResolutions': 'on',
#               }
#     r = requests.post('https://nmlegis.gov/Legislation/Legislation_List',
#                       data=payload)

if __name__ == '__main__':
    def print_bill_dic(bd):
        print("%s: %s" % (bd['billno'], bd['title']))
        print("Current location: %s --> %s" % (bd['curloc'],
                                               bd['curloclink']))
        print("Sponsor: %s --> %s" % (bd['sponsor'], bd['sponsorlink']))
        print("Contents at: %s" % (bd['contents_url']))

    billdic = parse_bill_page('HJR1')
    print_bill_dic(billdic)

