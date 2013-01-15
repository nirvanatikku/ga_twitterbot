#!/usr/bin/env python

##
## Author: Nirvana Tikku (@ntikku, ntikku@gmail.com)
## Repo: https://github.com/nirvanatikku/ga_twitterbot
## License: MIT
##

import webapp2, json, logging, os, datetime, random ## core
import httplib2, tweepy ## libs
from datetime import timedelta
from apiclient.discovery import build
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.ext.webapp.util import run_wsgi_app
from PyCryptoSignedJWT import PyCryptoSignedJwtAssertionCredentials
from twbot.models import PendingTweet

##
## Let's get started.. Init our logger and dev_environment flag.
##

logger = logging.getLogger('ga_twitterbot')
logger.setLevel(logging.DEBUG)
dev_env = os.environ['SERVER_SOFTWARE'].startswith('Development')

##
## Constants
##

# all credentials are stored in twitterbot_credentials.json
# TODO: you must update this file with relevant credentials!
creds = json.loads(open('twitterbot_credentials.json').read())

#
# Google Analytics/API credentials
#
gdata_scopes = creds['scopes']
# TODO: you will need to fetch this from your google API console and add it to twitterbot_credentials.json.
# refer to: 'API access' for your application within - https://code.google.com/apis/console/
# note: must be a SERVICE account.
client_id = creds['client_id']
service_account = creds['service_account']
# TODO: you will need to generate this the crypto_key 'privatekey.pem' after downloading key.p12 from the API console.
# refer to: https://github.com/richieforeman/google-api-python-client-pycryptojwt/blob/master/README.md#key-conversion
crypto_key = creds['pem_filename'] 

#
# Twitter OAuth credentials
#
tw_consumer_key = creds['tw_consumer_key']
tw_consumer_secret = creds['tw_consumer_secret']
tw_access_token = creds['tw_access_token']
tw_access_token_secret = creds['tw_access_token_secret']

##
## /Constants
##

logger.info("<<< Initializing Twitter Bot >>>")

##
## Services
##

try:
	logger.debug("service init")

	key = open(crypto_key).read()
	logger.debug(">> loaded key")

	##
	## google oauth
	##
	credentials = PyCryptoSignedJwtAssertionCredentials(
		service_account,
		key, 
		scope=" ".join(gdata_scopes))
	logger.debug(">> built credentials")

	http = httplib2.Http()
	httplib2.debuglevel = True
	http = credentials.authorize(http)
	logger.debug(">> authorized credentials and init'd http obj")

	service = build(serviceName='analytics', version='v3', http=http)
	logger.debug(">> analytics service init'd")

	##
	## twitter oauth 
	##
	auth = tweepy.OAuthHandler(tw_consumer_key, tw_consumer_secret)
	auth.set_access_token(tw_access_token, tw_access_token_secret)
	api = tweepy.API(auth)
	logger.debug(">> twitter/tweepy init'd")

	logger.info("service init'd!")
except Exception:
	logger.debug("Error initializing google analytics and tweepy")
	service = None
	api = None

##
## /Services
##

##
## Utils
##

"""
BotMessage is a template renderer.
This class takes a context and will render a template as defined
in the 'templates' directory. Simply instantiate a new BotMessage 
and invoke the 'render_page' method with the desired template, 
and a context (dictionary).
"""
class BotMessage:

	ROOT = "templates/"

	def __init__(self):
		self.path = BotMessage.ROOT

	def render_page(self, pagePath, ctx={}):
		return self.render(pagePath,ctx)

	## pagePath: string, ctx: dict
	def render(self, tmplPath, ctx={}):
		path = os.path.join(os.path.dirname(__file__), self.path + tmplPath)
		return template.render(path, ctx)

"""
This utility initializes the start and end date for the query upon instantiation.
Once instantiated, invoke 'seed' to populate the PendingTweets. 
You can setup your own logic here. In this example, the twitterbot will publish
trending tracks in descending order; in order to achieve this I store a 'rank'.
This assumes that the GA query performs the sort. 
"""
class SeedTweetsUtil:

	# init'd from twitterbot_credentials
	Google_Analytics_ID = creds['ga_account_id']
	
	# query related
	# TODO: you will want to update this as per your requirements.
	Google_Analytics_Max_Results = "100"
	Google_Analytics_Filters = 'ga:eventAction==YouTube'
	Google_Analytics_Sort = '-ga:totalEvents'
	Google_Analytics_Dimensions = 'ga:eventLabel'
	Google_Analytics_Metrics = 'ga:totalEvents'

	def __init__(self):
		self.start_date = self.get_start_date()
		self.end_date = self.get_end_date()

	""" currently set to: 'yesterday' """
	def get_start_date(self):
		day_before = datetime.datetime.now() - timedelta(days=1)
		return day_before.strftime("%Y-%m-%d")

	""" currently set to: 'today' """
	def get_end_date(self):
		return datetime.datetime.now().strftime("%Y-%m-%d")

	def seed(self):
		logger.debug('seeding tweets from date range: %s - %s' % (self.start_date, self.end_date))
		try:
			""" query google analytics """
			api_query = service.data().ga().get(
				ids = SeedTweetsUtil.Google_Analytics_ID,
				start_date = self.start_date,
				end_date = self.end_date,
				metrics = SeedTweetsUtil.Google_Analytics_Metrics,
				dimensions = SeedTweetsUtil.Google_Analytics_Dimensions,
				sort = SeedTweetsUtil.Google_Analytics_Sort,
				filters = SeedTweetsUtil.Google_Analytics_Filters,
				max_results = SeedTweetsUtil.Google_Analytics_Max_Results)
			results = api_query.execute()
			logger.info(" google analytics query results %s " % results )
			self.store_pending_tweets(results)
			return True
		except Exception as e:
			logger.debug(str(e)) 
			return False
		
	""" 
	Loops through results. In this example, values are '[PRIMARY_KEY]_[YOUTUBE_ID]' and thus must be stripped. 
	TODO: you will want to prune and store data that is relevant to you.
	"""
	def store_pending_tweets(self, query_results):
		logger.debug('attempting to store pending tweets')
		trackIDcache = [] # keep a cache to ensure that we aren't adding the same PRIMARY_KEY twice. artifact of my analytics data.
		""" now we store our pending tweets """
		if len(query_results.get('rows', [])) > 0:
			db.delete(PendingTweet.all()) # clear all the pending tweets
			logger.debug("cleared all pending tweets")
			pos = 1
			for row in query_results.get('rows'):
				logger.debug( '\t'.join(row) )
				firstPart = row[0].index("_") # eventLabel, the first column, looks like "12726_NngHqOYtMoo"
				trackInfo = [row[0][0:firstPart], row[0][firstPart+1:]]
				logger.debug("track info is %s " % trackInfo)
				trackID = trackInfo[0]
				trackYouTubeID = trackInfo[1]
				playCount = long(row[1])
				if trackID not in trackIDcache and trackYouTubeID != 'NoVideoFound':
					pos += self.store_pending_tweet(trackID, trackYouTubeID, playCount, pos)
					trackIDcache.append(trackID)

	""" store a pending tweet to the datastore. these will be retrieved and used in constructing the tweet. """
	def store_pending_tweet(self, trackID, trackYouTubeID, playCount, pos):
		## in this example, we're going to store the track primary key, the associated youtube video id, the # of times played, and the rank.
		pt = PendingTweet(trackPk=trackID, youtubeID=trackYouTubeID, playCount=playCount, rank=pos)
		pt.put()
		logger.info("Adding a PendingTweet (%s) " % pt)
		return 1

