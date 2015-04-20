__author__ = 'daisy'

class Streamer:
  """
  Processes matches from the Dota 2 web API
  (see http://dev.dota2.com/showthread.php?t=58317 and
  https://wiki.teamfortress.com/wiki/WebAPI#Dota_2) and transforms polling
  requests into a stream.

  This class is not thread-safe.
  """

  def start(self, poll_interval=2000):
    """
    Starts the Streamer; may not be started if it has already started.
    :param poll_interval: Number of milliseconds after which to poll for new
      matches.  Default is 2000.  Valve suggests rate limiting within
      applications to at most one request per second.
    :return:
    """
    # TODO

  def stop(self):
    """
    Stops the Streamer, closing all connections.  It is fine to stop a Streamer
    more than once.
    :return:
    """
    # TODO