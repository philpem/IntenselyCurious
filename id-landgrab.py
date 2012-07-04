#!/usr/bin/env python
#
# Landgrab: an IntenseDebate comment scraper.
#
# Pulls all the comments from an IntenseDebate comment form and dumps them in
# a sane and reasonable format.
#
# That format is, of course, CSV.
#
# Things we can find out:
#    A commenter's name (and, where appropriate, InstantDebate user ID)
#    Comment order and threading (parent)
#    Date and time of posting
#    InstantDebate internal post ID
#    And, of course, the text of the comment itself
#

import urllib
import urllib2
import cookielib
import re
import htmlentitydefs
from lxml import etree
import MySQLdb
from datetime import datetime, date

# IntenseDebate account ID
ID_ACCT="a52f66556303bc0fe20312cfad5cc8b9"

CONTROLS = [
		# Control ID	Last strip ID		IntenseDebate ID prefix
		{'cid': 1,		'strips': 1215,		'idpfx': ''					},		# Precocious
		{'cid': 2,		'strips': 100,		'idpfx': 'copper'			}		# Copper Road
	]


###########
# Dragons lurketh here (you probably don't want to change anything below this line)
###########

"""
# Set up URLLib2 and the Cookie Jar
cookiejar = cookielib.LWPCookieJar()
opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookiejar))
urllib2.install_opener(opener)
"""

IDCS_RE = re.compile('.*IDCommentScript.src = "([^"]*).*')

useragent='Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'
HEADERS = {'User-agent' : useragent}

def ParseLine(line):
	inStr=False
	x = ""
	fields = []
	for c in line:
		if inStr:
			if c != "'":
				x = x + c
			else:
				# end of string
				inStr = False
		else:
			if c == "'":
				inStr = True
			elif c == ",":
				try:
					fields.append(int(x.strip()))
				except:
					fields.append(x.strip())
				x = ""
			else:
				x = x + c
	if len(x) > 0:
		try:
			fields.append(int(x.strip()))
		except:
			fields.append(x.strip())
	return fields

def GetIDCommentScriptSrc(account, postid=None, url=None):
	# http://intensedebate.com/js/genericCommentWrapper2.php?acct=a52f66556303bc0fe20312cfad5cc8b9&postid=&title=&url=http://precociouscomic.com/comic.php?page=1
	if postid is not None:
		print "--- Get By PostID: %s" % postid
		data = urllib.urlencode({'acct':account, 'postid':postid, 'title':'', 'url':''})
	elif url is not None:
		print "--- Get By URL: %s" % url
		data = urllib.urlencode({'acct':account, 'postid':'', 'title':'', 'url':url})
	else:
		print "WTF? Attempt to get the comment script URL with no usable ID!"
		return None

	req = urllib2.Request("http://intensedebate.com/js/genericCommentWrapper2.php?%s" % data, None, HEADERS)
	resp = urllib2.urlopen(req)
	pagestr = resp.read()
	rematch = IDCS_RE.match(pagestr)
	if rematch is not None:
		return rematch.group(1)
	else:
		return None

# RE to extract IDCommentSubThread data (which is nested properly, unlike IDComment data)
IDCST_RE = re.compile(r'IDCommentSubThread(?P<id>[0-9]+)')

# Parse the comment tree, returning a dict mapping from ID to parent
def ParseCommentTree(innerhtml):
	def walk(tree, depth=0, parent=0):
		lp = []

		if 'id' in tree.keys():
			tid = tree.get('id')
			x = IDCST_RE.match(tid)
			if x:
				cid = int(x.group('id'))
				lp = lp + [(cid, parent)]
				#print "  "*depth, depth, parent, cid, tree.tag, " [%s]" % tree.get('id')
				for i in tree:
					lp = lp + walk(i, depth+1, cid)
				return lp

		for i in tree:
			lp = lp + walk(i, depth+1, parent)
		return lp

	# Fix IntenseDebate's broken XHTML and parse it
	text = re.sub(r'<p class="idc-fade"<', r'<p class="idc-fade"><', innerhtml)
	tree = etree.HTML(text)
	return dict(walk(tree))

##
# Removes HTML or XML character references and entities from a text string.
#
# @param text The HTML (or XML) source text.
# @return The plain text, as a Unicode string, if necessary.

def unescape(text):
	def fixup(m):
		text = m.group(0)
		if text[:2] == "&#":
			# character reference
			try:
				if text[:3] == "&#x":
					return unichr(int(text[3:-1], 16))
				else:
					return unichr(int(text[2:-1]))
			except ValueError:
				pass
		else:
			# named entity
			try:
				text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
			except KeyError:
				pass
		return text # leave as is
	return re.sub("&#?\w+;", fixup, text)

# Turn IntenseDebate's comment HTML into something we can actually use
def StripCommentTextHTML(s):
	# First we split on linebreaks
	a = re.sub(r'<[bB][rR]\s*/>', r'\n', s)

	# Turn HTML entity escape sequences back into their character equivalents
	a = unescape(a)

	# Finally strip leading and trailing spaces from each line
	k = a.split('\n')
	for i in range(len(k)):
		k[i] = k[i].strip()
	a = '\n'.join(k)

	return a

### Regular expressions ###
# Used to get the InnerHTML blob for a comment
IHTM_RE = re.compile(r'var innerHTML = \'(.*)\'; idcCommentsDiv')
# Used to retrieve the text of a comment
CMNT_RE = re.compile(r'<div id="IDComment-CommentText([0-9]*)".*?>(.*?)</div>')

