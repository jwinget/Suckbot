import random
import re
import string
import itertools
import urllib2
import sys
from BeautifulSoup import BeautifulSoup, BeautifulStoneSoup
import yaml
import os.path
import requests
import json
import traceback
from unidecode import unidecode
import markovify
import nltk
import numpy

from irc import IRCBot, run_bot

reload(sys)
sys.setdefaultencoding('utf-8')

g_chain_length = 2

config_file = "./config.yaml"

if not os.path.isfile(config_file):
  print "config.yaml does not exist.  Copy config.yaml.default to config.yaml and update settings"
  sys.exit(1)

config = yaml.load(file(config_file))

host = config['irc']['host']
port = config['irc']['port']
chans = config['irc']['channels']
nick = config['bot']['name']

last_msg = ''

class POSifiedText(markovify.Text):
    """
    Generates a better markov model, but is slower
    """
    def word_split(self, sentence):
        words = re.split(self.word_split_pattern, sentence.decode('utf8','ignore'))
        words = [ '::'.join(tag) for tag in nltk.pos_tag(words) ]
        return words
    def word_join(self, words):
        sentence = " ".join(word.split("::")[0] for word in words)
        return sentence

class MarkovBot(IRCBot):
    """
    http://code.activestate.com/recipes/194364-the-markov-chain-algorithm/
    http://github.com/ericflo/yourmomdotcom
    """
    chain_length = g_chain_length
    chattiness = .01
    prefix = 'irc'
    separator = '-'
    stop_word = '\n'
    brainfile = 'combined.txt'
    text_model = None
    
    def __init__(self, *args, **kwargs):
        super(MarkovBot, self).__init__(*args, **kwargs)
        self.parse_brain(self.brainfile)

    def make_key(self, k):
        return '-'.join((self.prefix, k))
    
    def sanitize_message(self, message):
        return re.sub('[\"\']', '', message.lower())

    def parse_brain(self, brainfile):
        with open(brainfile, 'rb') as f:
            text = f.read()
        self.text_model = POSifiedText(text)

    def get_pagetitle(self, url):
        try:
            hdr = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8'}
            req = urllib2.Request(url,headers=hdr)
            page = urllib2.urlopen(req)
            soup = BeautifulSoup(page, convertEntities=BeautifulSoup.HTML_ENTITIES)
            titleTag = soup.html.head.title
        except:
            title = ""
            print 'nobots '+title
            return title
        try:
            title = unidecode(titleTag.string)
            print 'success '+title
        except:
            try:
                title = unicode.decode(titleTag.string)
                print 'unicode '+title
            except:
                title = 'No title'
        return title

    def random_image(self, msg, fetch=True, rsz=8, pages=5, rand_result=True, nsfw=False, animate=False):
        ''' Return a random google image '''
        print "Random Image: msg = %s, fetch = %s, nsfw = %s, rsz = %s, pages = %s, rand = %s, animate = %s" % (msg, fetch, nsfw, rsz, pages, rand_result, animate)
        max_attempts = 5
        if rand_result:
            attempts = 0
        else:
            attempts = max_attempts - 1
        while attempts < max_attempts:
            attempts += 1
            gurl = 'http://ajax.googleapis.com/ajax/services/search/images'
            payload = {'v': '1.0', 'rsz': rsz}
            if rand_result:
                payload['start'] = rsz * random.randrange(pages)
            else:
                payload['start'] = rsz * pages
            if nsfw:
                payload['safe'] = 'off'
            else:
                payload['safe'] = 'active'
            if animate:
                payload['imgtype'] = 'animated'
            payload['q'] = msg
            r = requests.get(gurl, params=payload)
            try:
                parsed = json.loads(r.text)
                results = (parsed['responseData']['results'])
                urls = []
                random.shuffle(results)
                # TODO: Look at grabbing unescaped URL and trimming hashes from URL
                # Might eliminate some invalid extension false positives
                url = results[0][u'url']
                valid_suffixes = ('.gif','.jpg','.jpeg','.png')
                #if not url.lower().endswith(valid_suffixes):
                #    print "Bad file suffix for URL: " + url
                #    continue;
                if fetch:
                  response = requests.head(url)
                  if response.status_code != 200:
                      print "Bad status code: got %d for %s" % (response.status_code, url )
                      continue
                return url + ""
            except:
                e = sys.exc_info()[0]
                print "Error grabbing images"
                print traceback.format_exc()
        return 'Unable to find image'

    def generate_message(self, text_model):
        sentence = text_model.make_short_sentence(140)
        return sentence

    def log(self, sender, message, channel):
        # speak only when spoken to, or when the spirit moves me
        suckbot = re.compile('suckbot', re.IGNORECASE)
        if suckbot.search(message):
            say_something = True
        elif random.random() < self.chattiness:
            say_something = True
        elif self.is_ping(message):
            say_something = True
        else:
            say_something = False
        
        messages = []
        
        # use a convenience method to strip out the "ping" portion of a message
        if self.is_ping(message):
            message = self.fix_ping(message)

        if message.startswith('/'):
            return

        if message.endswith('?'):
            message = message[:-1]

        # possible image search regex
        imageRe = re.compile('^(nsfw )?(image|animate) (me|nth|first|random)(.*)$', re.IGNORECASE)
        if '!!' in message:
            global last_msg
            message = message.replace('!!', last_msg)
        matches = imageRe.search(message)
        if matches:
            # defaults
            rsz = 8
            pages = 8
            rand_result = True
            image_search = matches.group(4)
            animate = False

            # did message start with nsfw?
            nsfw = matches.group(1) == 'nsfw '

            if matches.group(2) == 'animate':
                animate = True

            if matches.group(3) == 'me':
                # no change from defaults
                'nothing'
            elif matches.group(3) == 'first':
                # only grab first result
                rsz = 1
                pages = 0
                rand_result = False
            elif matches.group(3) == 'random':
                # use random text
                image_search = ' '.join(random.choice(self.brain.keys()).split(self.separator))
            elif matches.group(3) == 'nth':
                # parse the number from the rest of the message
                remaining = matches.group(4).split(' ')
                pages = int(remaining[1]) - 1
                image_search = ' '.join(remaining[2:])
                rsz = 1
                rand_result = False

            try:
                return image_search + ': ' + self.random_image(image_search, rsz=rsz, pages=pages, rand_result=rand_result, nsfw=nsfw, animate=animate)
            except:
                return 'HI MY NAME IS CHURCHY AND I LIKE BREAKING THINGS'

        if 'meow bomb' in message:
            urls = []
            for i in range(0,5):
                # don't full fetch the result to make it faster.  chances are most will work
                urls.append(self.random_image("meow",fetch=False))
            return ' '.join(urls)

        if 'i.imgur' in message and 'http' not in message:
            say_something = True
            parts = message.split()
            for p in parts:
                if 'imgur' in p:
                    return('lrn2url: http://'+p)

        if 'http' in message:
            say_something = True
            parts = message.split()
            for p in parts:
                if 'http' in p:
                    title = self.get_pagetitle(p)
                    return title

        turbine = re.compile('turbine', re.IGNORECASE)
        if turbine.search(message):
            return 'POWERED BY OUR FANS'

        dk = re.compile('draftkings', re.IGNORECASE)
        if dk.search(message):
            return 'SPORTS'

        if not say_something:
            last_msg = message
            # write out to brain file
            with open(self.brainfile, 'a') as f:
                f.write(message + '\n')

            # add new line into his brain
            text_model += markovify.Text(message)

        if say_something:
            return self.generate_message(self.text_model)
               

    def command_patterns(self):
        return (
            ('.*', self.log),
        )


run_bot(MarkovBot, host, port, nick, chans)
