#!/usr/bin/python

from urllib import urlopen
from urlparse import urljoin
from BeautifulSoup import BeautifulSoup, Tag, Comment, NavigableString
import re

unlikelycandidates = re.compile("combx|comment|community|disqus|extra|foot|header|menu|remark|rss|shoutbox|sidebar|sponsor|ad-break|agegate|pagination|pager|popup|tweet|twitter", re.IGNORECASE)

okcandidates = re.compile("and|article|body|column|main|shadow", re.IGNORECASE)

negative = re.compile("combx|comment|com-|contact|foot|footer|footnote|masthead|media|meta|outbrain|promo|related|scroll|shoutbox|sidebar|sponsor|shopping|tags|tool|widget", re.IGNORECASE)
positive = re.compile("article|body|content|entry|hentry|main|page|pagination|post|text|blog|story", re.IGNORECASE)

blockElements = ['a', 'blockquote', 'dl', 'div', 'img', 'ol', 'p', 'pre', 'table', 'ul']

def getText(tag):
    return ' '.join([c.strip() for c in tag.findAll(text=True)]).replace('&nbsp;', ' ').strip()

def getLinkDensity(tag):
    textLength = len(getText(tag))
    linkLength = 0
    for link in tag.findAll('a'):
        linkLength = linkLength + len(getText(link))
    if textLength == 0:
        return 0
    else:
        return float(linkLength) / float(textLength)

def scaleScore(n):
    n.score = n.score * (1 - getLinkDensity(n))
    return n

def classWeight(t):
    weight = 0

    if t.has_key('class'):
        c = t['class']

        if re.search(negative, c):
            weight = weight - 25

        if re.search(positive, c):
            weight = weight + 25

    if t.has_key('id'):
        i = t['id']

        if re.search(negative, i):
            weight = weight - 25
        if re.search(positive, i):
            weight = weight + 25

    return weight

def cleanConditionally(e, tag):
    tags = e.findAll(tag)
    for t in reversed(tags):
        weight = classWeight(t)
        score = 0
        if t.score != None:
            score = t.score
        if weight + score < 0:
            t.extract()
            continue

        p = len(t.findAll('p'))
        img = len(t.findAll('img'))
        li = len(t.findAll('li')) - 100
        input = len(t.findAll('input'))

        ld = getLinkDensity(t)
        con = getText(t)

        if img > p:
            t.extract()
        elif li > p and tag.name != 'ul' and tag.name != 'ol':
            t.extract()
        elif input > p / 3:
            t.extract()
        elif con < 25 and img != 1:
            t.extract()
        elif weight < 25 and ld > 0.2:
            t.extract()
        elif weight >= 25 and ld > 0.5:
            t.extract()

