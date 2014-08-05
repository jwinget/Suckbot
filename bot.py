import random
import re
import string
import itertools
import urllib2
from BeautifulSoup import BeautifulSoup
#import lxml.html

from irc import IRCBot, run_bot

g_chain_length = 2

class MarkovBot(IRCBot):
    """
    http://code.activestate.com/recipes/194364-the-markov-chain-algorithm/
    http://github.com/ericflo/yourmomdotcom
    """
    chain_length = g_chain_length
    chattiness = .01
    max_words = 30
    messages_to_generate = 5
    prefix = 'irc'
    separator = '-'
    stop_word = '\n'
    brainfile = 'combined.txt'
    brain = {}
    
    def __init__(self, *args, **kwargs):
        super(MarkovBot, self).__init__(*args, **kwargs)
        self.parse_brain(self.brainfile)
        
    def make_key(self, k):
        return '-'.join((self.prefix, k))
    
    def sanitize_message(self, message):
        return re.sub('[\"\']', '', message.lower())

    def split_message(self, message):
        # split the incoming message into words, i.e. ['what', 'up', 'bro']
        words = message.split()
        
        # if the message is any shorter, it won't lead anywhere
        if len(words) > self.chain_length:
            
            # add some stop words onto the message
            # ['what', 'up', 'bro', '\x02']
            words.append(self.stop_word)
            
            # len(words) == 4, so range(4-2) == range(2) == 0, 1, meaning
            # we return the following slices: [0:3], [1:4]
            # or ['what', 'up', 'bro'], ['up', 'bro', '\x02']
            for i in range(len(words) - self.chain_length):
                yield words[i:i + self.chain_length + 1]

    def parse_brain(self, brainfile):
        with open(brainfile, 'rb') as f:
            for line in f:
                for words in self.split_message(self.sanitize_message(line)):
                    # grab everything but the last word
                    key = self.separator.join(words[:-1])
                    
                    # add the last word to the set
                    try:
                        if words[-1] not in self.brain[key]:
                            self.brain[key].append(words[-1])
                    except KeyError:
                        self.brain[key] = [words[-1]]

    def get_pagetitle(self, url):
        try:
            soup = BeautifulSoup(urllib2.urlopen(url))
            title = soup.title.string
            #t = lxml.html.parse(url)
            #title = t.find(".//title").text.encode('utf-8', errors='ignore')
        except:
            title = 'No title'
        return title

    def generate_message(self, seed):
        key = seed
        
        # keep a list of words we've seen
        gen_words = []
        
        # only follow the chain so far, up to <max words>
        for i in xrange(self.max_words):
        
            # split the key on the separator to extract the words -- the key
            # might look like "this\x01is" and split out into ['this', 'is']
            words = key.split(self.separator)
            
            # add the word to the list of words in our generated message
            gen_words.append(words[0])
            
            # get a new word that lives at this key -- if none are present we've
            # reached the end of the chain and can bail
            try:
                choices = (self.brain[key])
                if len(choices) > 0:
                    end_it = False
                    if '\n' in choices and random.randrange(100) < 4:
                        end_it = True
                    if not end_it:
                        next_word = random.choice(choices)
                    else:
                        next_word = '\n'
                else:
                    next_word = '\n'
            except KeyError:
                break
            if next_word == self.stop_word:
                # add the last word and break
                gen_words.append(words[1])
                break
         
            # create a new key combining the end of the old one and the next_word
            key = self.separator.join(words[-1:] + [next_word])

        return ' '.join(gen_words)

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

        if not say_something:
            # write out to brain file
            with open(self.brainfile, 'a') as f:
                f.write(message + '\n')

            # add new line into his brain
            for words in self.split_message(self.sanitize_message(message)):
                # grab everything but the last word
                key = self.separator.join(words[:-1])
                
                # add the last word to the set
                try:
                    if words[-1] not in self.brain[key]:
                        self.brain[key].append(words[-1])
                except KeyError:
                    self.brain[key] = [words[-1]]

        # old method of finding candidate chains
        #for words in self.split_message(self.sanitize_message(message)):

        # split up the incoming message into chunks that are 1 word longer than
        # the size of the chain, e.g. ['what', 'up', 'bro'], ['up', 'bro', '\x02']
        for words in itertools.permutations(self.sanitize_message(message).split(),g_chain_length):
            # grab everything but the last word
            key = self.separator.join(words)

            # if we should say something, generate some messages based on what
            # was just said and select the longest, then add it to the list
            if say_something:
                best_message = ''
                for i in range(self.messages_to_generate):
                    generated = self.generate_message(seed=key)
                    if len(generated) > len(best_message):
                        best_message = generated
               
                # throw out messages 2 words or shorter
                if best_message and len(best_message.split()) > g_chain_length:
                    messages.append(best_message)
        
        if len(messages):
            rand_index = random.randrange(len(messages))
            return messages[rand_index]

    def command_patterns(self):
        return (
            ('.*', self.log),
        )


host = 'kamigamiguild.com'
port = 6667
nick = 'SuckBot'

run_bot(MarkovBot, host, port, nick, ['#general'])
