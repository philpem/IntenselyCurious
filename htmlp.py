import re
from HTMLParser import HTMLParser
from htmlentitydefs import name2codepoint

class MyHTMLParser(HTMLParser):
	RE_THREAD = re.compile(r'ID(CommentSub)?Thread([0-9]+)')
	RE_COMMENT = re.compile(r'IDComment([0-9]+)')

	def handle_starttag(self, tag, attrs):
		if (tag == 'div' or tag == 'span'):
			for attr in attrs:
				if attr[0] == 'id':
					x = self.RE_COMMENT.match(attr[1])
					if x:
						print 'Open +', attr[1]
						print x.group(1)
						break
					x = self.RE_THREAD.match(attr[1])
					if x:
						print 'Open *', attr[1]
						print x.group(len(x.groups()))

"""
		print "Start tag:", tag
		for attr in attrs:
			print "     attr:", attr
"""
"""
	def handle_endtag(self, tag):
		print "End tag  :", tag
	def handle_data(self, data):
		print "Data     :", data
	def handle_comment(self, data):
		print "Comment  :", data
	def handle_entityref(self, name):
		c = unichr(name2codepoint[name])
		print "Named ent:", c
	def handle_charref(self, name):
		if name.startswith('x'):
			c = unichr(int(name[1:], 16))
		else:
			c = unichr(int(name))
		print "Num ent  :", ord(c)
	def handle_decl(self, data):
		print "Decl     :", data
"""

f = open('inner_html', 'r')

p = MyHTMLParser()
# IntenseDebate fucked up their HTML. This blob of Magick fixes it.
p.feed(re.sub(r'<p class="idc-fade"<', r'<p class="idc-fade"><', f.read()))