def getContent(soup):
    
    # clean up tags with crappy class/id
    for tag in soup.findAll():
        classandid = ""
        if tag.has_key('class'):
            classandid = tag['class']
        if tag.has_key('id'):
            classandid = "%s %s" % (classandid, tag['id'])
        if re.search(unlikelycandidates, classandid) and not re.search(okcandidates, classandid) and not tag.name == 'body':
            tag.extract()

    toScore = soup.findAll(['p', 'td', 'pre'])
    candidates = []
    for n in toScore:
        if len(getText(n)) < 25:
            continue
        score = 0
        if n.score != None:
            score = n.score

        # 1 point for the paragraph itself
        score = score + 1
        # 1 point for each comma
        score = score + len(getText(n).split(","))
        # 1 point for each 100 characters, up to 3 max
        score = score + min(3, round(len(getText(n)) / 100))
            
        n.score = score

        # if there's a parent, add the score for this node to its score and add the parent
        # as a candidate
        if n.parent:
            if n.parent.score == None:
                n.parent.score = 0
                candidates.append(n.parent)
            n.parent.score = n.parent.score + score
            # same for grandparent, except only add half of the score
            if n.parent.parent:
                if n.parent.parent.score == None:
                    n.parent.parent.score = 0
                    candidates.append(n.parent.parent)
                n.parent.parent.score = n.parent.parent.score + score / 2.0

        candidates.append(n)

    candidates = map(scaleScore, candidates)
    h = sorted(candidates, key = lambda n: n.score, reverse= True)
    topCandidate = 0

    # if there is no top candidate, just use the body tag, but store the contents in a div
    if len(h) == 0 or h[0].name == 'body':
        topCandidate = Tag(soup, "div")
        topCandidate.score = 0
        for c in soup.html.body.contents:
            topCandidate.insert(len(topCandidate.contents), c)
        soup.html.body.insert(0, topCandidate)
        soup.html.body.score = 0
    else:
        topCandidate = h[0]
        
    # set up a new div to cram contents into
    article = Tag(soup, "div")

    siblings = topCandidate.parent.contents

    siblingScoreThreshold = max(10, topCandidate.score * 0.2)

    topClass = ""
    if topCandidate.has_key('class'):
        topClass = topCandidate['class']

    # iterate through siblings to see if anything else was left out
    for sib in siblings:
        append = False
        bonus = 0

        if sib == topCandidate:
            append = True

        if isinstance(sib, NavigableString):
            # text is mostly whitespace
            continue
        else:
            sibclass = ""
            if sib.has_key('class'):
                sibclass = sib['class']

            # bonus for having same class as topCandidate
            if sibclass == topClass and topClass != "":
                bonus = bonus + topCandidate.score * 0.2
                    
            sibtext = getText(sib)
            siblen = len(sibtext)
            sibscore = 0
            if sib.score:
                sibscore = sib.score

            # if above the threshold, it's in
            if sibscore + bonus > siblingScoreThreshold:
                append = True
        
            ld = getLinkDensity(sib)

            if sib.name == 'p':
                if siblen > 80 and ld < 0.25 :
                    append = True
                if siblen <= 80 and ld == 0 and siblen > 0:
                    append = True

        if append:
            article.insert(len(article.contents), sib)

    [el.extract() for el in soup.contents]
    
    soup.insert(0, article)

def cleanUp(soup):
    # get rid of script and style elements
    [el.extract() for el in soup.findAll(['script', 'style', 'link', 'noscript'])]

    # replace divs with no block elements with p
    divs = soup.findAll('div')
    for d in divs:
        if len(d.findAll(blockElements)) == 0:
            p = Tag(soup, "p")
            if d.has_key('id'):
                p['id'] = d['id']
            if d.has_key('class'):
                p['class'] = d['class']
            for t in d.contents:
                p.insert(len(p.contents), t)
            d.replaceWith(p)

    # get rid of empty p tags
    for p in soup.findAll('p'):
        if len(getText(p)) == 0:
            p.extract()

def postprocess(url, soup):
    cleanConditionally(soup, 'table')
    cleanConditionally(soup, 'ul')
    cleanConditionally(soup, 'div')

    # get rid of all classes and ids
    for el in soup.findAll(True):
        if el.has_key('class'):
            del(el['class'])
        if el.has_key('id'):
            del(el['id'])

    # get rid of style
    for el in soup.findAll(True):
        if el.has_key('style'):
            del(el['style'])
        if el.has_key('width'):
            del(el['width'])
        if el.has_key('height'):
            del(el['height'])

    # change links to absolute links
    links = soup.findAll('a')
    for l in links:
        if l.has_key('href'):
            l['href'] = urljoin(url, l['href'])

    # change imgs to absolute
    imgs = soup.findAll('img')
    for i in imgs:
        if i.has_key('src'):
            i['src'] = urljoin(url, i['src'])

    soup.div['class']='article-content'

def getContentFromURL(url):
    s = urlopen(url)
    doc = s.read()
    soup = BeautifulSoup(doc, convertEntities=BeautifulSoup.HTML_ENTITIES)

    cleanUp(soup)
    getContent(soup)
    postprocess(url, soup)

    return unicode(soup)
