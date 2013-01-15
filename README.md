# TwitterBot via AppEngine (Driven by Google Analytics) #

I've provided all the necessary libraries in this project. Ideally I would have set it up with submodules, but I wanted to provide a guaranteed solution for you, the developer, to get up and running as soon as possible.

### Initial Setup ###
- Clone this repo
- Create a new AppEngine app from this repo

### Google Analytics Setup ###
- Go to the Google API Console
- Register for Google Analytics 
- Create a Service Account
- Download the .p12 key
- Convert the p12 key into a pem key (look at the PyCryptoSignedJWT readme) such that 'privatekey.pem' is sufficiently populated
- Add relevant values from Google API Console to twitterbot_credentials.json

### Twitter Setup ###
- Go to the Twitter API Portal
- Create an App
- Create your OAuth key
- Add relevant values from Twitter API Portal to twitterbot_credentials.json

### Query Setup ###
- Build the GA query via the Query Explorer
- Ensure that the GA Profile contains the gserviceaccount user
- Update SeedTweetsUtil as per your query and business requirements
- Update templates/status with whatever values are present in your context
- Alter the twbot/models.py for whatever information you need to store in PendingTweet

### Tune the Cron.yaml schedules ###
- Update cron.yaml with desired times

Once you have completed the steps above, ensure that the app.yaml file has your app's name, then go ahead and deploy it.

If you have any questions, feel free to reach out to me: ntikku at gmail dot com
