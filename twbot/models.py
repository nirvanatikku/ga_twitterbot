from google.appengine.ext import db

class PendingTweet(db.Model):
    trackPk = db.StringProperty()
    youtubeID = db.StringProperty()
    playCount = db.IntegerProperty()
    seeded = db.DateTimeProperty(auto_now=True)
    rank = db.IntegerProperty()
