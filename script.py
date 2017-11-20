from plexapi.server import PlexServer
from logging.handlers import TimedRotatingFileHandler
import os, urllib.parse, http.client, json, logging, time, configparser

log = logging.getLogger(os.path.splitext(__file__)[0])
log.setLevel(logging.INFO)
handler = TimedRotatingFileHandler(os.path.splitext(__file__)[0] + '.log', when='midnight', interval=1, backupCount=3)
handler.setFormatter(logging.Formatter('[%(asctime)s][%(levelname)s](%(threadName)-10s) %(message)s'))
log.addHandler(handler)

config = configparser.ConfigParser()
if os.path.exists(os.path.splitext(__file__)[0] + '.ini'):
  config.read(os.path.splitext(__file__)[0] + '.ini')

plex = PlexServer(config['DEFAULT']['PLEX_SERVER'], config['DEFAULT']['PLEX_TOKEN'])

total = 0
scanned = 0
failed = 0
skipped = 0

movies = plex.library.section(config['DEFAULT']['PLEX_SECTION'])
for video in movies.search(sort='addedAt:desc'):
  root_file= os.path.splitext(os.path.basename(video.locations[0]))[0]
  log.info ('[DNET] Scanning Movie %s' % (root_file))
  total = total + 1
  
  params = urllib.parse.urlencode({'q': root_file})
  conn = http.client.HTTPConnection(config['DEFAULT']['API_SERVER'])
  conn.request('GET', config['DEFAULT']['API_QUERY'] + '?' + params)
  result = conn.getresponse()
  data = result.read()
  #log.info ('[DNET] API output for %s: %s' % (root_file, data))
  
  json_obj = json.loads(data)
  
  if json_obj:
    log.info ('[DNET] Found Movie ID #%s for %s' % (json_obj['ID'], root_file))
    try:
      if json_obj['CHECKED'] == '0':
        status = 'New'
        #if video.isWatched:
        #  video.markUnwatched()
      elif json_obj['CHECKED'] == '1':
        status = 'Checked'
        if not video.isWatched:
          video.markWatched()
      elif json_obj['CHECKED'] == '2':
        status = 'Updated'
        #if video.isWatched:
        #  video.markUnWatched()
      
      if len(video.labels) == 1:  
        if status == video.labels[0].tag:
          log.info ('[DNET] Skipped Label for %s: %s' % (root_file, status))
          skipped = skipped + 1
          continue
      
      if len(video.labels) >= 1: 
        for label in video.labels:
          video.removeLabel(label.tag)
          
      if len(video.labels) == 0:
        video.addLabel(status)
        log.info ('[DNET] Label set to %s for %s' % (status, root_file))
      scanned = scanned + 1
    except Exception as ex:
      log.info ('[DNET] Could not post data from API for %s: %s' % (root_file, ex))
  else:
    if len(video.labels) >= 1: 
      for label in video.labels:
        video.removeLabel(label.tag)
        
    if len(video.labels) == 0:
      video.addLabel('None')
      log.info ('[DNET] MOVIE NOT FOUND: %s' % (root_file))
    failed = failed + 1
  
log.info ('[DNET] Job finished - TOTAL: %d, SCANNED: %d, SKIPPED: %d, FAILED: %d' % (total, scanned, skipped, failed))