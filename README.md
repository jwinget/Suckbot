Suckbot
=======

Bad IRC Markov bot

Running
=======


```bash
virtualenv env

touch combined.txt

# copy default config to runtime config
cp config.yaml.default config.yaml

# update the settings for your own bot/server
vim config.yaml

./runbot.sh
```

`runbot.sh` will source the virtualenv, install/update dependencies, and launch the bot.