##
## /Utils
##

##
## Request Handlers
##

"""
The BaseHandler is based off the webapp2 RequestHandler.
The noteworthy property of this class is:
	> provides a 'tweet' method that takes a context and will build a Tweet object, 
		stores it, and publishes the update and returns a tuple with the status update and the message.
		>> If in dev environment, doesn't publish to twitter
		>> If in prod environment, publishes to twitter
"""
class BaseHandler(webapp2.RequestHandler):

	def __init__(self, request, response):
		super( BaseHandler, self ).__init__(request, response)

	## build, save and publish the tweet
	def tweet(self, ctx):	
		msg = BotMessage().render_page('status', ctx)
		logger.info("posting tweet %s" % msg)
		if dev_env:
			return (msg, msg)
		else:
			return (api.update_status(msg), msg)

"""
The CronTweetHandler is expected to be tied to the endpoint that publishes
the tweet. This request handler performs a few tasks:
	1. Retrieves the latest tweet, sorted by 'playCount' in this example
	2. If the tweet is considered in the top 10 positions, prefixes with a 'position' char
"""
class CronTweetHandler(BaseHandler):

	"""
	Provides some ordering to tweets. For Top 10, prefix the tweet with '1', '2', '3' etc. 
	Minimizes character usage by using unicode values (simply 1 char).
	"""
	def get_pos_string(self, pos):
		if pos is None:
			return ''
		if pos > 10:
			return ''
		if pos == 1:
			return u' \u2780 '
		elif pos == 2:
			return u' \u2781 '
		elif pos == 3:
			return u' \u2782 '
		elif pos == 4:
			return u' \u2783 '
		elif pos == 5:
			return u' \u2784 '
		elif pos == 6:
			return u' \u2785 '
		elif pos == 7:
			return u' \u2786 '
		elif pos == 8:
			return u' \u2787 '
		elif pos == 9:
			return u' \u2788 '
		elif pos == 10:
			return u' \u2789 '
		else:
			return ''

	""" 
	TODO: customize this as per your requirements. 
	in this example, we get the most played track
	in the stored 'pending' tweets.
	"""
	def get_pending_tweet(self):
		return db.Query(PendingTweet).order("-playCount").get()

	""" Handle our get request. We will fetch our pending tweet, and publish it. """
	def get(self):
		pending_tweet = self.get_pending_tweet()
		logger.debug("working with %s" % pending_tweet)
		if pending_tweet is not None:
			ctx = {}
			ctx['youtubeID'] = str(pending_tweet.youtubeID)
			ctx['rank'] = self.get_pos_string(pending_tweet.rank)
			pending_tweet.delete()
			logger.info("tweeting %s" % ctx)
			ret = self.tweet(ctx)
			self.response.write("%s" % ret[1])
		else:
			self.response.write("couldn't tweet. seems as though pending_tweet doesn't exist.")

"""
This is our request handler that will seed the datastore with
relevant information from Google Analytics. 
"""
class CronSeedTweetsHandler(BaseHandler):

	def get(self):
		logger.debug('request to seed tweets')
		seeder = SeedTweetsUtil()
		seeded = seeder.seed()
		self.response.write("Successfully Seeded PendingTweets" if seeded is True else "Failed to Seed PendingTweets")
		return

##
## /Handlers
##

"""
The main application. There are two endpoints that are relevant: 
	1. seed tweets
	2. publish a tweet
"""
app = webapp2.WSGIApplication([
    ('/cron/seed_tweets', CronSeedTweetsHandler),
    ('/cron/tweet', CronTweetHandler)
], debug=dev_env)

def main():
	run_wsgi_app(app)

if __name__ == '__main__':
	main()
	logger.info("<<< Initialized Twitter Bot! >>>")
