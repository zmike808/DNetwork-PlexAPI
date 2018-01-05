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
rerun = 0

cache = '*'
if os.path.exists(os.path.splitext(__file__)[0] + '.cache'):
  cache = open(os.path.splitext(__file__)[0] + '.cache', 'r').read().replace('\n', '')
  
params = urllib.parse.urlencode({'t': cache})
conn = http.client.HTTPConnection(config['DEFAULT']['API_SERVER'])
url = config['DEFAULT']['API_QUERY'] + '?' + params
log.info ('[DNET] API CALL: %s ' % url)
conn.request('GET', url)
result = conn.getresponse()
data = result.read()
#log.info ('[DNET] API output: %s (%s)' % (data, url))
    
json_obj = json.loads(data)
if json_obj and len(json_obj) > 0:
  section = plex.library.section(config['DEFAULT']['PLEX_SECTION'])
  for obj in json_obj:
    sync = False
    root_file = obj['NAME'] + ' (' + obj['YEAR'] + ')'
    log.info ('[DNET] Scanning for %s in PLEX section %s' % (root_file, config['DEFAULT']['PLEX_SECTION']))
    total = total + 1
    
    if not cache == obj[config['DEFAULT']['CACHE']]:
      cache = obj[config['DEFAULT']['CACHE']]
    
    try:
      for video in section.search(title=obj['NAME'], sort='addedAt:desc'):
        log.info ('[DNET] Found Movie option in PLEX : %s' % (video.originalTitle))
        if video.originalTitle == root_file:
          sync = True
          log.info ('[DNET] MATCH - Found Movie in PLEX for %s (%s): %s' % (root_file, obj['ID'], video.originalTitle))      
          try:
            if obj['CHECKED'] == '0':
              status = 'New'
              #if video.isWatched:
              #  video.markUnwatched()
              #  log.info ('[DNET] > Switched ViewState for %s: Unwatched' % root_file)
            elif obj['CHECKED'] == '1':
              status = 'Checked'
              if not video.isWatched:
                video.markWatched()
                log.info ('[DNET] > Switched ViewState for %s: Watched' % root_file)
            elif obj['CHECKED'] == '2':
              status = 'Updated'
              #if video.isWatched:
              #  video.markUnWatched()
              #  log.info ('[DNET] > Switched ViewState for %s: Unwatched' % root_file)
              
            if obj['RATING'] != '0':
              video.edit(**{"userRating.value": ((float(obj['RATING'])/6)*10)})
              log.info ('[DNET] > Set userRating for %s: %s' % (root_file, ((float(obj['RATING'])/6)*10)))
            else:
              video.edit(**{"userRating.value": "-1"})
              log.info ('[DNET] > Set userRating for %s: None' % root_file)
            
            if len(video.labels) == 1:  
              if status == video.labels[0].tag:
                log.info ('[DNET] > Skipped Label for %s: %s' % (root_file, status))
                skipped = skipped + 1
                video.refresh()
                log.info ('[DNET] > Refreshed Metadata for %s' % root_file)
                break
            
            if len(video.labels) >= 1: 
              for label in video.labels:
                video.removeLabel(label.tag)
              # log.info ('[DNET] > Set Label for %s: None' % root_file)
              video.reload()
              # rerun = rerun + 1
              # break
                
            if len(video.labels) == 0:
              video.addLabel(status)
              log.info ('[DNET] > Set Label for %s: %s' % (root_file, status))
            scanned = scanned + 1
            video.refresh()
            log.info ('[DNET] > Refreshed Metadata for %s' % root_file)
            break
          except Exception as ex:
            log.info ('[DNET] > Could not post data from API for %s: %s' % (root_file, ex))
        else:
          log.info ('[DNET] Skipped Movie option in PLEX : %s' % (video.originalTitle))
    
      if sync == False:
        failed = failed + 1
        params = urllib.parse.urlencode({'q': root_file, 'payload': ''})
        conn.request("POST", config['DEFAULT']['API_HOOK'], params)
        result = conn.getresponse()
        if result.status == 200:
          log.info ('[DNET] Reset PLEX SYNC for %s' % root_file)
        else:
          log.info ('[DNET] Could not reset PLEX SYNC for %s' % root_file)
    except Exception as ex:
      log.info ('[DNET] Could not communicate with PLEX for %s: %s' % (root_file, ex))
      failed = failed + 1
  try:
    if rerun == 0:
      f = open(os.path.splitext(__file__)[0] + '.cache', 'w' )
      f.write(cache)
      f.close()
  except:
    log.info ('[DNET] Unable to write cache to %s: %s' % (os.path.splitext(__file__)[0] + '.cache', ex))
  
log.info ('[DNET] Job finished - TOTAL: %d, SCANNED: %d, SKIPPED: %d, RERUN: %d, FAILED: %d' % (total, scanned, skipped, rerun, failed))
