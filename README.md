Requires a local_config.py file in ./input/dota/stream containing:

* a DOTA2_API_KEY variable set to a valid developer API key for the Dota 2 web
    API.
* a AWSAccessKeyId and AWSSecretKey for AWS.

You also need an SQS queue with the name "dota_match_ids" on your AWS account.
I have configured mine with a max message size of 1 KB for now, since the body
is just the match ID.

Install redis (see http://redis.io/topics/quickstart)

Start redis:

    redis-server

Also requires boto installed:

    # Install boto (Amazon SQS SDK)
    pip install boto

luarocks:

    sudo apt-get install luarocks

luasocket:

    sudo luarocks install luasocket
