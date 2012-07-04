import re
from lxml import etree

CMNT_RE = re.compile(r'IDCommentSubThread(?P<id>[0-9]+)')

def ParseCommentTree(innerhtml):
	def walk(tree, depth=0, parent=0):
		lp = []

		if 'id' in tree.keys():
			tid = tree.get('id')
			x = CMNT_RE.match(tid)
			if x:
				cid = int(x.group('id'))
				lp = lp + [(cid, parent)]
				#print "  "*depth, depth, parent, int(x.group('id')), tree.tag, " [%s]" % tree.get('id')
				for i in tree:
					lp = lp + walk(i, depth+1, int(x.group('id')))
				return lp

		for i in tree:
			lp = lp + walk(i, depth+1, parent)
		return lp

	# Fix IntenseDebate's broken XHTML and parse it
	text = re.sub(r'<p class="idc-fade"<', r'<p class="idc-fade"><', innerhtml)
	tree = etree.HTML(text)
	return dict(walk(tree))

f = open('inner_html', 'r')
print ParseCommentTree(f.read())

