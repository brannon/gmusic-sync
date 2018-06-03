# gmusic-sync

Beets plugin for syncing music to Google Play Music

# Using from the Git repo
 
## Clone the repo

```
mkdir -p $HOME/src
cd $HOME/src
git clone https://github.com/brannon/gmusic-sync
```

## Install dependencies

```
cd $HOME/src/gmusic-sync
pip install -r requirements.txt
```

## Add to the `PYTHONPATH`

This is necessary for the plugin to be discovered by beets.

TODO: Support installing the plugin via pip

```
export PYTHONPATH="$HOME/src/gmusic-sync"
```

## Add the plugin to the beets config

```
beet config -e
```

That should open the beets config yaml in vim. Add the following to the `plugins` section:
```
plugins:
  - gmusic-sync
```

## Verify the plugin is working

```
beet gmusic-sync --help
```

NOTE: Running this the first time should display an OAuth prompt for Google Play Music. Follow the directions.

The output should look like:
```
Usage: beet gmusic-sync [options]

Options:
  -h, --help     show this help message and exit
  -p, --pretend
```

Any errors mean the plugin is not installed / configured correctly.
