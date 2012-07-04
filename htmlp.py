import re
from lxml import etree

CMNT_RE = re.compile(r'IDCommentSubThread(?P<id>[0-9]+)')

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

f = open('inner_html', 'r')

# Fix IntenseDebate's broken XHTML
text = re.sub(r'<p class="idc-fade"<', r'<p class="idc-fade"><', f.read())

tree = etree.HTML(text)

print dict(walk(tree))

