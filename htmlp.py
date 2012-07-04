import re
from lxml import etree

CMNT_RE = re.compile(r'IDCommentSubThread(?P<id>[0-9]+)')

comments = {}

def walk(tree, depth=0, parent=0):
	walked = False

	if 'id' in tree.keys():
		tid = tree.get('id')
		x = CMNT_RE.match(tid)
		if x:
			print "  "*depth, depth, parent, int(x.group('id')), tree.tag, " [%s]" % tree.get('id')
			comments[int(x.group('id'))] = parent
			#print int(x.group(1))
			for i in tree:
				walk(i, depth+1, int(x.group('id')))
			walked = True

	if not walked:
		for i in tree:
			walk(i, depth+1, parent)


f = open('inner_html', 'r')

# Fix IntenseDebate's broken XHTML
text = re.sub(r'<p class="idc-fade"<', r'<p class="idc-fade"><', f.read())

tree = etree.HTML(text)


walk(tree)
print comments
#print etree.tostring(tree, pretty_print=True, method="html")