# NOTE: span id="IDCommentVoteScore<n>" is used to store the comment's voting score

# Used to retrieve a comment entry
IDCD_RE = re.compile(r'commentObj.comments\[[0-9]*\]=new IDComment\((.*?) \);')

def GetIDCommentData(account, postid=None, url=None):
	postscript = GetIDCommentScriptSrc(account, postid, url)
	req = urllib2.Request(postscript, None, HEADERS)
	resp = urllib2.urlopen(req)
	rtext = resp.read()
	lines = IDCD_RE.findall(rtext)
	lt = []
	for line in lines:
		x = ParseLine(line)
		# function IDComment(userid, commentid, time, status, depth, votescore, totalChildren, lastActivity, threadparentid, commentDiv, displayName) {
		cm = {}
		names = ['userid', 'commentid', 'time', 'status', 'depth', 'votescore', 'totalChildren', 'lastActivity', 'threadparentid', 'commentDiv', 'displayName']
		for n in range(len(x)):
			cm[names[n]] = x[n]
		lt.append(cm)

	# get the "inner HTML" block (which contains the actual thread)
	ihtml = re.sub(r'\\(.)', r'\1', IHTM_RE.search(rtext).group(1))

	# Decode the InnerHTML data into a comment tree
	ctree = ParseCommentTree(ihtml)

	# blast it apart into individual comments
	commenttext = CMNT_RE.findall(ihtml)
	# now tie the comments in with the LT data
	for comment in commenttext:
		cid = int(comment[0])
		ctxt = StripCommentTextHTML(comment[1])
		for i in range(len(lt)):
			if int(lt[i]['commentid']) == int(cid):
				lt[i]['text'] = ctxt
				break

	# Sort out the threading order
	for i in range(len(lt)):
		if int(lt[i]['commentid']) in ctree:
			lt[i]['parent'] = ctree[lt[i]['commentid']]
		else:
			print ">>> AARGH: No thread parent information found for comment %d. Assuming this is a rooted post." % int(lt[i]['commentid'])
			lt[i]['parent'] = 0

	return lt


# Connect to MySQL
if __name__ == '__main__':
	db = MySQLdb.connect(host="localhost", user="precocious", passwd="password", db="precocious")
	cur = db.cursor()

	for comic in CONTROLS:
		CONTROL_ID = comic['cid']
		NSTRIPS = comic['strips']
		IDPREFIX = comic['idpfx']

		print "----- Processing Control_ID %d ('%s'); %d strips to import -----" % (CONTROL_ID, IDPREFIX, NSTRIPS)

		for pid in range(1, NSTRIPS+1):
			print "\n\nProcessing postid=%d" % pid

			if CONTROL_ID == 1:
				# -- PRECOCIOUS --
				if (pid <= 100):
					# Comments for strips up to and including #100 have their comments stored in two places.
					# There's the "original" location, which we'll deal with first...
					data1 = GetIDCommentData(ID_ACCT, url='http://precociouscomic.com/comic.php?page=%d' % pid)

					# And there's the "replacement" location which kicked in after the site move...
					# First figure out the date offset from the first strip...
					dt = date.fromordinal(date(2009,3,9).toordinal() + pid - 1)
					# Turn that into a URL which follows Clickthulhu's format
					data2 = GetIDCommentData(ID_ACCT, url='http://precociouscomic.com/archive/comic/%04d/%02d/%02d' % (dt.year, dt.month, dt.day))

					# Now mash both datasets together
					data = data1 + data2
				elif (pid > 100) and (pid <= 241):
					data = GetIDCommentData(ID_ACCT, postid=(pid-100))
				else:
					data = GetIDCommentData(ID_ACCT, postid=pid)
			else:
				# -- COPPER ROAD --
				data = GetIDCommentData(ID_ACCT, postid='%s%d' % (IDPREFIX, pid))

			for x in data:
				# print x
				if 'text' not in x:
					print ">>> WARNING: Post %d comment %d has been skipped; reason: no text found, deleted comment?" % (pid, int(x['commentid']))
					continue

				try:
					cur.execute("""INSERT INTO comments
					(comment_id, control_id, comic_id, comment_timestamp, comment_parent_id, comment_author, comment_author_avatar, comment_author_email, comment_author_link, comment_author_show_link, comment_author_ip, comment_text, comment_rank, comment_is_spam, comment_is_moderated)
					VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
					(
						int(x['commentid']),				# Sequential ID number
						int(CONTROL_ID),					# Always 1 for Precocious, 2 for Copper Road
						int(pid),							# Comic ID #, should be available via the ID info
						datetime.strptime(x['time'], "%B %d, %Y %H:%M:%S"),		# FIXME Time/Date posted
						int(x['parent']),					# Comment ID # of any parent comment
						unescape(x['displayName']),			# Commenter Name
						"",									# comment_author_avatar --> should always be null
						"",									# Commenter email address
						"",									# FIXME Commenter website
						0,									# FIXME 1 = show website, 0 = do not show site
						"unknown",							# FIXME? IP address of commenter
						x['text'],							# Text of comment
						0,									# Rank - should be 0
						0,									# Is_Spam - should be 0
						0									# Is_Moderated - should be 0
					))
				except:
					print
					print "!!! Something rotten in Denmark! Uncaught exception. XData is:"
					print x
					print
					raise

	cur.close()
	db.close()

